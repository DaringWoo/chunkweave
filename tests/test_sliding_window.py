"""Sliding window: fixed size, overlap, edges, metadata."""

import itertools

import pytest

from chunkweave import ConfigError, SlidingWindowConfig
from chunkweave.strategies import SlidingWindowChunker


def make(chunk_size, overlap=0):
    return SlidingWindowChunker(SlidingWindowConfig(chunk_size=chunk_size, overlap=overlap))


def test_overlap_zero_is_fixed_size():
    chunks = make(3).chunk("abcdefghi")
    assert [(c.start_offset, c.end_offset) for c in chunks] == [(0, 3), (3, 6), (6, 9)]
    assert [c.content for c in chunks] == ["abc", "def", "ghi"]
    assert not any(c.metadata.organization for c in chunks)


def test_normal_overlap():
    chunks = make(4, overlap=2).chunk("abcdefgh")
    # step=2; the tail window at 6 is emitted even though [4,8) reached the end
    assert [(c.start_offset, c.end_offset) for c in chunks] == [
        (0, 4),
        (2, 6),
        (4, 8),
        (6, 8),
    ]


def test_max_legal_overlap_advances_by_one():
    chunks = make(3, overlap=2).chunk("abcde")
    assert [(c.start_offset, c.end_offset) for c in chunks] == [
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
            chunks = make(size, ov).chunk(text)
            starts = [c.start_offset for c in chunks]
            assert starts == sorted(starts)
            assert all(a < b for a, b in itertools.pairwise(starts))


def test_text_shorter_than_window_single_chunk():
    chunks = make(10).chunk("abc")
    assert len(chunks) == 1
    assert (chunks[0].start_offset, chunks[0].end_offset) == (0, 3)
    assert chunks[0].metadata.strategy["window_index"] == 0
    assert chunks[0].metadata.strategy["overlap_size"] == 0


def test_last_window_truncated():
    chunks = make(4).chunk("abcdefghi")  # len 9
    assert chunks[-1].content == "i"
    assert (chunks[-1].start_offset, chunks[-1].end_offset) == (8, 9)


def test_empty_text_empty_result():
    assert make(5).chunk("") == []


def test_window_index_and_overlap_size_metadata():
    chunks = make(3, overlap=1).chunk("abcdef")
    assert [c.metadata.strategy["window_index"] for c in chunks] == [0, 1, 2]
    assert [c.metadata.strategy["overlap_size"] for c in chunks] == [0, 1, 1]


def test_unicode_offsets():
    text = "中文字符🎉多一点字"
    chunks = make(3, overlap=1).chunk(text)
    for c in chunks:
        assert c.content == text[c.start_offset : c.end_offset]
    assert chunks[0].content == "中文字"


def test_invalid_config():
    with pytest.raises(ConfigError):
        make(5, overlap=5)
    with pytest.raises(ConfigError):
        make(0)
