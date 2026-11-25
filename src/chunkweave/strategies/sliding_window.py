"""Sliding window chunking strategy."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from ..chunk import Chunk, ChunkMetadata, chunk_id_for
from ..config import SlidingWindowConfig


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
