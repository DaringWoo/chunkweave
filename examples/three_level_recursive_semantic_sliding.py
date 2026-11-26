"""Three levels: recursive -> semantic -> sliding_window."""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "苹果富含维生素。苹果可以榨汁。香蕉也很好吃。"
    "微积分研究变化率。导数描述瞬时速度。积分计算面积。"
    "跑步有益健康。游泳锻炼全身。"
)

POLICIES = Path(__file__).parent / "policies"


class DemoProvider:
    """Deterministic offline similarity provider."""

    def score(self, left: str, right: str) -> float:
        return 0.9 if left and right and left[0] == right[0] else 0.2


def main() -> None:
    engine = ChunkEngine()
    result = engine.execute(
        TEXT,
        Policy.from_file(POLICIES / "three_level.yaml"),
        provider=DemoProvider(),
    )
    for c in result.chunks:
        if c.level == 0:
            print(f"L0 {c.chunk_id} [{c.start_offset},{c.end_offset}) {c.content!r}")
        elif c.level == 1:
            bs = c.strategy_metadata["boundary_score"]
            print(
                f"  L1 {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"bs={bs} {c.content!r}"
            )
        else:
            print(
                f"    L2 {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"{c.content!r}"
            )
    print(f"\nflat view: {len(result.chunks)} chunks total")


if __name__ == "__main__":
    main()
