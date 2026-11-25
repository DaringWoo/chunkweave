"""Registering a custom chunker and using it at any hierarchy level."""

import re
import sys
from collections.abc import Sequence
from typing import ClassVar

from chunkweave import Chunk, ChunkEngine, ChunkMetadata
from chunkweave.chunk import chunk_id_for

sys.stdout.reconfigure(encoding="utf-8")


class WordChunker:
    """Third-party chunker: groups of at most ``max_words`` words.

    Chunks run from a word's start to the last included word's end; the
    whitespace between groups is uncovered (like keep_separator="none").
    """

    metadata_keys: ClassVar[frozenset[str]] = frozenset({"word_count"})

    def __init__(self, config):
        self.max_words = config.get("max_words", 4)

    def chunk(self, text: str) -> Sequence[Chunk]:
        word_spans = [m.span() for m in re.finditer(r"\S+", text)]
        chunks: list[Chunk] = []
        for i in range(0, len(word_spans), self.max_words):
            group = word_spans[i : i + self.max_words]
            start, end = group[0][0], group[-1][1]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id_for(len(chunks)),
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    metadata=ChunkMetadata(strategy={"word_count": len(group)}),
                )
            )
        return chunks


def main() -> None:
    engine = ChunkEngine()
    engine.register("words", lambda cfg: WordChunker(cfg))
    result = engine.chunk(
        "the quick brown fox jumps over the lazy dog",
        {
            "organization": "hierarchical",
            "levels": [
                {"strategy": "words", "config": {"max_words": 3}},
                {"strategy": "sliding_window", "config": {"chunk_size": 8}},
            ],
        },
    )
    for c in result.chunks:
        org = c.metadata.organization
        print(
            f"{c.chunk_id} L{org['level']} seq={org['sequence']} "
            f"[{c.start_offset},{c.end_offset}) {c.content!r} strat={c.metadata.strategy}"
        )


if __name__ == "__main__":
    main()
