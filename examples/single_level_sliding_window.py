"""单层滑动窗口：最简单的切块方式。

演示要点：
- sliding_window 按固定长度（chunk_size）切窗口，相邻窗口重叠 overlap 个字符；
- 窗口长度以 Unicode 码点计，中英文混排时行为一致；
- 每个 Chunk 的 strategy_metadata 里有窗口序号和它与前一窗口的重叠长度。
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

# Windows 控制台默认编码可能不是 UTF-8，强制切换以免中文输出乱码。
sys.stdout.reconfigure(encoding="utf-8")

# 三个英文全字母句（pangram），总长约 140 字符，
# 按 chunk_size=30 / overlap=8 会切出多个窗口。
TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump!"
)

# 示例 Policy 统一放在 examples/policies/ 下，便于对照阅读 YAML 与效果。
POLICIES = Path(__file__).parent / "policies"


def main() -> None:
    engine = ChunkEngine()
    # sliding.yaml 的关键内容：
    #   strategy: sliding_window
    #   params: {chunk_size: 30, overlap: 8}
    #   metadata.fields 里声明了两个固定值字段 source/lang，
    #   会出现在每个 Chunk 的 metadata 里。
    policy = Policy.from_file(POLICIES / "sliding.yaml")
    result = engine.execute(TEXT, policy)

    for c in result.chunks:
        # strategy_metadata 由策略自己填写，sliding_window 提供：
        #   window_index  —— 这是第几个窗口（从 0 开始）
        #   overlap_size  —— 本窗口与前一个窗口重叠的字符数（首窗口为 0）
        # 用 start/end Offset 可以验证：相邻窗口起点之差 = chunk_size - overlap。
        print(
            f"{c.chunk_id} [{c.start_offset:>3},{c.end_offset:>3}) "
            f"win={c.strategy_metadata['window_index']} "
            f"ov={c.strategy_metadata['overlap_size']} :: {c.content!r}"
        )

    # include.strategy / include.organization 默认开启，
    # 所以 metadata 里除了 Policy 声明的业务字段（source/lang），
    # 还有复制进来的 strategy、strategy_metadata、level、sequence 等。
    print(f"\n{len(result.chunks)} chunks, metadata={result.chunks[0].metadata}")


if __name__ == "__main__":
    main()
