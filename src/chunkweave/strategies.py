"""Chunking strategies, their parameter models and protocols.

``Chunker`` is the strategy contract: ``chunk(text)`` returns
:class:`ChunkSpan` objects whose offsets are relative to the input text.
``SimilarityProvider`` is the injected similarity computation for semantic
chunking. Builtin strategies: ``sliding_window``, ``recursive``,
``semantic``.

"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from .models import ChunkSpan, ChunkweaveError, ProviderMissingError

Separator = str | re.Pattern[str]
KeepSeparator = Literal["previous", "next", "none"]

DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", "。", "！", "？", "；", "，", "")
DEFAULT_UNIT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", "。", "！", "？")


# ---------------------------------------------------------------------------
# Parameter models (Policy ``params`` payload, JSON-serializable form)
# ---------------------------------------------------------------------------


class SeparatorSpec(BaseModel):
    """A declared separator: a literal string, or a regex via ``regex: true``."""

    model_config = ConfigDict(extra="forbid")

    value: str
    regex: StrictBool = False

    @model_validator(mode="after")
    def _regex_must_compile(self) -> SeparatorSpec:
        if self.regex:
            try:
                re.compile(self.value)
            except re.error as e:
                raise ValueError(f"separator regex does not compile: {e}") from e
        return self


SeparatorDecl = str | SeparatorSpec
"""Declared separator form in ``params``: literal string or ``SeparatorSpec``."""


def compile_separator(decl: SeparatorDecl) -> Separator:
    """Compile a declared separator to ``str`` or ``re.Pattern``."""
    if isinstance(decl, SeparatorSpec):
        return re.compile(decl.value) if decl.regex else decl.value
    return decl


def _default_separators() -> list[SeparatorDecl]:
    return list(DEFAULT_SEPARATORS)


def _default_unit_separators() -> list[SeparatorDecl]:
    return list(DEFAULT_UNIT_SEPARATORS)


class SlidingWindowParams(BaseModel):
    """``params`` for ``sliding_window``. Lengths are Unicode code points."""

    model_config = ConfigDict(extra="forbid")

    chunk_size: StrictInt = Field(gt=0)
    overlap: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _overlap_below_size(self) -> SlidingWindowParams:
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap must satisfy 0 <= overlap < chunk_size, got {self.overlap}"
            )
        return self


class RecursiveParams(BaseModel):
    """``params`` for ``recursive``. ``separators`` mix literals and regexes."""

    model_config = ConfigDict(extra="forbid")

    chunk_size: StrictInt = Field(gt=0)
    separators: list[SeparatorDecl] = Field(
        default_factory=_default_separators
    )
    overlap: StrictInt = Field(default=0, ge=0)
    keep_separator: KeepSeparator = "previous"
    max_depth: StrictInt | None = None

    @model_validator(mode="after")
    def _max_depth_positive(self) -> RecursiveParams:
        if self.max_depth is not None and self.max_depth <= 0:
            raise ValueError(f"max_depth must be > 0, got {self.max_depth}")
        return self


class SemanticParams(BaseModel):
    """``params`` for ``semantic``. Provider is injected, never declared."""

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    chunk_size: StrictInt = Field(gt=0)
    unit_separators: list[SeparatorDecl] = Field(
        default_factory=_default_unit_separators
    )

    @field_validator("threshold", mode="before")
    @classmethod
    def _threshold_is_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(
                f"threshold must be a number in [0, 1], got {type(value).__name__}"
            )
        return float(value)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Chunker(Protocol):
    """A text chunking strategy.

    Implementations receive their validated params (and, when required, an
    injected provider) at construction time and produce :class:`ChunkSpan`
    results; organization fields and business metadata are not their job.
    """

    def chunk(self, text: str) -> list[ChunkSpan]:
        """Split ``text`` and return spans in stable input order."""
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


# ---------------------------------------------------------------------------
# Builtin chunkers (new contract: params model in, ChunkSpan out)
# ---------------------------------------------------------------------------


class SlidingWindowChunker:
    """Splits text into fixed-size windows advancing by ``chunk_size - overlap``.

    ``overlap = 0`` is fixed-size chunking; no separate FixedSize algorithm
    exists. Windows always advance, so the loop terminates.
    """

    def __init__(self, params: SlidingWindowParams) -> None:
        self.params = params

    def chunk(self, text: str) -> list[ChunkSpan]:
        if not text:
            return []
        size = self.params.chunk_size
        step = size - self.params.overlap
        spans: list[ChunkSpan] = []
        start = 0
        index = 0
        while start < len(text):
            end = min(start + size, len(text))
            spans.append(
                ChunkSpan(
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    strategy_metadata={
                        "window_index": index,
                        "overlap_size": 0 if index == 0 else self.params.overlap,
                    },
                )
            )
            index += 1
            start += step
        return spans


class RecursiveChunker:
    """Splits text by separator priority, then merges leaves up to ``chunk_size``."""

    def __init__(self, params: RecursiveParams) -> None:
        self.params = params
        self._separators: list[Separator] = [
            compile_separator(d) for d in params.separators
        ]

    def chunk(self, text: str) -> list[ChunkSpan]:
        if not text:
            return []
        leaves = _leaf_fragments(
            text,
            self._separators,
            self.params.keep_separator,
            self.params.chunk_size,
            self.params.max_depth,
        )
        merged = _merge_fragments(leaves, self.params.chunk_size)
        merged = _apply_overlap(merged, self.params.overlap)
        return [
            ChunkSpan(
                content=text[f.start : f.end],
                start_offset=f.start,
                end_offset=f.end,
                strategy_metadata={
                    "separator_used": f.separator_used,
                    "separator_level": f.separator_level,
                },
            )
            for f in merged
        ]


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

    Requires an injected :class:`SimilarityProvider` at construction time;
    provider exceptions propagate unchanged. Semantic blocks longer than
    ``chunk_size`` are re-split through the recursive mechanism so the length
    limit always holds.
    """

    def __init__(
        self, params: SemanticParams, provider: SimilarityProvider | None
    ) -> None:
        self.params = params
        self.provider = provider
        self._unit_separators: list[Separator] = [
            compile_separator(d) for d in params.unit_separators
        ]
        self._fallback = RecursiveChunker(
            RecursiveParams(
                chunk_size=params.chunk_size,
                separators=list(params.unit_separators),
                keep_separator="previous",
            )
        )

    def _scores(self, pairs: list[tuple[str, str]]) -> list[float]:
        assert self.provider is not None
        batch = getattr(self.provider, "score_batch", None)
        if callable(batch):
            return [float(s) for s in batch(pairs)]
        return [float(self.provider.score(left, right)) for left, right in pairs]

    def chunk(self, text: str) -> list[ChunkSpan]:
        if self.provider is None:
            raise ProviderMissingError("semantic")
        if not text:
            return []

        units = _semantic_units(text, self._unit_separators)
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
                if score < self.params.threshold:
                    blocks.append((cur_start, cur_end))
                    block_scores.append(cur_score)
                    cur_start = units[i + 1][0]
                    cur_score = score
                cur_end = units[i + 1][1]
            blocks.append((cur_start, cur_end))
            block_scores.append(cur_score)

        spans: list[ChunkSpan] = []
        for (block_start, block_end), boundary_score in zip(blocks, block_scores, strict=True):
            if block_end - block_start <= self.params.chunk_size:
                ranges = [(block_start, block_end)]
            else:
                ranges = [
                    (block_start + s.start_offset, block_start + s.end_offset)
                    for s in self._fallback.chunk(text[block_start:block_end])
                ]
            for i, (start, end) in enumerate(ranges):
                span_score = boundary_score if i == 0 else None
                spans.append(
                    ChunkSpan(
                        content=text[start:end],
                        start_offset=start,
                        end_offset=end,
                        strategy_metadata={"boundary_score": span_score},
                    )
                )
        return spans
