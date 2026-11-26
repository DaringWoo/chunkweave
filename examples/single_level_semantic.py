"""Single level + semantic strategy with a deterministic fake provider.

A real provider would call an embedding model; this demo provider is
deterministic and offline: similarity is high when two adjacent units start
with the same character, low otherwise.
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = "苹果很甜。苹果是水果。香蕉也是水果。微积分很难。导数是微积分的基础。"

POLICIES = Path(__file__).parent / "policies"


class DemoProvider:
    """Stand-in for an embedding-similarity service."""

    def score(self, left: str, right: str) -> float:
        return 0.9 if left and right and left[0] == right[0] else 0.2

    def score_batch(self, pairs):
        return [self.score(left, right) for left, right in pairs]


def main() -> None:
    engine = ChunkEngine()
    result = engine.execute(
        TEXT,
        Policy.from_file(POLICIES / "semantic.yaml"),
        provider=DemoProvider(),
    )
    for c in result.chunks:
        print(
            f"{c.chunk_id} [{c.start_offset},{c.end_offset}) "
            f"boundary_score={c.strategy_metadata['boundary_score']} :: {c.content!r}"
        )


if __name__ == "__main__":
    main()
