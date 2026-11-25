"""Chunking strategies and their protocols.

``Chunker`` is the strategy contract, ``SimilarityProvider`` the injected
similarity computation for semantic chunking, ``ProviderAware`` the opt-in
injection point. Builtin strategies: ``sliding_window``, ``recursive``,
``semantic``.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

from .config import (
    KeepSeparator,
    RecursiveConfig,
    SemanticConfig,
    Separator,
    SlidingWindowConfig,
)
from .models import (
    Chunk,
    ChunkMetadata,
    ChunkweaveError,
    ProviderMissingError,
    chunk_id_for,
)


@runtime_checkable
class Chunker(Protocol):
    """A text chunking strategy.

    Implementations receive their configuration at construction time and
    produce :class:`Chunk` results plus their declared strategy metadata.
    They MUST NOT set organization fields (``parent_id``, ``level``,
    ``sequence``); that is the organization layer's job.
    """

    metadata_keys: ClassVar[frozenset[str]]
    """Strategy metadata keys this chunker may produce."""

    def chunk(self, text: str) -> Sequence[Chunk]:
        """Split ``text`` and return chunks in stable input order."""
        ...


class SimilarityProvider(Protocol):
    """Injected similarity computation for semantic chunking.

    ``score(left, right)`` returns a similarity in ``[0, 1]`` for two
    adjacent semantic units; higher means more similar. Implementations are
    synchronous and side-effect free. ``score_batch`` is an optional batch
    optimization; the engine falls back to per-pair ``score`` calls.
    """

    def score(self, left: str, right: str) -> float:
        """Similarity of two adjacent units in ``[0, 1]``."""
        ...


@runtime_checkable
class ProviderAware(Protocol):
    """A chunker that accepts an injected similarity provider."""

    def set_provider(self, provider: SimilarityProvider) -> None:
        """Inject the similarity provider used by ``chunk``."""
        ...


class SlidingWindowChunker:
    """Splits text into fixed-size windows advancing by ``chunk_size - overlap``.

    ``overlap = 0`` is fixed-size chunking; no separate FixedSize algorithm
    exists. Windows always advance, so the loop terminates.
    """

    metadata_keys: ClassVar[frozenset[str]] = frozenset({"window_index", "overlap_size"})

    def __init__(self, config: SlidingWindowConfig) -> None:
        self.config = config

    def chunk(self, text: str) -> Sequence[Chunk]:
        if not text:
            return []
        size = self.config.chunk_size
        step = size - self.config.overlap
        chunks: list[Chunk] = []
        start = 0
        index = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append(
                Chunk(
                    chunk_id=chunk_id_for(index),
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    metadata=ChunkMetadata(
                        strategy={
                            "window_index": index,
                            "overlap_size": 0 if index == 0 else self.config.overlap,
                        }
                    ),
                )
            )
            index += 1
            start += step
        return chunks


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


def _semantic_units(text: str, separators: Sequence[Separator]) -> list[tuple[int, int]]:
    """Split ``text`` into semantic units at every separator level.

    Units keep their trailing separator (attached to the previous unit), cover
    the whole text without gaps, are never merged, and are not constrained by
    ``chunk_size``. An empty-string separator is meaningless here and ignored.
    """
    pieces = [(0, len(text))]
    for sep in separators:
        pattern = _compile_separator(sep)
        if pattern is None:
            continue
        next_pieces: list[tuple[int, int]] = []
        for start, end in pieces:
            next_pieces.extend(_split_with_separator(text, start, end, pattern, "previous"))
        pieces = next_pieces
    return pieces


class SemanticChunker:
    """Splits text where adjacent-unit similarity drops below ``threshold``.

    Requires an injected :class:`SimilarityProvider`; provider exceptions
    propagate unchanged. Semantic blocks longer than ``chunk_size`` are
    re-split through the recursive mechanism so the length limit always holds.
    """

    metadata_keys: ClassVar[frozenset[str]] = frozenset({"boundary_score"})

    def __init__(
        self, config: SemanticConfig, provider: SimilarityProvider | None = None
    ) -> None:
        self.config = config
        self.provider = provider

    def set_provider(self, provider: SimilarityProvider) -> None:
        self.provider = provider

    def _scores(self, pairs: list[tuple[str, str]]) -> list[float]:
        assert self.provider is not None
        batch = getattr(self.provider, "score_batch", None)
        if callable(batch):
            return [float(s) for s in batch(pairs)]
        return [float(self.provider.score(left, right)) for left, right in pairs]

    def chunk(self, text: str) -> Sequence[Chunk]:
        if self.provider is None:
            raise ProviderMissingError("semantic")
        if not text:
            return []

        units = _semantic_units(text, self.config.unit_separators)
        if not units:
            return []

        blocks: list[tuple[int, int]] = []
        block_scores: list[float | None] = []
        if len(units) < 2:
            blocks = [units[0]]
            block_scores = [None]
        else:
            pairs = [
                (text[s1:e1], text[s2:e2])
                for (s1, e1), (s2, e2) in itertools.pairwise(units)
            ]
            scores = self._scores(pairs)
            if len(scores) != len(pairs):
                raise ChunkweaveError(
                    f"provider returned {len(scores)} scores for "
                    f"{len(pairs)} unit pairs"
                )
            cur_start, cur_end = units[0]
            cur_score: float | None = None
            for i, score in enumerate(scores):
                if score < self.config.threshold:
                    blocks.append((cur_start, cur_end))
                    block_scores.append(cur_score)
                    cur_start = units[i + 1][0]
                    cur_score = score
                cur_end = units[i + 1][1]
            blocks.append((cur_start, cur_end))
            block_scores.append(cur_score)

        chunks: list[Chunk] = []
        for (block_start, block_end), boundary_score in zip(blocks, block_scores, strict=True):
            if block_end - block_start <= self.config.chunk_size:
                ranges = [(block_start, block_end)]
            else:
                ranges = [
                    (block_start + s, block_start + e)
                    for s, e in split_text(
                        text[block_start:block_end],
                        self.config.unit_separators,
                        self.config.chunk_size,
                        keep="previous",
                    )
                ]
            for i, (start, end) in enumerate(ranges):
                chunk_score = boundary_score if i == 0 else None
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id_for(len(chunks)),
                        content=text[start:end],
                        start_offset=start,
                        end_offset=end,
                        metadata=ChunkMetadata(strategy={"boundary_score": chunk_score}),
                    )
                )
        return chunks
