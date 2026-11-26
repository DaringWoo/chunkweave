"""Organization: single/multi-level descent, parent-child, offsets, edges."""

import itertools

import pytest
from pydantic import BaseModel, ConfigDict

from chunkweave import ChunkEngine, ChunkSpan, PolicyValidationError
from conftest import FakeProvider, make_policy


class NoParams(BaseModel):
    """Params schema for test chunkers: no keys allowed."""

    model_config = ConfigDict(extra="forbid")


def two_level_policy():
    return make_policy(
        [
            {"name": "l0", "strategy": "recursive",
             "params": {"chunk_size": 10, "separators": ["\n\n"]}},
            {"name": "l1", "strategy": "sliding_window", "params": {"chunk_size": 3}},
        ]
    )


# ---- single level ----


def test_single_level_sliding_window():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefghij",
        make_policy([
            {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 4}}
        ]),
    )
    assert [c.content for c in result.chunks] == ["abcd", "efgh", "ij"]


def test_single_level_recursive():
    engine = ChunkEngine()
    result = engine.execute(
        "a。b。c。",
        make_policy([
            {"name": "l0", "strategy": "recursive",
             "params": {"chunk_size": 4, "separators": ["。"]}}
        ]),
    )
    assert [c.content for c in result.chunks] == ["a。b。", "c。"]


def test_single_level_semantic():
    engine = ChunkEngine()
    result = engine.execute(
        "苹果。香蕉。",
        make_policy([
            {"name": "l0", "strategy": "semantic",
             "params": {"threshold": 0.5, "chunk_size": 10,
                        "unit_separators": ["。"]}}
        ]),
        provider=FakeProvider({("苹果。", "香蕉。"): 0.1}),
    )
    assert [c.content for c in result.chunks] == ["苹果。", "香蕉。"]


def test_single_level_root_fields():
    engine = ChunkEngine()
    result = engine.execute(
        "a。b。",
        make_policy([
            {"name": "l0", "strategy": "recursive",
             "params": {"chunk_size": 3, "separators": ["。"]}}
        ]),
    )
    for i, c in enumerate(result.chunks):
        assert c.parent_id is None
        assert c.level == 0
        assert c.sequence == i
        assert c.strategy == "recursive"


def test_single_level_output_in_order():
    engine = ChunkEngine()
    result = engine.execute(
        "x" * 25,
        make_policy([
            {"name": "l0", "strategy": "sliding_window", "params": {"chunk_size": 5}}
        ]),
    )
    starts = [c.start_offset for c in result.chunks]
    assert starts == sorted(starts)


# ---- two levels ----


def test_two_level_parent_child():
    engine = ChunkEngine()
    text = "ab\ncdef\n\ngh"
    result = engine.execute(text, two_level_policy())
    level0 = [c for c in result.chunks if c.level == 0]
    level1 = [c for c in result.chunks if c.level == 1]
    assert len(level0) == 2
    by_parent: dict[str | None, list] = {}
    for c in level1:
        by_parent.setdefault(c.parent_id, []).append(c)
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
            assert child.level == 1
    for parent in level0:
        seqs = [c.sequence for c in by_parent[parent.chunk_id]]
        assert seqs == list(range(len(seqs)))


def test_root_fields():
    engine = ChunkEngine()
    result = engine.execute("aa\n\nbb", two_level_policy())
    for c in result.chunks:
        if c.level == 0:
            assert c.parent_id is None
        else:
            assert c.parent_id is not None


def test_three_levels_different_strategies():
    engine = ChunkEngine()
    text = "章节A一。甲。章节B二。乙。"
    result = engine.execute(
        text,
        make_policy(
            [
                {"name": "chapter", "strategy": "recursive",
                 "params": {"chunk_size": 12, "separators": ["章节"]}},
                {"name": "event", "strategy": "semantic",
                 "params": {"threshold": 0.5, "chunk_size": 6,
                            "unit_separators": ["。"]}},
                {"name": "detail", "strategy": "sliding_window",
                 "params": {"chunk_size": 2}},
            ]
        ),
        provider=FakeProvider(),
    )
    levels = {c.level for c in result.chunks}
    assert levels == {0, 1, 2}
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in result.chunks:
        if c.level > 0:
            parent = by_id[c.parent_id]
            assert parent.level == c.level - 1
            assert parent.start_offset <= c.start_offset
            assert c.end_offset <= parent.end_offset
            assert c.strategy == {
                1: "semantic",
                2: "sliding_window",
            }[c.level]


def test_level_name_copied_into_metadata():
    engine = ChunkEngine()
    result = engine.execute(
        "aa\n\nbb",
        make_policy(
            [
                {"name": "chapter", "strategy": "recursive",
                 "params": {"chunk_size": 4, "separators": ["\n\n"]}},
                {"name": "piece", "strategy": "sliding_window",
                 "params": {"chunk_size": 50}},
            ]
        ),
    )
    for c in result.chunks:
        assert c.metadata["level_name"] == {0: "chapter", 1: "piece"}[c.level]


def test_local_to_global_offset_conversion():
    engine = ChunkEngine()
    text = "A" * 1000 + "B" * 1000
    result = engine.execute(
        text,
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 1000}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 300, "overlap": 50}},
            ]
        ),
    )
    for c in result.chunks:
        assert c.content == text[c.start_offset : c.end_offset]


def test_children_never_cross_parent_boundary():
    engine = ChunkEngine()
    text = "段落一内容。\n\n段落二内容更多一些。\n\n段三。"
    result = engine.execute(
        text,
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
            ]
        ),
    )
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in result.chunks:
        if c.level == 1:
            parent = by_id[c.parent_id]
            assert c.start_offset >= parent.start_offset
            assert c.end_offset <= parent.end_offset


def test_parent_overlap_duplicate_coverage_allowed():
    engine = ChunkEngine()
    text = "a" * 20
    result = engine.execute(
        text,
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 10, "overlap": 4}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 5}},
            ]
        ),
    )
    level0 = [c for c in result.chunks if c.level == 0]
    assert len(level0) >= 2
    level1 = [c for c in result.chunks if c.level == 1]
    ranges = [(c.start_offset, c.end_offset, c.parent_id) for c in level1]
    overlap_found = any(
        a[:2] != b[:2] and a[2] != b[2] and a[0] < b[1] and b[0] < a[1]
        for a in ranges
        for b in ranges
    )
    assert overlap_found
    for c in result.chunks:
        assert c.content == text[c.start_offset : c.end_offset]


# ---- edges ----


def test_empty_input():
    engine = ChunkEngine()
    result = engine.execute("", two_level_policy())
    assert result.chunks == []
    assert result.total == 0


def test_empty_levels_rejected_at_load():
    import yaml

    from chunkweave import Policy, PolicyValidationError

    with pytest.raises(PolicyValidationError):
        Policy.from_yaml(
            yaml.safe_dump(
                {
                    "api_version": "chunkweave/v1",
                    "policy": {"id": "p", "name": "n", "version": "1.0.0"},
                    "pipeline": {"levels": []},
                }
            )
        )


def test_single_level_pipeline_is_flat():
    engine = ChunkEngine()
    result = engine.execute(
        "a。b。",
        make_policy([
            {"name": "only", "strategy": "recursive",
             "params": {"chunk_size": 3, "separators": ["。"]}}
        ]),
    )
    assert all(c.level == 0 for c in result.chunks)
    assert all(c.parent_id is None for c in result.chunks)


def test_level_with_no_results_terminates_branch():
    class EmptyChunker:
        def chunk(self, text):
            return []

    engine = ChunkEngine()
    engine.register(
        "empty",
        lambda params, _provider: EmptyChunker(),
        params_model=NoParams,
    )
    result = engine.execute(
        "aaaa\n\nbbbb",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 6, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "empty"},
            ]
        ),
    )
    level0 = [c for c in result.chunks if c.level == 0]
    level1 = [c for c in result.chunks if c.level == 1]
    assert len(level0) == 2
    assert level1 == []  # every parent produced no children -> branch ends


def test_unsplittable_chunk_has_one_equal_child():
    engine = ChunkEngine()
    result = engine.execute(
        "aa\n\nbb",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 4, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 50}},
            ]
        ),
    )
    level1 = [c for c in result.chunks if c.level == 1]
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in level1:
        parent = by_id[c.parent_id]
        assert c.content == parent.content
        assert (c.start_offset, c.end_offset) == (
            parent.start_offset,
            parent.end_offset,
        )


def test_no_infinite_loop_degenerate_input():
    engine = ChunkEngine()
    result = engine.execute(
        "x" * 100,
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 1}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 1}},
            ]
        ),
    )
    assert len(result.chunks) == 200  # 100 parents + 100 children


def test_empty_spans_are_dropped():
    """A strategy producing empty-content spans yields no empty chunks."""

    class EmptyEmittingChunker:
        def chunk(self, text):
            return [
                ChunkSpan(content="", start_offset=0, end_offset=0),
                ChunkSpan(content=text[:2], start_offset=0, end_offset=2),
                ChunkSpan(content="", start_offset=2, end_offset=2),
            ]

    engine = ChunkEngine()
    engine.register(
        "empty_emitting",
        lambda params, _provider: EmptyEmittingChunker(),
        params_model=NoParams,
    )
    result = engine.execute(
        "abcd",
        make_policy([
            {"name": "l0", "strategy": "empty_emitting"},
        ]),
    )
    assert len(result.chunks) == 1
    assert result.chunks[0].content == "ab"
    assert result.chunks[0].chunk_id == "chunk-0000"  # numbering skips drops
    assert result.chunks[0].sequence == 0


def test_result_sorted_parents_before_children_at_same_start():
    """At equal start_offset a parent chunk precedes its children."""
    engine = ChunkEngine()
    result = engine.execute(
        "abcd",
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
            ]
        ),
    )
    starts = [c.start_offset for c in result.chunks]
    assert starts == sorted(starts)
    for a, b in itertools.pairwise(result.chunks):
        if a.start_offset == b.start_offset:
            assert a.level <= b.level


def test_chunk_ids_breadth_first_sequential():
    engine = ChunkEngine()
    result = engine.execute("aa\n\nbb", two_level_policy())
    ids = [c.chunk_id for c in result.chunks]
    assert len(ids) == len(set(ids))
    assert all(id_.startswith("chunk-") for id_ in ids)


def test_unregistered_strategy_in_level():
    engine = ChunkEngine()
    with pytest.raises(PolicyValidationError) as exc:
        engine.execute(
            "abc",
            make_policy([
                {"name": "l0", "strategy": "nope"},
            ]),
        )
    assert "nope" in str(exc.value)
