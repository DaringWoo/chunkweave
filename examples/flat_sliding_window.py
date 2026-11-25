"""Flat organization + sliding_window strategy."""

import sys

from chunkweave import ChunkEngine

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump!"
)


def main() -> None:
    engine = ChunkEngine()
    result = engine.chunk(
        TEXT,
        {
            "organization": "flat",
            "strategy": "sliding_window",
            "config": {"chunk_size": 30, "overlap": 8},
            "custom": {"source": "pangrams", "lang": "en"},
        },
    )
    for c in result.chunks:
        print(
            f"{c.chunk_id} [{c.start_offset:>3},{c.end_offset:>3}) "
            f"win={c.metadata.strategy['window_index']} "
            f"ov={c.metadata.strategy['overlap_size']} :: {c.content!r}"
        )
    print(f"\n{len(result.chunks)} chunks, custom={result.chunks[0].metadata.custom}")


if __name__ == "__main__":
    main()
