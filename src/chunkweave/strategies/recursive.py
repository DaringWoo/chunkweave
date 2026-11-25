"""Recursive separator-based chunking strategy.

Splits text by descending separator priority into leaf fragments, then
greedily merges adjacent leaves back up to ``chunk_size``. Also exposes the
leaf-splitting machinery for the semantic strategy's unit splitting and
length fallback.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from ..chunk import Chunk, ChunkMetadata, chunk_id_for
from ..config import KeepSeparator, RecursiveConfig, Separator

CHAR_FALLBACK_SEPARATOR = ""
"""Pseudo separator used when splitting falls back to raw code points."""


def _compile_separator(sep: Separator) -> re.Pattern[str] | None:
    """Compile a separator to a pattern; ``""`` means char fallback (None)."""
    if isinstance(sep, re.Pattern):
        return sep
    if sep == CHAR_FALLBACK_SEPARATOR:
        return None
    return re.compile(re.escape(sep))


def _separator_spec(sep: Separator) -> str:
    """JSON-friendly form of a configured separator for metadata."""
    return sep.pattern if isinstance(sep, re.Pattern) else sep


def _split_with_separator(
    text: str,
    start: int,
    end: int,
    pattern: re.Pattern[str],
    keep: KeepSeparator,
) -> list[tuple[int, int]]:
    """Split ``text[start:end]`` at every non-empty match of ``pattern``.

    ``keep`` decides where a matched separator lands: ``previous`` attaches it
    to the piece before it, ``next`` to the piece after it, ``none`` drops it
    leaving an uncovered gap. Empty matches are ignored so separators that can
    match the empty string cannot stall the splitter.
    """
    matches = [m for m in pattern.finditer(text, start, end) if m.end() > m.start()]
    if not matches:
        return [(start, end)]
    pieces: list[tuple[int, int]] = []
    cursor = start
    if keep == "previous":
        for m in matches:
            pieces.append((cursor, m.end()))
            cursor = m.end()
        pieces.append((cursor, end))
    elif keep == "next":
        for m in matches:
            pieces.append((cursor, m.start()))
            cursor = m.start()
        pieces.append((cursor, end))
    else:
        for m in matches:
            pieces.append((cursor, m.start()))
            cursor = m.end()
        pieces.append((cursor, end))
    return [(s, e) for s, e in pieces if e > s]


@dataclass
class _Fragment:
    start: int
    end: int
    separator_used: str | None
    separator_level: int | None


def _leaf_fragments(
    text: str,
    separators: Sequence[Separator],
    keep: KeepSeparator,
    chunk_size: int,
    max_depth: int | None,
) -> list[_Fragment]:
    """Split ``text`` into leaf fragments of at most ``chunk_size`` code points.

    Worklist-driven descent: a fragment larger than ``chunk_size`` is split by
    the separator at its current level; pieces that still exceed the limit are
    pushed to the next (finer) separator level. When separators are exhausted,
    an empty-string separator is reached, or ``max_depth`` is exceeded, the
    fragment is split by raw code points. Termination is guaranteed because the
    separator level strictly increases.
    """
    if not text:
        return []
    compiled = [(_separator_spec(s), _compile_separator(s)) for s in separators]
    depth_cap = len(compiled) if max_depth is None else min(len(compiled), max_depth)

    leaves: list[_Fragment] = []
    worklist: list[tuple[int, int, int, str | None, int | None]] = [
        (0, len(text), 0, None, None)
    ]
    while worklist:
        start, end, level, sep_used, sep_level = worklist.pop()
        if end - start <= chunk_size:
            leaves.append(_Fragment(start, end, sep_used, sep_level))
            continue
        if level >= depth_cap:
            for s in range(start, end, chunk_size):
                leaves.append(
                    _Fragment(s, min(s + chunk_size, end), CHAR_FALLBACK_SEPARATOR, level)
                )
            continue
        spec, pattern = compiled[level]
        if pattern is None:
            for s in range(start, end, chunk_size):
                leaves.append(_Fragment(s, min(s + chunk_size, end), spec, level))
            continue
        pieces = _split_with_separator(text, start, end, pattern, keep)
        if len(pieces) <= 1:
            worklist.append((start, end, level + 1, sep_used, sep_level))
            continue
        for piece_start, piece_end in pieces:
            worklist.append((piece_start, piece_end, level + 1, spec, level))
    leaves.sort(key=lambda f: (f.start, f.end))
    return leaves


def _merge_fragments(leaves: list[_Fragment], chunk_size: int) -> list[_Fragment]:
    """Greedily merge adjacent leaves up to ``chunk_size``.

    A merge never spans an uncovered gap (``keep_separator="none"`` leaves
    separated by dropped separator text). A merged fragment records the
    separator info of its first leaf.
    """
    if not leaves:
        return []
    merged: list[_Fragment] = []
    cur_start, cur_end = leaves[0].start, leaves[0].end
    cur_sep, cur_level = leaves[0].separator_used, leaves[0].separator_level
    for leaf in leaves[1:]:
        if leaf.start == cur_end and leaf.end - cur_start <= chunk_size:
            cur_end = leaf.end
            continue
        merged.append(_Fragment(cur_start, cur_end, cur_sep, cur_level))
        cur_start, cur_end = leaf.start, leaf.end
        cur_sep, cur_level = leaf.separator_used, leaf.separator_level
    merged.append(_Fragment(cur_start, cur_end, cur_sep, cur_level))
    return merged


def _apply_overlap(merged: list[_Fragment], overlap: int) -> list[_Fragment]:
    """Carry up to ``overlap`` code points of each chunk's tail into the next.

    The carry is clamped to ``len(prev) - 1`` so ``start_offset`` stays
    strictly increasing, and is zero across an uncovered gap produced by
    ``keep_separator="none"``.
    """
    if overlap <= 0 or len(merged) < 2:
        return merged
    out = [merged[0]]
    for prev, cur in itertools.pairwise(merged):
        carry = 0 if cur.start > prev.end else min(overlap, (prev.end - prev.start) - 1)
        new_start = max(prev.start + 1, cur.start - carry)
        out.append(_Fragment(new_start, cur.end, cur.separator_used, cur.separator_level))
    return out


def _fragments_to_chunks(text: str, fragments: list[_Fragment]) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=chunk_id_for(i),
            content=text[f.start : f.end],
            start_offset=f.start,
            end_offset=f.end,
            metadata=ChunkMetadata(
                strategy={
                    "separator_used": f.separator_used,
                    "separator_level": f.separator_level,
                }
            ),
        )
        for i, f in enumerate(fragments)
    ]


def split_text(
    text: str,
    separators: Sequence[Separator],
    chunk_size: int,
    keep: KeepSeparator = "previous",
    overlap: int = 0,
    max_depth: int | None = None,
) -> list[tuple[int, int]]:
    """Split ``text`` into ``(start, end)`` chunk ranges via the recursive mechanism."""
    leaves = _leaf_fragments(text, separators, keep, chunk_size, max_depth)
    merged = _merge_fragments(leaves, chunk_size)
    merged = _apply_overlap(merged, overlap)
    return [(f.start, f.end) for f in merged]


class RecursiveChunker:
    """Splits text by separator priority, then merges leaves up to ``chunk_size``."""

    metadata_keys: ClassVar[frozenset[str]] = frozenset(
        {"separator_used", "separator_level"}
    )

    def __init__(self, config: RecursiveConfig) -> None:
        self.config = config

    def chunk(self, text: str) -> Sequence[Chunk]:
        if not text:
            return []
        leaves = _leaf_fragments(
            text,
            self.config.separators,
            self.config.keep_separator,
            self.config.chunk_size,
            self.config.max_depth,
        )
        merged = _merge_fragments(leaves, self.config.chunk_size)
        merged = _apply_overlap(merged, self.config.overlap)
        return _fragments_to_chunks(text, merged)
