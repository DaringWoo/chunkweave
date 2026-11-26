"""ChunkEngine public API: execute/validate/compile, registration, tracing."""

import pytest
from pydantic import BaseModel, ConfigDict, Field, StrictInt

import chunkweave
from chunkweave import (
    ChunkEngine,
    ChunkResult,
    ChunkSpan,
    ExecutionPlan,
    PolicyValidationError,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
)
from conftest import FakeProvider, make_policy


def single_level(strategy="sliding_window", params=None, name="l0", **kw):
    return make_policy(
        [{"name": name, "strategy": strategy, "params": params or {}}], **kw
    )


class EveryNParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: StrictInt = Field(default=2, gt=0)


class EveryNChunker:
    """Custom chunker: fixed N-code-point pieces."""

    def __init__(self, params):
        self.size = params.size

    def chunk(self, text: str) -> list[ChunkSpan]:
        return [
            ChunkSpan(
                content=text[s : s + self.size],
                start_offset=s,
                end_offset=min(s + self.size, len(text)),
                strategy_metadata={"half": i},
            )
            for i, s in enumerate(range(0, len(text), self.size))
        ]


class NeedyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NeedyChunker:
    """Custom chunker that requires a provider."""

    def __init__(self, provider):
        self.provider = provider

    def chunk(self, text: str) -> list[ChunkSpan]:
        if self.provider is None:
            raise ProviderMissingError("needy")
        return [ChunkSpan(content=text, start_offset=0, end_offset=len(text))]


# ---- execute basics ----


def test_execute_single_level():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        single_level(params={"chunk_size": 3}),
    )
    assert isinstance(result, ChunkResult)
    assert [c.content for c in result.chunks] == ["abc", "def", "gh"]


def test_execute_two_levels():
    engine = ChunkEngine()
    result = engine.execute(
        "ab\ncdef\n\ngh",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 3}},
            ]
        ),
    )
    assert len(result.chunks) == 6
    assert {c.level for c in result.chunks} == {0, 1}


def test_execute_rejects_non_policy():
    engine = ChunkEngine()
    for bad in ("policy.yaml", "api_version: chunkweave/v1", {"pipeline": {}}, 42):
        with pytest.raises(TypeError):
            engine.execute("abc", bad)


def test_execute_rejects_non_text():
    engine = ChunkEngine()
    with pytest.raises(TypeError):
        engine.execute(b"bytes", single_level(params={"chunk_size": 2}))
    with pytest.raises(TypeError):
        engine.execute(None, single_level(params={"chunk_size": 2}))


def test_compile_and_validate_reject_non_policy():
    engine = ChunkEngine()
    for bad in ("x.yaml", {"pipeline": {}}, None):
        with pytest.raises(TypeError):
            engine.compile(bad)
        with pytest.raises(TypeError):
            engine.validate(bad)


def test_unregistered_strategy_surfaces_error():
    engine = ChunkEngine()
    with pytest.raises(UnregisteredStrategyError) as exc:
        engine.execute("abc", single_level(strategy="nope"))
    assert "nope" in str(exc.value)


def test_execute_unknown_param_rejected():
    engine = ChunkEngine()
    with pytest.raises(PolicyValidationError) as exc:
        engine.execute(
            "abc",
            single_level(params={"chunk_size": 4, "nope": 1}),
        )
    assert "nope" in str(exc.value)


# ---- validate ----


def test_validate_returns_none_and_does_not_chunk():
    class ExplodingChunker:
        def chunk(self, text):
            raise AssertionError("chunk() must not be called by validate")

    engine = ChunkEngine()
    engine.register(
        "boom",
        lambda params, _p: ExplodingChunker(),
        params_model=NeedyParams,
    )
    policy = make_policy([{"name": "l0", "strategy": "boom"}])
    assert engine.validate(policy) is None


def test_validate_rejects_invalid_policy():
    engine = ChunkEngine()
    with pytest.raises(UnregisteredStrategyError):
        engine.validate(single_level(strategy="ghost"))


# ---- provider ----


def test_semantic_needs_provider_before_chunking():
    engine = ChunkEngine()
    policy = single_level(
        strategy="semantic",
        params={"threshold": 0.5, "chunk_size": 10},
    )
    with pytest.raises(ProviderMissingError):
        engine.execute("a。b。", policy)


def test_custom_requires_provider_needs_provider():
    engine = ChunkEngine()
    engine.register(
        "needy",
        lambda params, provider: NeedyChunker(provider),
        params_model=NeedyParams,
        requires_provider=True,
    )
    policy = single_level(strategy="needy")
    with pytest.raises(ProviderMissingError):
        engine.execute("abc", policy)
    # with a provider the same policy runs
    result = engine.execute("abc", policy, provider=FakeProvider())
    assert len(result.chunks) == 1


def test_missing_provider_error_before_any_chunking():
    """Provider check happens before chunkers are even constructed."""
    constructed = []

    class TrackingChunker:
        def __init__(self):
            constructed.append(1)

        def chunk(self, text):
            return []

    engine = ChunkEngine()
    engine.register(
        "tracked",
        lambda params, _p: TrackingChunker(),
        params_model=NeedyParams,
    )
    policy = make_policy(
        [
            {"name": "l0", "strategy": "tracked"},
            {"name": "l1", "strategy": "semantic",
             "params": {"threshold": 0.5, "chunk_size": 4}},
        ]
    )
    with pytest.raises(ProviderMissingError):
        engine.execute("abc", policy)
    assert constructed == []  # no chunker was even created


def test_provider_exception_propagates():
    class BadProvider:
        def score(self, left, right):
            raise ValueError("embedding service down")

    engine = ChunkEngine()
    policy = single_level(
        strategy="semantic",
        params={"threshold": 0.5, "chunk_size": 10},
    )
    with pytest.raises(ValueError, match="embedding service down"):
        engine.execute("a。b。c。", policy, provider=BadProvider())


# ---- registration ----


def test_register_custom_chunker_used_at_any_level():
    engine = ChunkEngine()
    engine.register(
        "everyn", lambda params, _p: EveryNChunker(params), params_model=EveryNParams
    )
    flat = engine.execute(
        "abcdef",
        single_level(strategy="everyn", params={"size": 2}),
    )
    assert [c.content for c in flat.chunks] == ["ab", "cd", "ef"]
    hier = engine.execute(
        "abcd\n\nefgh",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 6, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "everyn", "params": {"size": 3}},
            ]
        ),
    )
    level1 = [c for c in hier.chunks if c.level == 1]
    assert level1
    assert all(c.strategy_metadata.get("half") is not None for c in level1)


def test_custom_params_validated_by_params_model():
    engine = ChunkEngine()
    engine.register(
        "everyn", lambda params, _p: EveryNChunker(params), params_model=EveryNParams
    )
    # undefined key rejected by the params model
    with pytest.raises(PolicyValidationError) as exc:
        engine.execute("abc", single_level(strategy="everyn", params={"nope": 1}))
    assert "nope" in str(exc.value)
    # invalid value rejected too
    with pytest.raises(PolicyValidationError):
        engine.execute("abc", single_level(strategy="everyn", params={"size": 0}))


def test_register_conflict_and_replace():
    engine = ChunkEngine()
    factory = lambda p, _x: EveryNChunker(p)  # noqa: E731
    with pytest.raises(RegistryConflictError):
        engine.register(
            "sliding_window", factory, params_model=EveryNParams
        )
    engine.register(
        "sliding_window", factory, params_model=EveryNParams, replace=True
    )
    result = engine.execute(
        "abcd", single_level(params={"size": 2})
    )
    assert [c.content for c in result.chunks] == ["ab", "cd"]


# ---- tracing & serialization ----


def test_result_tracing_fields():
    engine = ChunkEngine()
    policy = single_level(params={"chunk_size": 3}, policy_id="p42", version="2.0.1")
    result = engine.execute("abcdef", policy)
    assert result.policy_id == "p42"
    assert result.policy_version == "2.0.1"
    assert result.policy_hash == engine.compile(policy).policy_hash
    assert result.engine_version == chunkweave.__version__
    assert result.execution_time_ms >= 0


def test_execution_id_unique_per_call():
    engine = ChunkEngine()
    policy = single_level(params={"chunk_size": 3})
    r1 = engine.execute("abcdef", policy)
    r2 = engine.execute("abcdef", policy)
    assert r1.execution_id != r2.execution_id


def test_same_input_same_chunks():
    engine = ChunkEngine()
    policy = single_level(params={"chunk_size": 3})
    r1 = engine.execute("abcdefgh", policy)
    r2 = engine.execute("abcdefgh", policy)
    assert [c.model_dump() for c in r1.chunks] == [
        c.model_dump() for c in r2.chunks
    ]


def test_result_serialization_roundtrip():
    engine = ChunkEngine()
    result = engine.execute(
        "ab\ncdef\n\ngh",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 3}},
            ],
            fields={"doc": {"value": "测试"}},
        ),
    )
    payload = result.model_dump_json()
    import json

    assert json.loads(payload)["total"] == len(result.chunks)
    restored = ChunkResult.model_validate_json(payload)
    assert [c.model_dump() for c in restored.chunks] == [
        c.model_dump() for c in result.chunks
    ]
    assert restored.total == result.total
    assert restored.execution_id == result.execution_id


def test_result_dump_ignores_total_on_validate():
    engine = ChunkEngine()
    result = engine.execute("abc", single_level(params={"chunk_size": 3}))
    data = result.model_dump()
    assert data["total"] == 1
    restored = ChunkResult.model_validate(data)
    assert restored.total == 1


def test_compile_returns_plan():
    engine = ChunkEngine()
    plan = engine.compile(single_level(params={"chunk_size": 3}))
    assert isinstance(plan, ExecutionPlan)
    assert plan.levels[0].params == {"chunk_size": 3, "overlap": 0}
