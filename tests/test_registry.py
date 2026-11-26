"""Registry: builtins, custom chunkers, conflicts, boundary."""

import pytest
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from chunkweave import (
    Chunker,
    RecursiveChunker,
    RecursiveParams,
    Registry,
    RegistryConflictError,
    SemanticChunker,
    SemanticParams,
    SlidingWindowChunker,
    SlidingWindowParams,
    UnregisteredStrategyError,
)


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UnitParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: StrictInt = Field(default=5, gt=0)


def test_builtin_strategies_registered():
    reg = Registry()
    assert set(reg.names()) == {"sliding_window", "recursive", "semantic"}
    sw = reg.get("sliding_window")
    assert sw.factory(sw.params_model.model_validate({"chunk_size": 4}), None)
    assert isinstance(
        sw.factory(sw.params_model.model_validate({"chunk_size": 4}), None),
        SlidingWindowChunker,
    )
    rec = reg.get("recursive")
    assert isinstance(
        rec.factory(rec.params_model.model_validate({"chunk_size": 4}), None),
        RecursiveChunker,
    )
    sem = reg.get("semantic")
    assert sem.requires_provider is True
    provider = object()
    assert isinstance(
        sem.factory(sem.params_model.model_validate({"threshold": 0.5, "chunk_size": 4}), provider),
        SemanticChunker,
    )


def test_builtin_specs_declare_params_model():
    reg = Registry()
    assert reg.get("sliding_window").params_model is SlidingWindowParams
    assert reg.get("recursive").params_model is RecursiveParams
    assert reg.get("semantic").params_model is SemanticParams
    assert reg.get("sliding_window").requires_provider is False


def test_unregistered_name_raises_with_name():
    reg = Registry()
    with pytest.raises(UnregisteredStrategyError) as exc:
        reg.get("does_not_exist")
    assert "does_not_exist" in str(exc.value)
    assert exc.value.name == "does_not_exist"


def test_duplicate_register_rejected_and_preserved():
    reg = Registry()
    original = reg.get("sliding_window")
    with pytest.raises(RegistryConflictError):
        reg.register(
            "sliding_window",
            lambda p, _x: original.factory(p, _x),
            params_model=NoParams,
        )
    assert reg.get("sliding_window") is original


def test_explicit_replace_wins():
    reg = Registry()
    marker = object()

    def factory(params, provider):
        return marker

    reg.register("recursive", factory, params_model=NoParams, replace=True)
    assert reg.get("recursive").factory(None, None) is marker


class ReverseChunker:
    """Third-party chunker conforming to the Chunker protocol."""

    def __init__(self, params):
        self.unit = params.unit

    def chunk(self, text: str):
        from chunkweave import ChunkSpan

        return [
            ChunkSpan(
                content=text[s : s + self.unit][::-1],
                start_offset=s,
                end_offset=min(s + self.unit, len(text)),
                strategy_metadata={"rev": i},
            )
            for i, s in enumerate(range(0, len(text), self.unit))
        ]


def test_custom_chunker_registers_and_chunks():
    reg = Registry()
    reg.register(
        "reverse",
        lambda params, _p: ReverseChunker(params),
        params_model=UnitParams,
    )
    spec = reg.get("reverse")
    chunker = spec.factory(spec.params_model.model_validate({"unit": 3}), None)
    spans = chunker.chunk("abcdefg")
    assert [s.content for s in spans] == ["cba", "fed", "g"]
    assert all(s.strategy_metadata.get("rev") is not None for s in spans)


def test_custom_chunker_conforms_to_protocol():
    assert isinstance(ReverseChunker(UnitParams()), Chunker)


def test_builtin_chunkers_conform_to_protocol():
    reg = Registry()
    raw_params = {
        "sliding_window": {"chunk_size": 5},
        "recursive": {"chunk_size": 5},
        "semantic": {"chunk_size": 5, "threshold": 0.5},
    }
    for name in reg.names():
        spec = reg.get(name)
        chunker = spec.factory(
            spec.params_model.model_validate(raw_params[name]),
            object() if spec.requires_provider else None,
        )
        assert isinstance(chunker, Chunker)


def test_registry_has_no_extra_duties():
    reg = Registry()
    public = [a for a in dir(reg) if not a.startswith("_")]
    assert set(public) == {"register", "get", "names"}
