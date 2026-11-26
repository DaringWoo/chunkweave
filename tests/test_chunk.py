"""Chunk model: unified type, offsets, deterministic ids, serialization."""


from chunkweave import (
    Chunk,
    ChunkEngine,
    ChunkResult,
    ChunkSpan,
    RecursiveParams,
    SemanticParams,
    SlidingWindowParams,
)
from chunkweave.strategies import (
    RecursiveChunker,
    SemanticChunker,
    SlidingWindowChunker,
)
from conftest import FakeProvider, make_policy


def _chunkers():
    return [
        SlidingWindowChunker(SlidingWindowParams(chunk_size=4, overlap=1)),
        RecursiveChunker(RecursiveParams(chunk_size=10, separators=["\n", "。"])),
        SemanticChunker(
            SemanticParams(threshold=0.5, chunk_size=12), FakeProvider()
        ),
    ]


def test_strategies_produce_chunk_spans():
    text = "第一段落。第二段落。\n第三段。"
    for chunker in _chunkers():
        for span in chunker.chunk(text):
            assert isinstance(span, ChunkSpan)
            assert isinstance(span.content, str)
            assert isinstance(span.start_offset, int)
            assert isinstance(span.end_offset, int)
            assert isinstance(span.strategy_metadata, dict)


def test_span_offsets_are_local_and_deterministic():
    text = "alpha beta gamma delta epsilon zeta eta theta"
    for chunker in _chunkers():
        first = chunker.chunk(text)
        second = chunker.chunk(text)
        assert [s.model_dump() for s in first] == [
            s.model_dump() for s in second
        ]


def test_content_matches_offsets_with_unicode():
    text = "中文句子，带emoji🎉和组合字符é结尾。"
    for chunker in _chunkers():
        for span in chunker.chunk(text):
            assert span.content == text[span.start_offset : span.end_offset]
            assert 0 <= span.start_offset < span.end_offset <= len(text)


def test_empty_text_empty_spans():
    for chunker in _chunkers():
        assert chunker.chunk("") == []


def test_spans_have_no_organization_fields():
    text = "abc def ghi jkl mno"
    for chunker in _chunkers():
        for span in chunker.chunk(text):
            assert not {"parent_id", "level", "sequence"} & set(
                span.strategy_metadata
            )


def _result(text="ab\ncdef\n\ngh"):
    engine = ChunkEngine()
    return engine.execute(
        text,
        make_policy(
            [
                {"name": "l0", "strategy": "recursive",
                 "params": {"chunk_size": 10, "separators": ["\n\n"]}},
                {"name": "l1", "strategy": "sliding_window",
                 "params": {"chunk_size": 3}},
            ],
            fields={"src": {"value": "测试"}},
        ),
    )


def test_chunk_fields():
    result = _result()
    for c in result.chunks:
        assert isinstance(c.chunk_id, str)
        assert isinstance(c.content, str)
        assert isinstance(c.level, int)
        assert isinstance(c.sequence, int)
        assert isinstance(c.strategy, str)
        assert isinstance(c.strategy_metadata, dict)
        assert isinstance(c.metadata, dict)
        assert c.metadata["src"] == "测试"


def test_chunk_id_unique_and_deterministic():
    first = _result()
    second = _result()
    ids = [c.chunk_id for c in first.chunks]
    assert len(ids) == len(set(ids))
    assert ids == [c.chunk_id for c in second.chunks]


def test_chunk_json_roundtrip():
    chunk = Chunk(
        chunk_id="chunk-0003",
        content="中文🎉内容",
        parent_id="chunk-0000",
        level=1,
        sequence=2,
        start_offset=5,
        end_offset=12,
        strategy="recursive",
        strategy_metadata={"separator_used": "\n"},
        metadata={"kind": "x"},
    )
    restored = Chunk.model_validate_json(chunk.model_dump_json())
    assert restored == chunk


def test_result_json_roundtrip():
    result = _result()
    restored = ChunkResult.model_validate_json(result.model_dump_json())
    assert [c.model_dump() for c in restored.chunks] == [
        c.model_dump() for c in result.chunks
    ]


def test_total_is_serialized_computed_field():
    result = _result("abcdef")
    data = result.model_dump()
    assert data["total"] == len(result.chunks)
    assert result.total == len(result.chunks)


def test_serialization_output_stable():
    result = _result()
    assert result.model_dump_json() == result.model_dump_json()


def test_parent_id_rebuilds_tree():
    """parent_id alone reconstructs the hierarchy (no tree view needed)."""
    result = _result()
    children: dict[str | None, list] = {}
    for c in result.chunks:
        children.setdefault(c.parent_id, []).append(c)
    roots = children.get(None, [])
    assert len(roots) == 2
    by_id = {c.chunk_id: c for c in result.chunks}
    for c in result.chunks:
        if c.level == 1:
            assert c.parent_id in by_id
            assert c in children[c.parent_id]


def test_chunk_result_sorted_by_offset_parent_first():
    result = _result()
    for i, c in enumerate(result.chunks):
        if i == 0:
            continue
        prev = result.chunks[i - 1]
        assert (prev.start_offset, prev.level) <= (c.start_offset, c.level)
