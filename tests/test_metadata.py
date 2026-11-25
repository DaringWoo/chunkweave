"""Four-group metadata rules, reserved fields, custom attach semantics."""

import pytest

from chunkweave import (
    Chunk,
    ChunkMetadata,
    ConfigError,
    MetadataConflictError,
    attach_custom_metadata,
    reserved_field_names,
)


def _chunk(content="abc", start=0, end=3):
    return Chunk(chunk_id=f"c{start}", content=content, start_offset=start, end_offset=end)


def test_reserved_fields_union():
    reserved = reserved_field_names({"window_index"})
    for key in ("chunk_id", "content", "start_offset", "end_offset"):
        assert key in reserved
    for key in ("parent_id", "level", "sequence"):
        assert key in reserved
    assert "window_index" in reserved
    assert "unrelated" not in reserved


def test_reserved_conflict_rejected():
    chunks = [_chunk()]
    with pytest.raises(MetadataConflictError):
        attach_custom_metadata(chunks, {"chunk_id": "boom"})
    with pytest.raises(MetadataConflictError):
        attach_custom_metadata(chunks, {"level": 2})
    with pytest.raises(MetadataConflictError):
        attach_custom_metadata(chunks, {"window_index": 1}, strategy_keys={"window_index"})


def test_custom_metadata_independent_copies():
    custom = {"tags": ["x", "y"], "nested": {"a": [1, 2]}}
    chunks = [_chunk("a", 0, 1), _chunk("b", 1, 2)]
    out = attach_custom_metadata(chunks, custom)
    assert len(out) == 2
    out[0].metadata.custom["tags"].append("MUT")
    out[0].metadata.custom["nested"]["a"].append(99)
    assert out[1].metadata.custom["tags"] == ["x", "y"]
    assert out[1].metadata.custom["nested"]["a"] == [1, 2]
    # original custom mapping untouched
    assert custom == {"tags": ["x", "y"], "nested": {"a": [1, 2]}}


def test_attach_returns_new_list_and_chunks():
    chunks = [_chunk()]
    out = attach_custom_metadata(chunks, {"k": "v"})
    assert out is not chunks
    assert out[0] is not chunks[0]
    assert chunks[0].metadata.custom == {}
    assert out[0].metadata.custom == {"k": "v"}


def test_attach_merges_with_existing_custom():
    chunk = _chunk()
    chunk.metadata.custom = {"keep": 1, "override": "old"}
    out = attach_custom_metadata([chunk], {"override": "new", "extra": 2})
    assert out[0].metadata.custom == {"keep": 1, "override": "new", "extra": 2}
    # original not modified
    assert chunk.metadata.custom == {"keep": 1, "override": "old"}


def test_non_serializable_custom_rejected():
    with pytest.raises(ConfigError):
        attach_custom_metadata([_chunk()], {"bad": object()})


def test_empty_custom_returns_copy_of_list():
    chunks = [_chunk()]
    out = attach_custom_metadata(chunks, {})
    assert out == chunks
    out2 = attach_custom_metadata(chunks, None)
    assert out2 == chunks


def test_metadata_groups_are_separate_dicts():
    meta = ChunkMetadata()
    assert meta.organization is not meta.strategy
    assert meta.strategy is not meta.custom
    m2 = ChunkMetadata()
    assert meta.organization is not m2.organization
