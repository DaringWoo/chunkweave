"""Single level + sliding_window strategy via a Policy file."""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump!"
)

POLICIES = Path(__file__).parent / "policies"


def main() -> None:
    engine = ChunkEngine()
    policy = Policy.from_file(POLICIES / "sliding.yaml")
    result = engine.execute(TEXT, policy)
    for c in result.chunks:
        print(
            f"{c.chunk_id} [{c.start_offset:>3},{c.end_offset:>3}) "
            f"win={c.strategy_metadata['window_index']} "
            f"ov={c.strategy_metadata['overlap_size']} :: {c.content!r}"
        )
    print(f"\n{len(result.chunks)} chunks, metadata={result.chunks[0].metadata}")


if __name__ == "__main__":
    main()
