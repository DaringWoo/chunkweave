"""Recursive strategy: priority splitting, merging, keep/overlap, metadata."""

import itertools
import re

from chunkweave import RecursiveConfig
from chunkweave.strategies import RecursiveChunker


def make(chunk_size, **kwargs):
    return RecursiveChunker(RecursiveConfig(chunk_size=chunk_size, **kwargs))


def spans(chunks):
    return [(c.start_offset, c.end_offset) for c in chunks]


def assert_offsets(chunks, text):
    for c in chunks:
        assert c.content == text[c.start_offset : c.end_offset]
    starts = [c.start_offset for c in chunks]
    assert all(a < b for a, b in itertools.pairwise(starts))


# ---- 5.1 splitting ----


def test_multilevel_separator_descent():
    text = "aa\n\nbb\ncc"
    chunks = make(4, separators=["\n\n", "\n"]).chunk(text)
    assert spans(chunks) == [(0, 4), (4, 7), (7, 9)]
    meta = [c.metadata.strategy for c in chunks]
    assert meta[0]["separator_used"] == "\n\n"
    assert meta[0]["separator_level"] == 0
    assert meta[1]["separator_used"] == "\n"
    assert meta[1]["separator_level"] == 1


def test_text_within_size_no_split():
    chunks = make(100, separators=["\n\n"]).chunk("short text")
    assert len(chunks) == 1
    assert chunks[0].content == "short text"
    assert "separator_used" in chunks[0].metadata.strategy
    assert "separator_level" in chunks[0].metadata.strategy


def test_regex_separator():
    text = "第一章aaa第二章bbb第三章c"
    chunks = make(6, separators=[re.compile(r"第[一二三四五六七八九十]+章")]).chunk(text)
    assert spans(chunks) == [(0, 3), (3, 9), (9, 15), (15, 16)]
    assert_offsets(chunks, text)
    assert chunks[0].metadata.strategy["separator_used"] == r"第[一二三四五六七八九十]+章"


def test_no_match_falls_back_to_chars():
    chunks = make(3, separators=[","]).chunk("abcdefg")
    assert spans(chunks) == [(0, 3), (3, 6), (6, 7)]
    assert all(c.metadata.strategy["separator_used"] == "" for c in chunks)


def test_empty_separator_list_only_fallback():
    chunks = make(4, separators=[]).chunk("abcdefghi")
    assert spans(chunks) == [(0, 4), (4, 8), (8, 9)]


def test_explicit_empty_separator_is_char_fallback():
    chunks = make(4, separators=["\n\n", ""]).chunk("aaaa\n\nbbbbbb")
    assert spans(chunks) == [(0, 4), (4, 6), (6, 10), (10, 12)]
    assert all(c.metadata.strategy["separator_used"] == "" for c in chunks)


def test_empty_match_regex_no_deadlock():
    chunks = make(3, separators=[re.compile("x*")]).chunk("abcabcabc")
    assert spans(chunks) == [(0, 3), (3, 6), (6, 9)]


def test_oversized_atomic_fragment_forced_split():
    text = "pre " + "z" * 10 + " post"
    chunks = make(4, separators=[" "]).chunk(text)
    assert_offsets(chunks, text)
    assert all(c.end_offset - c.start_offset <= 4 for c in chunks)


def test_max_depth_char_fallback():
    chunks = make(2, separators=["z"], max_depth=1).chunk("xxxx")
    assert spans(chunks) == [(0, 2), (2, 4)]


def test_empty_text():
    assert make(5).chunk("") == []


def test_terminates_on_pathological_input():
    text = "a" * 1000
    chunks = make(7, separators=["\n", ""]).chunk(text)
    assert_offsets(chunks, text)
    assert len(chunks) == (1000 + 6) // 7


# ---- 5.2 greedy merge ----


def test_small_fragments_greedily_merged():
    # separators split into small leaves that re-merge up to chunk_size
    text = "a。b。c。"
    chunks = make(4, separators=["。"]).chunk(text)
    assert spans(chunks) == [(0, 4), (4, 6)]
    assert chunks[0].content == "a。b。"


def test_merge_never_exceeds_size():
    text = "ab。cd。ef。gh。"
    chunks = make(5, separators=["。"]).chunk(text)
    assert all(c.end_offset - c.start_offset <= 5 for c in chunks)
    assert_offsets(chunks, text)


def test_merged_chunk_takes_first_leaf_separator():
    text = "ab\nc\nd\n\nef"
    chunks = make(4, separators=["\n\n", "\n"]).chunk(text)
    # level-0 "\n\n" -> [0,8) too big -> level-1 "\n" -> [0,3),[3,5),[5,7),[7,8);
    # plus leaf [8,10) "ef" from level 0. Merged: [(0,3),(3,7),(7,10)]
    assert spans(chunks) == [(0, 3), (3, 7), (7, 10)]
    metas = [c.metadata.strategy for c in chunks]
    assert metas[0]["separator_used"] == "\n" and metas[0]["separator_level"] == 1
    # [3,7) merged two level-1 leaves; [7,10) merged a level-1 leaf with the
    # level-0 "ef" leaf -> first leaf's separator wins in both cases
    assert metas[1]["separator_used"] == "\n" and metas[1]["separator_level"] == 1
    assert metas[2]["separator_used"] == "\n" and metas[2]["separator_level"] == 1


# ---- 5.3 keep_separator ----


def test_keep_previous_default_restores_text():
    text = "aa\n\nbb\n\ncc"
    chunks = make(4, separators=["\n\n"]).chunk(text)
    assert spans(chunks) == [(0, 4), (4, 8), (8, 10)]
    assert "".join(c.content for c in chunks) == text


def test_keep_next_attaches_separator_after():
    text = "aa\nbb"
    chunks = make(10, separators=["\n"], keep_separator="next").chunk(text)
    assert "".join(c.content for c in chunks) == text
    # split pieces: "aa", "\nbb" -> merge fits in one chunk of size 10
    assert len(chunks) == 1


def test_keep_next_heading_style():
    text = "第一章aaa第二章bbb"
    chunks = make(
        8, separators=[re.compile(r"第[一二三四]+章")], keep_separator="next"
    ).chunk(text)
    assert spans(chunks) == [(0, 6), (6, 12)]
    assert chunks[0].content == "第一章aaa"
    assert chunks[1].content == "第二章bbb"


def test_keep_none_drops_separator_leaves_gap():
    text = "aa\n\nbb"
    chunks = make(4, separators=["\n\n"], keep_separator="none").chunk(text)
    assert spans(chunks) == [(0, 2), (4, 6)]
    assert_offsets(chunks, text)
    # gap [2, 4) uncovered
    assert chunks[0].end_offset < chunks[1].start_offset


def test_keep_none_with_regex_keeps_match_text_out():
    text = "aa!!bb"
    chunks = make(4, separators=[re.compile("!+")], keep_separator="none").chunk(
        text
    )
    assert spans(chunks) == [(0, 2), (4, 6)]


# ---- 5.4 overlap ----


def test_overlap_carries_context():
    text = "aa\n\nbb\n\ncc"
    chunks = make(5, separators=["\n\n"], overlap=3).chunk(text)
    s = spans(chunks)
    assert s[0] == (0, 4)
    # chunk2 nominal start 4, carries min(3, 4-1)=3 -> start 1
    assert s[1] == (1, 8)
    # chunk3 nominal start 8, prev len 7 -> carry min(3,6)=3 -> start max(2,5)=5
    assert s[2] == (5, 10)
    assert_offsets(chunks, text)


def test_overlap_clamped_on_small_chunks():
    text = "a。b。c。"
    chunks = make(2, separators=["。"], overlap=10).chunk(text)
    starts = [c.start_offset for c in chunks]
    assert all(a < b for a, b in itertools.pairwise(starts))
    assert_offsets(chunks, text)
    for prev, cur in itertools.pairwise(chunks):
        assert cur.start_offset > prev.start_offset
        assert cur.start_offset < cur.end_offset


def test_overlap_never_crosses_gap():
    text = "aa\n\nbb"
    chunks = make(
        4, separators=["\n\n"], keep_separator="none", overlap=5
    ).chunk(text)
    assert spans(chunks) == [(0, 2), (4, 6)]  # unchanged: no carry across gap


# ---- 5.5 strategy metadata ----


def test_separator_metadata_present():
    chunks = make(4, separators=["\n\n", "\n"]).chunk("aa\n\nbb\ncc")
    for c in chunks:
        assert "separator_used" in c.metadata.strategy
        assert "separator_level" in c.metadata.strategy
        assert c.metadata.organization == {}


def test_final_segment_without_separator():
    chunks = make(2, separators=["。"]).chunk("a。b")  # trailing "b" has no sep
    assert chunks[-1].content == "b"


def test_unicode_offsets():
    text = "中文一句。再来一句🎉。最后。"
    chunks = make(6, separators=["。"]).chunk(text)
    assert_offsets(chunks, text)
