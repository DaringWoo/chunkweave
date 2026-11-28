"""三层流水线：recursive → semantic → sliding_window 组合使用。

演示要点：
- 不同层级可以用不同策略，各层 params 独立；
- semantic 层需要在 execute() 时注入 provider，其它层不需要；
- 切块沿层级逐层细化：话题段 → 语义块 → 固定窗口。
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

# 三个话题混排：水果（3 句）→ 微积分（3 句）→ 运动（2 句）。
# 第 0 层先按 chunk_size 粗切，第 1 层 semantic 在内部找话题边界，
# 第 2 层把偏长的语义块切成固定窗口。
TEXT = (
    "苹果富含维生素。苹果可以榨汁。香蕉也很好吃。"
    "微积分研究变化率。导数描述瞬时速度。积分计算面积。"
    "跑步有益健康。游泳锻炼全身。"
)

POLICIES = Path(__file__).parent / "policies"


class DemoProvider:
    """确定性假 Provider：首字相同则相似度高（视为同话题）。

    多层流水线里只要有一层是 semantic，execute() 就必须传 provider；
    缺的話在开始切块前就会报 ProviderMissingError。
    """

    def score(self, left: str, right: str) -> float:
        return 0.9 if left and right and left[0] == right[0] else 0.2


def main() -> None:
    engine = ChunkEngine()
    result = engine.execute(
        TEXT,
        Policy.from_file(POLICIES / "three_level.yaml"),
        provider=DemoProvider(),
    )
    # 按层级缩进打印，直观看到"父块包含子块"的结构。
    # 同一篇文本在结果里出现多次（每层各一遍），这是分层切块的本质：
    # L0/L1 用于理解结构，L2（叶子层）通常才是入库检索的粒度。
    for c in result.chunks:
        if c.level == 0:
            print(f"L0 {c.chunk_id} [{c.start_offset},{c.end_offset}) {c.content!r}")
        elif c.level == 1:
            # bs 是 boundary_score：这个语义块由多强的边界开启，
            # 首块为 None。
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
