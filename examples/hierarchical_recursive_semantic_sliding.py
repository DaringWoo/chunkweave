"""Hierarchical: recursive -> semantic -> sliding_window (three levels)."""

import sys

from chunkweave import ChunkEngine

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "苹果富含维生素。苹果可以榨汁。香蕉也很好吃。"
    "微积分研究变化率。导数描述瞬时速度。积分计算面积。"
    "跑步有益健康。游泳锻炼全身。"
)


class DemoProvider:
    """Deterministic offline similarity provider."""

    def score(self, left: str, right: str) -> float:
        return 0.9 if left and right and left[0] == right[0] else 0.2


def main() -> None:
    engine = ChunkEngine()
    engine.set_provider(DemoProvider())
    result = engine.chunk(
        TEXT,
        {
            "organization": "hierarchical",
            "levels": [
                {
                    "name": "segment",
                    "strategy": "recursive",
                    "config": {"chunk_size": 40, "separators": ["。"]},
                },
                {
                    "name": "topic",
                    "strategy": "semantic",
                    "config": {"threshold": 0.5, "chunk_size": 30, "unit_separators": ["。"]},
                },
                {
                    "name": "detail",
                    "strategy": "sliding_window",
                    "config": {"chunk_size": 10},
                },
            ],
        },
    )
    for node in result.tree():
        p = node.chunk
        print(f"L0 {p.chunk_id} [{p.start_offset},{p.end_offset}) {p.content!r}")
        for n2 in node.children:
            c2 = n2.chunk
            bs = c2.metadata.strategy["boundary_score"]
            print(f"  L1 {c2.chunk_id} [{c2.start_offset},{c2.end_offset}) bs={bs} {c2.content!r}")
            for n3 in n2.children:
                c3 = n3.chunk
                print(f"    L2 {c3.chunk_id} [{c3.start_offset},{c3.end_offset}) {c3.content!r}")
    print(f"\nflat view: {len(result.chunks)} chunks total")


if __name__ == "__main__":
    main()
