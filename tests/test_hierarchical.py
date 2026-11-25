"""Hierarchical organization: levels, parent-child, offsets, edges."""

import pytest

from chunkweave import ChunkEngine, ConfigError


class FakeProvider:
    def score(self, left: str, right: str) -> float:
        return 0.9 if left[0] == right[0] else 0.1


def two_level_cfg():
    return {
        "organization": "hierarchical",
        "levels": [
            {
                "strategy": "recursive",
                "config": {"chunk_size": 10, "separators": ["\n\n"]},
            },
            {"strategy": "sliding_window", "config": {"chunk_size": 3}},
        ],
    }


def test_two_level_parent_child():
    engine = ChunkEngine()
    text = "ab\ncdef\n\ngh"
    result = engine.chunk(text, two_level_cfg())
    level0 = [c for c in result.chunks if c.metadata.organization["level"] == 0]
    level1 = [c for c in result.chunks if c.metadata.organization["level"] == 1]
    # level0: "\n\n" splits -> [0,8) "ab\ncdef\n\n"? check
    assert len(level0) == 2
    by_parent = {}
    for c in level1:
        by_parent.setdefault(c.metadata.organization["parent_id"], []).append(c)
    assert set(by_parent) == {c.chunk_id for c in level0}
    for parent in level0:
        for child in by_parent[parent.chunk_id]:
            assert (
                parent.start_offset
                <= child.start_offset
                < child.end_offset
                <= parent.end_offset
            )
            assert child.content == text[child.start_offset : child.end_offset]
            assert child.metadata.organization["level"] == 1
    # sequence numbering within each parent
    for parent in level0:
        seqs = [
            c.metadata.organization["sequence"]
            for c in by_parent[parent.chunk_id]
        ]
        assert seqs == list(range(len(seqs)))


def test_root_fields():
    engine = ChunkEngine()
    result = engine.chunk("aa\n\nbb", two_level_cfg())
    for c in result.chunks:
        org = c.metadata.organization
        if org["level"] == 0:
            assert org["parent_id"] is None
        else:
            assert org["parent_id"] is not None


def test_three_levels_different_strategies():
    engine = ChunkEngine()
    engine.set_provider(FakeProvider())
    text = "章节A一。甲。章节B二。乙。"
    result = engine.chunk(
        text,
        {
            "organization": "hierarchical",
            "levels": [
                {
                    "strategy": "recursive",
                    "config": {"chunk_size": 12, "separators": ["章节"]},
                    "name": "chapter",
                },
                {
                    "strategy": "semantic",
                    "config": {"threshold": 0.5, "chunk_size": 6, "unit_separators": ["。"]},
                    "name": "event",
                },
                {
                    "strategy": "sliding_window",
                    "config": {"chunk_size": 2},
                    "name": "detail",
                },
            ],
        },
    )
    levels = {c.metadata.organization["level"] for c in result.chunks}
    assert levels == {0, 1, 2}
    # every non-root parent_id resolves to a chunk one level up
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in result.chunks:
        org = c.metadata.organization
        if org["level"] > 0:
            parent = by_id[org["parent_id"]]
            assert parent.metadata.organization["level"] == org["level"] - 1
            assert parent.start_offset <= c.start_offset
            assert c.end_offset <= parent.end_offset


def test_local_to_global_offset_conversion():
    engine = ChunkEngine()
    text = "A" * 1000 + "B" * 1000
    result = engine.chunk(
        text,
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "sliding_window", "config": {"chunk_size": 1000}},
                {"strategy": "sliding_window", "config": {"chunk_size": 300, "overlap": 50}},
            ],
        },
    )
    for c in result.chunks:
        assert c.content == text[c.start_offset : c.end_offset]


def test_children_never_cross_parent_boundary():
    engine = ChunkEngine()
    text = "段落一内容。\n\n段落二内容更多一些。\n\n段三。"
    result = engine.chunk(
        text,
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"strategy": "sliding_window", "config": {"chunk_size": 4}},
            ],
        },
    )
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in result.chunks:
        org = c.metadata.organization
        if org["level"] == 1:
            parent = by_id[org["parent_id"]]
            assert c.start_offset >= parent.start_offset
            assert c.end_offset <= parent.end_offset


def test_parent_overlap_duplicate_coverage_allowed():
    engine = ChunkEngine()
    text = "a" * 20
    result = engine.chunk(
        text,
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "sliding_window", "config": {"chunk_size": 10, "overlap": 4}},
                {"strategy": "sliding_window", "config": {"chunk_size": 5}},
            ],
        },
    )
    level0 = [c for c in result.chunks if c.metadata.organization["level"] == 0]
    assert len(level0) >= 2
    level1 = [c for c in result.chunks if c.metadata.organization["level"] == 1]
    # children of different overlapping parents may cover the same text range
    ranges = [(c.start_offset, c.end_offset, c.metadata.organization["parent_id"]) for c in level1]
    overlap_found = any(
        a[:2] != b[:2] and a[2] != b[2] and a[0] < b[1] and b[0] < a[1]
        for a in ranges
        for b in ranges
    )
    assert overlap_found
    for c in result.chunks:
        assert c.content == text[c.start_offset : c.end_offset]


def test_empty_input():
    engine = ChunkEngine()
    result = engine.chunk("", two_level_cfg())
    assert result.chunks == []
    assert result.tree() == []


def test_empty_levels_rejected():
    engine = ChunkEngine()
    with pytest.raises(ConfigError):
        engine.chunk("text", {"organization": "hierarchical", "levels": []})


def test_single_level_hierarchical():
    engine = ChunkEngine()
    result = engine.chunk(
        "a。b。",
        {
            "organization": "hierarchical",
            "levels": [
                {
                    "strategy": "recursive",
                    "config": {"chunk_size": 3, "separators": ["。"]},
                }
            ],
        },
    )
    assert all(c.metadata.organization["level"] == 0 for c in result.chunks)
    assert all(c.metadata.organization["parent_id"] is None for c in result.chunks)


def test_level_with_no_results_terminates_branch():
    engine = ChunkEngine()
    # a custom strategy that returns nothing for inputs containing "empty"
    from typing import ClassVar

    class EmptyForSome:
        metadata_keys: ClassVar[frozenset[str]] = frozenset()

        def __init__(self, config):
            pass

        def chunk(self, text):
            return []

    engine.register("empty", lambda cfg: EmptyForSome(cfg))
    result = engine.chunk(
        "aaaa\n\nbbbb",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 6, "separators": ["\n\n"]}},
                {"strategy": "empty", "config": {}},
            ],
        },
    )
    level0 = [c for c in result.chunks if c.metadata.organization["level"] == 0]
    level1 = [c for c in result.chunks if c.metadata.organization["level"] == 1]
    assert len(level0) == 2
    assert level1 == []  # every parent produced no children -> branch ends
    assert result.tree()  # roots exist


def test_unsplittable_chunk_has_no_children():
    engine = ChunkEngine()
    # level 1 sliding window of size 50 on parents of size <= 10: each parent
    # yields exactly one child equal to itself.
    result = engine.chunk(
        "aa\n\nbb",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "recursive", "config": {"chunk_size": 4, "separators": ["\n\n"]}},
                {"strategy": "sliding_window", "config": {"chunk_size": 50}},
            ],
        },
    )
    level1 = [c for c in result.chunks if c.metadata.organization["level"] == 1]
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in level1:
        parent = by_id[c.metadata.organization["parent_id"]]
        assert c.content == parent.content
        assert (c.start_offset, c.end_offset) == (parent.start_offset, parent.end_offset)


def test_no_infinite_loop_degenerate_input():
    engine = ChunkEngine()
    result = engine.chunk(
        "x" * 100,
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "sliding_window", "config": {"chunk_size": 1}},
                {"strategy": "sliding_window", "config": {"chunk_size": 1}},
            ],
        },
    )
    assert len(result.chunks) == 200  # 100 parents + 100 children
