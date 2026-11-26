"""Metadata Builder: value/source resolution, Context rules, include copies."""

import pytest

from chunkweave import ChunkEngine, ContextResolutionError
from conftest import make_policy


def _single(fields, include=None):
    return make_policy(
        [
            {"name": "l0", "strategy": "sliding_window",
             "params": {"chunk_size": 4}},
        ],
        fields=fields,
        include=include,
    )


# ---- value / source generation ----


def test_value_fields_attached_to_every_chunk():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        _single({"src": {"value": "doc1"}, "n": {"value": 3}}),
    )
    assert all(c.metadata["src"] == "doc1" for c in result.chunks)
    assert all(c.metadata["n"] == 3 for c in result.chunks)


def test_source_fields_resolve_from_context():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        _single({"author": {"source": "context.doc.author"}}),
        context={"doc": {"author": "张三"}},
    )
    assert all(c.metadata["author"] == "张三" for c in result.chunks)


def test_source_nested_path():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        _single({"lang": {"source": "context.doc.meta.lang"}}),
        context={"doc": {"meta": {"lang": "zh"}}},
    )
    assert all(c.metadata["lang"] == "zh" for c in result.chunks)


def test_value_null_is_written():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh", _single({"tag": {"value": None}})
    )
    for c in result.chunks:
        assert "tag" in c.metadata
        assert c.metadata["tag"] is None


def test_unreferenced_context_keys_never_appear():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        _single({"author": {"source": "context.doc.author"}}),
        context={"doc": {"author": "x", "secret": "s"}, "other": 1},
    )
    for c in result.chunks:
        assert set(c.metadata) >= {"author"}
        assert "secret" not in c.metadata
        assert "other" not in c.metadata


# ---- Context resolution failures ----


def test_missing_path_raises_with_field_and_path():
    engine = ChunkEngine()
    policy = _single({"author": {"source": "context.doc.author"}})
    with pytest.raises(ContextResolutionError) as exc:
        engine.execute("abcdefgh", policy, context={"doc": {}})
    assert exc.value.field == "author"
    assert exc.value.path == "context.doc.author"
    assert "context.doc.author" in str(exc.value)


def test_none_context_raises():
    engine = ChunkEngine()
    policy = _single({"author": {"source": "context.doc.author"}})
    with pytest.raises(ContextResolutionError) as exc:
        engine.execute("abcdefgh", policy)
    assert exc.value.field == "author"


def test_intermediate_non_mapping_raises():
    engine = ChunkEngine()
    policy = _single({"lang": {"source": "context.doc.meta.lang"}})
    with pytest.raises(ContextResolutionError) as exc:
        engine.execute("abcdefgh", policy, context={"doc": "not a mapping"})
    assert "doc" in str(exc.value)


def test_non_serializable_context_value_raises():
    engine = ChunkEngine()
    policy = _single({"bad": {"source": "context.obj"}})
    with pytest.raises(ContextResolutionError):
        engine.execute("abcdefgh", policy, context={"obj": object()})


def test_context_resolved_even_for_empty_text():
    """Context resolution happens before chunking, empty text included."""
    engine = ChunkEngine()
    policy = _single({"author": {"source": "context.doc.author"}})
    result = engine.execute("", policy, context={"doc": {"author": "x"}})
    assert result.chunks == []
    with pytest.raises(ContextResolutionError):
        engine.execute("", policy)


def test_no_partial_result_on_context_failure():
    engine = ChunkEngine()
    policy = _single({"author": {"source": "context.doc.author"}})
    with pytest.raises(ContextResolutionError):
        engine.execute("abcdefgh", policy)


# ---- independent copies ----


def test_metadata_independent_copies_per_chunk():
    engine = ChunkEngine()
    nested = {"tags": ["x", "y"]}
    result = engine.execute(
        "abcdefgh",
        _single({"info": {"value": nested}, "dyn": {"source": "context.d"}}),
        context={"d": {"list": [1, 2]}},
    )
    assert len(result.chunks) >= 2
    first, second = result.chunks[0], result.chunks[1]
    first.metadata["info"]["tags"].append("MUT")
    first.metadata["dyn"]["list"].append(99)
    assert second.metadata["info"]["tags"] == ["x", "y"]
    assert second.metadata["dyn"]["list"] == [1, 2]
    # declared value / context source untouched
    assert nested == {"tags": ["x", "y"]}


# ---- include copy semantics ----


def test_include_defaults_copy_six_keys():
    engine = ChunkEngine()
    result = engine.execute(
        "aa\n\nbb",
        make_policy(
            [
                {"name": "parent-level", "strategy": "recursive",
                 "params": {"chunk_size": 4, "separators": ["\n\n"]}},
                {"name": "child-level", "strategy": "sliding_window",
                 "params": {"chunk_size": 2}},
            ],
            fields={"kind": {"value": "k"}},
        ),
    )
    for c in result.chunks:
        for key in ("parent_id", "level", "sequence", "level_name",
                    "strategy", "strategy_metadata"):
            assert key in c.metadata
        assert c.metadata["parent_id"] == c.parent_id
        assert c.metadata["level"] == c.level
        assert c.metadata["sequence"] == c.sequence
        assert c.metadata["level_name"] == {0: "parent-level", 1: "child-level"}[c.level]
        assert c.metadata["strategy"] == c.strategy
        assert c.metadata["strategy_metadata"] == c.strategy_metadata
        assert c.metadata["strategy_metadata"] is not c.strategy_metadata
        assert c.metadata["kind"] == "k"


def test_include_organization_off():
    engine = ChunkEngine()
    result = engine.execute(
        "aa\n\nbb",
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 4, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 2}},
            ],
            include={"organization": False},
        ),
    )
    for c in result.chunks:
        for key in ("parent_id", "level", "sequence", "level_name"):
            assert key not in c.metadata
        assert "strategy" in c.metadata
        assert "strategy_metadata" in c.metadata
        # attributes still complete
        assert c.level in (0, 1)
        if c.level == 1:
            assert c.parent_id is not None


def test_include_strategy_off_keeps_attribute():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
            ],
            include={"strategy": False},
        ),
    )
    for c in result.chunks:
        assert "strategy" not in c.metadata
        assert "strategy_metadata" not in c.metadata
        # the Chunk attribute itself still carries the strategy info
        assert c.strategy == "sliding_window"
        assert c.strategy_metadata["window_index"] is not None


def test_chunk_attributes_complete_under_any_include():
    for include in ({"strategy": False, "organization": False},
                    {"strategy": False},
                    {"organization": False}):
        engine = ChunkEngine()
        result = engine.execute(
            "aa\n\nbb",
            make_policy(
                [
                    {"name": "l0", "strategy": "recursive",
                     "params": {"chunk_size": 4, "separators": ["\n\n"]}},
                    {"name": "l1", "strategy": "sliding_window",
                     "params": {"chunk_size": 2}},
                ],
                include=include,
            ),
        )
        for c in result.chunks:
            assert c.strategy in ("recursive", "sliding_window")
            assert c.strategy_metadata  # attribute never emptied
            assert c.level in (0, 1)
            assert isinstance(c.sequence, int)
            if c.level == 0:
                assert c.parent_id is None
            else:
                assert c.parent_id is not None


def test_metadata_key_set_matches_declaration():
    """metadata keys = declared fields + enabled include reserved keys only."""
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
            ],
            fields={"a": {"value": 1}, "b": {"source": "context.b"}},
            include={"organization": False},
            # Context supplies extra keys that must not leak in
        ),
        context={"b": 2, "extra": "x"},
    )
    for c in result.chunks:
        assert set(c.metadata) == {"a", "b", "strategy", "strategy_metadata"}


def test_include_copied_strategy_metadata_is_independent():
    engine = ChunkEngine()
    result = engine.execute(
        "abcdefgh",
        make_policy(
            [
                {"name": "l0", "strategy": "sliding_window",
                 "params": {"chunk_size": 4}},
            ],
        ),
    )
    c0, c1 = result.chunks[0], result.chunks[1]
    c0.metadata["strategy_metadata"]["window_index"] = 999
    assert c0.strategy_metadata["window_index"] == 0
    assert c1.metadata["strategy_metadata"]["window_index"] == 1
