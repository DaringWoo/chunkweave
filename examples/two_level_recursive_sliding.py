"""两层流水线：先按 Markdown 章节粗切，再在每个章节内滑窗细切。

演示要点：
- pipeline.levels 的顺序就是层级关系：第 0 层是父、第 1 层是子；
- 每个父块独立进入下一层切块，子块不会跨越父块边界；
- ChunkResult 永远是扁平列表，父子关系靠 parent_id/level/sequence 表达；
- 子块的 start_offset/end_offset 已经换算成相对原文的全局 Offset。
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

# 一篇两级结构的 Markdown 短文：两个一级标题、一个二级标题。
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
    # markdown.yaml 的 pipeline 有两层：
    #   level 0: recursive  —— 按 Markdown 标题分隔符切出"章节"父块
    #   level 1: sliding_window —— 在每个章节内部按固定窗口细切
    result = engine.execute(TEXT, Policy.from_file(POLICIES / "markdown.yaml"))
    for c in result.chunks:
        if c.level == 0:
            # 父块：parent_id 为 None，内容是一整个章节
            print(
                f"[section] {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"{c.content[:20]!r}…"
            )
        else:
            # 子块：parent_id 指向所属章节，sequence 是它在父块内的序号。
            # 注意 Offset 是相对整篇原文的，不是相对父块的——
            # 引擎在组织阶段已把局部 Offset 换算成全局 Offset。
            print(
                f"  └ {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"seq={c.sequence} parent={c.parent_id} {c.content!r}"
            )
    # ChunkResult.chunks 同时包含父块和子块，是"扁平视图"：
    # 想做向量入库通常只取叶子层，做层级检索则两层都要。
    print(f"\nflat view: {len(result.chunks)} chunks total")


if __name__ == "__main__":
    main()
