"""Sliding window: fixed size, overlap, edges, metadata."""

import itertools

import pytest
from pydantic import ValidationError

from chunkweave import SlidingWindowParams
from chunkweave.strategies import SlidingWindowChunker


def make(chunk_size, overlap=0):
    return SlidingWindowChunker(
        SlidingWindowParams(chunk_size=chunk_size, overlap=overlap)
    )


def test_overlap_zero_is_fixed_size():
    spans = make(3).chunk("abcdefghi")
    assert [(c.start_offset, c.end_offset) for c in spans] == [(0, 3), (3, 6), (6, 9)]
    assert [c.content for c in spans] == ["abc", "def", "ghi"]
    assert not any(
        {"parent_id", "level", "sequence"} & c.strategy_metadata.keys() for c in spans
    )


def test_normal_overlap():
    spans = make(4, overlap=2).chunk("abcdefgh")
    # step=2; the tail window at 6 is emitted even though [4,8) reached the end
    assert [(c.start_offset, c.end_offset) for c in spans] == [
        (0, 4),
        (2, 6),
        (4, 8),
        (6, 8),
    ]


def test_max_legal_overlap_advances_by_one():
    spans = make(3, overlap=2).chunk("abcde")
    assert [(c.start_offset, c.end_offset) for c in spans] == [
        (0, 3),
        (1, 4),
        (2, 5),
        (3, 5),
        (4, 5),
    ]


def test_window_always_advances_no_deadlock():
    text = "x" * 50
    for size in (1, 2, 7):
        for ov in range(size):
            spans = make(size, ov).chunk(text)
            starts = [c.start_offset for c in spans]
            assert starts == sorted(starts)
            assert all(a < b for a, b in itertools.pairwise(starts))


def test_text_shorter_than_window_single_chunk():
    spans = make(10).chunk("abc")
    assert len(spans) == 1
    assert (spans[0].start_offset, spans[0].end_offset) == (0, 3)
    assert spans[0].strategy_metadata["window_index"] == 0
    assert spans[0].strategy_metadata["overlap_size"] == 0


def test_last_window_truncated():
    spans = make(4).chunk("abcdefghi")  # len 9
    assert spans[-1].content == "i"
    assert (spans[-1].start_offset, spans[-1].end_offset) == (8, 9)


def test_empty_text_empty_result():
    assert make(5).chunk("") == []


def test_window_index_and_overlap_size_metadata():
    spans = make(3, overlap=1).chunk("abcdef")
    assert [c.strategy_metadata["window_index"] for c in spans] == [0, 1, 2]
    assert [c.strategy_metadata["overlap_size"] for c in spans] == [0, 1, 1]


def test_unicode_offsets():
    text = "中文字符🎉多一点字"
    spans = make(3, overlap=1).chunk(text)
    for c in spans:
        assert c.content == text[c.start_offset : c.end_offset]
    assert spans[0].content == "中文字"


def test_invalid_config():
    with pytest.raises(ValidationError):
        make(5, overlap=5)
    with pytest.raises(ValidationError):
        make(0)
