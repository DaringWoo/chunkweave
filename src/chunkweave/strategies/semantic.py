"""Semantic chunking strategy driven by an injected similarity provider."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import ClassVar

from ..chunk import Chunk, ChunkMetadata, chunk_id_for
from ..config import SemanticConfig, Separator
from ..errors import ChunkweaveError, ProviderMissingError
from .base import SimilarityProvider
from .recursive import _compile_separator, _split_with_separator, split_text


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
