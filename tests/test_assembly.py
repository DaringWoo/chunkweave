"""Metadata assembly: four groups, inheritance, reserved-field rejection."""

import pytest

from chunkweave import ChunkEngine, MetadataConflictError
from chunkweave.assembly import custom_for_level, validate_custom_across_levels


def _hier_config(**over):
    cfg = {
        "organization": "hierarchical",
        "levels": [
            {"strategy": "recursive", "config": {"chunk_size": 10, "separators": ["\n\n"]}},
            {"strategy": "sliding_window", "config": {"chunk_size": 3}},
        ],
    }
    cfg.update(over)
    return cfg


def test_four_groups_kept_separate():
    engine = ChunkEngine()
    result = engine.chunk(
        "ab\n\ncdef\n\ngh",
        _hier_config(
            custom={"doc": "x"},
            levels=[
                {
                    "strategy": "recursive",
                    "config": {"chunk_size": 10, "separators": ["\n\n"]},
                    "metadata": {"layer": "chapter"},
                },
                {"strategy": "sliding_window", "config": {"chunk_size": 3}},
            ],
        ),
    )
    chunk = result.chunks[0]
    assert chunk.chunk_id and chunk.content and chunk.start_offset >= 0
    assert set(chunk.metadata.organization) == {"parent_id", "level", "sequence"}
    assert chunk.metadata.strategy  # separator_used etc.
    assert chunk.metadata.custom["doc"] == "x"


def test_engine_custom_propagates_to_all_descendants():
    engine = ChunkEngine()
    result = engine.chunk("aa\n\nbb\n\ncc", _hier_config(custom={"tenant": "t1"}))
    assert result.chunks
    for c in result.chunks:
        assert c.metadata.custom["tenant"] == "t1"
    # mutate one chunk's copy: nobody else changes
    result.chunks[0].metadata.custom["tenant"] = "MUT"
    assert all(
        c.metadata.custom["tenant"] == "t1" for c in result.chunks[1:]
    )


def test_level_metadata_nearest_wins():
    engine = ChunkEngine()
    result = engine.chunk(
        "aa\n\nbb\n\ncc",
        _hier_config(
            custom={"who": "engine", "shared": "engine"},
            levels=[
                {
                    "strategy": "recursive",
                    "config": {"chunk_size": 10, "separators": ["\n\n"]},
                    "metadata": {"who": "level0", "shared": "level0"},
                },
                {
                    "strategy": "sliding_window",
                    "config": {"chunk_size": 3},
                    "metadata": {"shared": "level1"},
                },
            ],
        ),
    )
    level0 = [c for c in result.chunks if c.metadata.organization["level"] == 0]
    level1 = [c for c in result.chunks if c.metadata.organization["level"] == 1]
    assert level0 and level1
    for c in level0:
        assert c.metadata.custom == {
            "who": "level0",
            "shared": "level0",
        }
    for c in level1:
        # inherits engine + level0, overridden by its own level
        assert c.metadata.custom == {
            "who": "level0",
            "shared": "level1",
        }


def test_reserved_conflict_rejected_at_config_time():
    engine = ChunkEngine()
    with pytest.raises(MetadataConflictError):
        engine.chunk("aa\n\nbb", _hier_config(custom={"level": 9}))
    with pytest.raises(MetadataConflictError):
        engine.chunk(
            "aa\n\nbb",
            _hier_config(
                levels=[
                    {
                        "strategy": "recursive",
                        "config": {"chunk_size": 10},
                        "metadata": {"separator_used": "boom"},
                    },
                    {"strategy": "sliding_window", "config": {"chunk_size": 3}},
                ]
            ),
        )
    # level-1 strategy key colliding via inheritance
    with pytest.raises(MetadataConflictError):
        engine.chunk(
            "aa\n\nbb",
            _hier_config(
                levels=[
                    {
                        "strategy": "recursive",
                        "config": {"chunk_size": 10},
                        "metadata": {"window_index": 0},
                    },
                    {"strategy": "sliding_window", "config": {"chunk_size": 3}},
                ]
            ),
        )


def test_custom_for_level_ordering():
    merged = custom_for_level(
        {"a": 1, "b": 1},
        [{"b": 2, "c": 2}, {"b": 3, "d": 3}],
        level=1,
    )
    assert merged == {"a": 1, "b": 3, "c": 2, "d": 3}


def test_validate_across_levels():
    # ok case
    validate_custom_across_levels({"x": 1}, [{"y": 2}, {}], [frozenset(), frozenset()])
    with pytest.raises(MetadataConflictError):
        validate_custom_across_levels(
            {"window_index": 1}, [{}], [frozenset({"window_index"})]
        )
