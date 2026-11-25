"""ChunkEngine public API: execution, registration, views, serialization."""

from collections.abc import Sequence
from typing import ClassVar

import pytest

from chunkweave import (
    Chunk,
    ChunkEngine,
    ChunkNode,
    ChunkResult,
    FlatConfig,
    HierarchicalConfig,
    LevelConfig,
    ProviderMissingError,
    UnregisteredStrategyError,
)


class FakeProvider:
    def score(self, left: str, right: str) -> float:
        return 0.9 if left[0] == right[0] else 0.1


class Every2Chunker:
    """Custom chunker: fixed 2-code-point pieces."""

    metadata_keys: ClassVar[frozenset[str]] = frozenset({"half"})

    def __init__(self, config):
        self.size = config.get("size", 2)

    def chunk(self, text: str) -> Sequence[Chunk]:
        from chunkweave.models import ChunkMetadata, chunk_id_for

        return [
            Chunk(
                chunk_id=chunk_id_for(i),
                content=text[s : s + self.size],
                start_offset=s,
                end_offset=min(s + self.size, len(text)),
                metadata=ChunkMetadata(strategy={"half": i}),
            )
            for i, s in enumerate(range(0, len(text), self.size))
        ]


def test_engine_flat_one_call():
    engine = ChunkEngine()
    result = engine.chunk(
        "abcdefgh",
        {"organization": "flat", "strategy": "sliding_window", "config": {"chunk_size": 3}},
    )
    assert isinstance(result, ChunkResult)
    assert [c.content for c in result.chunks] == ["abc", "def", "gh"]


def test_engine_hierarchical_one_call():
    engine = ChunkEngine()
    result = engine.chunk(
        "ab\ncdef\n\ngh",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"strategy": "sliding_window", "config": {"chunk_size": 3}},
            ],
        },
    )
    assert len(result.chunks) == 6
    assert all("level" in c.metadata.organization for c in result.chunks)


def test_engine_accepts_config_objects():
    engine = ChunkEngine()
    flat = FlatConfig(strategy="sliding_window", config={"chunk_size": 2})
    r1 = engine.chunk("abcd", flat)
    assert len(r1.chunks) == 2
    hier = HierarchicalConfig(
        levels=[LevelConfig(strategy="sliding_window", config={"chunk_size": 2})]
    )
    r2 = engine.chunk("abcd", hier)
    assert all(c.metadata.organization["level"] == 0 for c in r2.chunks)


def test_unregistered_strategy_surfaces_error():
    engine = ChunkEngine()
    with pytest.raises(UnregisteredStrategyError) as exc:
        engine.chunk("abc", {"organization": "flat", "strategy": "nope", "config": {}})
    assert "nope" in str(exc.value)
    with pytest.raises(UnregisteredStrategyError):
        engine.chunk(
            "abc",
            {
                "organization": "hierarchical",
                "levels": [{"strategy": "nope", "config": {}}],
            },
        )


def test_semantic_without_provider_surfaces_error():
    engine = ChunkEngine()
    with pytest.raises(ProviderMissingError):
        engine.chunk(
            "a。b。",
            {
                "organization": "flat",
                "strategy": "semantic",
                "config": {"threshold": 0.5, "chunk_size": 10},
            },
        )


def test_provider_override_per_call():
    engine = ChunkEngine()
    result = engine.chunk(
        "苹果。香蕉。",
        {
            "organization": "flat",
            "strategy": "semantic",
            "config": {"threshold": 0.5, "chunk_size": 10},
            "provider": FakeProvider(),
        },
    )
    assert len(result.chunks) == 2


def test_register_custom_chunker_used_at_any_level():
    engine = ChunkEngine()
    engine.register("every2", lambda cfg: Every2Chunker(cfg))
    flat = engine.chunk(
        "abcdef",
        {"organization": "flat", "strategy": "every2", "config": {"size": 2}},
    )
    assert [c.content for c in flat.chunks] == ["ab", "cd", "ef"]
    hier = engine.chunk(
        "abcd\n\nefgh",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 6, "separators": ["\n\n"]}},
                {"strategy": "every2", "config": {"size": 3}},
            ],
        },
    )
    level1 = [c for c in hier.chunks if c.metadata.organization["level"] == 1]
    assert level1
    assert all(c.metadata.strategy.get("half") is not None for c in level1)


def test_flat_chunks_sorted_by_offset():
    engine = ChunkEngine()
    result = engine.chunk(
        "z" * 20,
        {"organization": "flat", "strategy": "sliding_window", "config": {"chunk_size": 6}},
    )
    starts = [c.start_offset for c in result.chunks]
    assert starts == sorted(starts)


def test_tree_view_matches_parent_id():
    engine = ChunkEngine()
    result = engine.chunk(
        "ab\ncdef\n\ngh",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"strategy": "sliding_window", "config": {"chunk_size": 3}},
            ],
        },
    )
    roots = result.tree()
    assert all(isinstance(n, ChunkNode) for n in roots)
    assert len(roots) == 2
    by_id = {c.chunk_id: c for c in result.chunks}
    seen = set()

    def walk(node):
        seen.add(node.chunk.chunk_id)
        for child in node.children:
            assert child.chunk.metadata.organization["parent_id"] == node.chunk.chunk_id
            walk(child)

    for root in roots:
        walk(root)
    assert seen == set(by_id)


def test_result_serialization_roundtrip():
    engine = ChunkEngine()
    result = engine.chunk(
        "ab\ncdef\n\ngh",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"strategy": "sliding_window", "config": {"chunk_size": 3}},
            ],
            "custom": {"doc": "测试"},
        },
    )
    payload = result.to_json()
    restored = ChunkResult.from_json(payload)
    assert [c.to_dict() for c in restored.chunks] == [c.to_dict() for c in result.chunks]
    # tree rebuilt from restored
    def shape(node):
        return (node.chunk.chunk_id, [shape(c) for c in node.children])

    assert [shape(n) for n in restored.tree()] == [shape(n) for n in result.tree()]


def test_result_serialization_stable():
    engine = ChunkEngine()
    cfg = {"organization": "flat", "strategy": "sliding_window", "config": {"chunk_size": 3}}
    assert engine.chunk("abcdef", cfg).to_json() == engine.chunk("abcdef", cfg).to_json()


def test_config_serialization_roundtrip():
    from chunkweave import engine_config_from_dict

    raw = {
        "organization": "hierarchical",
        "levels": [
            {"strategy": "recursive", "config": {"chunk_size": 50}, "name": "l0"},
            {"strategy": "semantic", "config": {"threshold": 0.7, "chunk_size": 20}},
        ],
        "custom": {"a": 1},
    }
    cfg = engine_config_from_dict(raw)
    assert cfg.to_dict() == raw
