"""Registering a custom chunker and using it at any pipeline level."""

import re
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from chunkweave import ChunkEngine, ChunkSpan, Policy

sys.stdout.reconfigure(encoding="utf-8")

POLICIES = Path(__file__).parent / "policies"


class WordsParams(BaseModel):
    """Params schema for the ``words`` strategy."""

    model_config = ConfigDict(extra="forbid")

    max_words: StrictInt = Field(default=4, gt=0)


class WordChunker:
    """Third-party chunker: groups of at most ``max_words`` words.

    Chunks run from a word's start to the last included word's end; the
    whitespace between groups is uncovered (like keep_separator="none").
    """

    def __init__(self, params: WordsParams) -> None:
        self.max_words = params.max_words

    def chunk(self, text: str) -> list[ChunkSpan]:
        word_spans = [m.span() for m in re.finditer(r"\S+", text)]
        spans: list[ChunkSpan] = []
        for i in range(0, len(word_spans), self.max_words):
            group = word_spans[i : i + self.max_words]
            start, end = group[0][0], group[-1][1]
            spans.append(
                ChunkSpan(
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    strategy_metadata={"word_count": len(group)},
                )
            )
        return spans


def main() -> None:
    engine = ChunkEngine()
    engine.register(
        "words",
        lambda params, _provider: WordChunker(params),
        params_model=WordsParams,
    )
    result = engine.execute(
        "the quick brown fox jumps over the lazy dog",
        Policy.from_file(POLICIES / "words.yaml"),
    )
    for c in result.chunks:
        print(
            f"{c.chunk_id} L{c.level} seq={c.sequence} "
            f"[{c.start_offset},{c.end_offset}) {c.content!r} "
            f"strat={c.strategy_metadata}"
        )


if __name__ == "__main__":
    main()
