"""Two levels: recursive (Markdown sections) -> sliding_window (windows)."""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "# 背景\n"
    "神经网络由多层神经元构成，每层学习不同抽象级别的特征。"
    "训练通过反向传播完成，梯度逐层回传。\n\n"
    "## 注意力\n"
    "Transformer 引入自注意力机制，彻底改变了序列建模方式。"
    "其核心是查询、键、值三者的点积注意力。\n\n"
    "# 规模\n"
    "大语言模型在此基础上堆叠数十层，参数规模达到千亿级。"
)

POLICIES = Path(__file__).parent / "policies"


def main() -> None:
    engine = ChunkEngine()
    result = engine.execute(TEXT, Policy.from_file(POLICIES / "markdown.yaml"))
    for c in result.chunks:
        if c.level == 0:
            print(
                f"[section] {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"{c.content[:20]!r}…"
            )
        else:
            print(
                f"  └ {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"seq={c.sequence} parent={c.parent_id} {c.content!r}"
            )
    print(f"\nflat view: {len(result.chunks)} chunks total")


if __name__ == "__main__":
    main()
