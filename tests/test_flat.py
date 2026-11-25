"""Flat organization: sibling output, all three strategies, no org fields."""

import pytest

from chunkweave import ChunkEngine


class FakeProvider:
    def score(self, left: str, right: str) -> float:
        return 0.9 if left[0] == right[0] else 0.1


def flat_cfg(strategy, config, custom=None):
    cfg = {"organization": "flat", "strategy": strategy, "config": config}
    if custom:
        cfg["custom"] = custom
    return cfg


def test_flat_sliding_window():
    engine = ChunkEngine()
    result = engine.chunk("abcdefghij", flat_cfg("sliding_window", {"chunk_size": 4}))
    assert [c.content for c in result.chunks] == ["abcd", "efgh", "ij"]
    for c in result.chunks:
        assert c.metadata.organization == {}


def test_flat_recursive():
    engine = ChunkEngine()
    result = engine.chunk(
        "a。b。c。", flat_cfg("recursive", {"chunk_size": 4, "separators": ["。"]})
    )
    assert [c.content for c in result.chunks] == ["a。b。", "c。"]
    for c in result.chunks:
        assert c.metadata.organization == {}


def test_flat_semantic_with_provider():
    engine = ChunkEngine()
    engine.set_provider(FakeProvider())
    result = engine.chunk(
        "苹果。香蕉。",
        flat_cfg("semantic", {"threshold": 0.5, "chunk_size": 10, "unit_separators": ["。"]}),
    )
    assert [c.content for c in result.chunks] == ["苹果。", "香蕉。"]


def test_flat_semantic_needs_provider():
    engine = ChunkEngine()
    from chunkweave import ProviderMissingError

    with pytest.raises(ProviderMissingError):
        engine.chunk(
            "a。b。", flat_cfg("semantic", {"threshold": 0.5, "chunk_size": 10})
        )


def test_flat_custom_metadata_attached():
    engine = ChunkEngine()
    result = engine.chunk(
        "abcdef", flat_cfg("sliding_window", {"chunk_size": 3}, custom={"src": "doc1"})
    )
    assert all(c.metadata.custom == {"src": "doc1"} for c in result.chunks)
    assert all(c.metadata.organization == {} for c in result.chunks)


def test_flat_output_in_order():
    engine = ChunkEngine()
    result = engine.chunk("x" * 25, flat_cfg("sliding_window", {"chunk_size": 5}))
    starts = [c.start_offset for c in result.chunks]
    assert starts == sorted(starts)
