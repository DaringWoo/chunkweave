"""Chunk model: unified type, offsets, deterministic ids, serialization."""

import json

import pytest

from chunkweave import (
    Chunk,
    ChunkMetadata,
    RecursiveConfig,
    SemanticConfig,
    SlidingWindowConfig,
)
from chunkweave.strategies import (
    LegacyRecursiveChunker as RecursiveChunker,
)
from chunkweave.strategies import (
    LegacySemanticChunker as SemanticChunker,
)
from chunkweave.strategies import (
    LegacySlidingWindowChunker as SlidingWindowChunker,
)


class _FakeProvider:
    def score(self, left: str, right: str) -> float:
        return 1.0


def _chunkers():
    return [
        SlidingWindowChunker(SlidingWindowConfig(chunk_size=4, overlap=1)),
        RecursiveChunker(RecursiveConfig(chunk_size=10, separators=["\n", "。"])),
        SemanticChunker(
            SemanticConfig(threshold=0.5, chunk_size=12), provider=_FakeProvider()
        ),
    ]


def test_strategies_produce_unified_chunk_type():
    text = "第一段落。第二段落。\n第三段。"
    for chunker in _chunkers():
        for chunk in chunker.chunk(text):
            assert isinstance(chunk, Chunk)
            assert isinstance(chunk.chunk_id, str)
            assert isinstance(chunk.content, str)
            assert isinstance(chunk.start_offset, int)
            assert isinstance(chunk.end_offset, int)
            assert isinstance(chunk.metadata, ChunkMetadata)


@pytest.mark.parametrize("chunker", _chunkers())
def test_chunk_id_unique_and_deterministic(chunker):
    text = "alpha beta gamma delta epsilon zeta eta theta"
    first = chunker.chunk(text)
    second = chunker.chunk(text)
    ids = [c.chunk_id for c in first]
    assert len(ids) == len(set(ids))
    assert ids == [c.chunk_id for c in second]


def test_content_matches_offsets_with_unicode():
    text = "中文句子，带emoji🎉和组合字符e\u0301结尾。"
    for chunker in _chunkers():
        for chunk in chunker.chunk(text):
            assert chunk.content == text[chunk.start_offset : chunk.end_offset]
            assert 0 <= chunk.start_offset < chunk.end_offset <= len(text)


def test_empty_text_offset_safety():
    for chunker in _chunkers():
        assert chunker.chunk("") == []


def test_strategy_result_has_no_organization_fields():
    text = "abc def ghi jkl mno"
    for chunker in _chunkers():
        for chunk in chunker.chunk(text):
            assert chunk.metadata.organization == {}


def test_chunk_json_roundtrip():
    original = Chunk(
        chunk_id="chunk-0003",
        content="中文🎉内容",
        start_offset=5,
        end_offset=12,
        metadata=ChunkMetadata(
            organization={"parent_id": "chunk-0000", "level": 1, "sequence": 2},
            strategy={"window_index": 3},
            custom={"source": "测试", "tags": ["a", "b"]},
        ),
    )
    restored = Chunk.from_json(original.to_json())
    assert restored == original
    again = Chunk.from_dict(json.loads(original.to_json()))
    assert again == original


def test_serialization_output_stable():
    chunk = Chunk(chunk_id="c", content="x", start_offset=0, end_offset=1)
    assert chunk.to_json() == chunk.to_json()
