"""单层递归切分：按分隔符优先级拆分的中文小说文本。

演示要点：
- recursive 按 separators 列表的顺序优先用前面的分隔符切；
- 分隔符既可以是字面字符串，也可以是正则（见 novel_regex.yaml）；
- keep_separator 控制分隔符归属前一块还是后一块；
- metadata 的 source 字段演示了如何从执行时的 context 里取值。
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

# 两章小说片段：章标题、空行分段、句号结尾，适合观察分隔符优先级。
TEXT = (
    "第一章 风起\n\n"
    "夜色降临，小镇灯火渐熄。远处传来汽笛声，惊起一片飞鸟。\n"
    "第二章 暗涌\n\n"
    "河水无声地流淌。没有人注意到桥下的影子在移动，直到脚步声越来越近。"
)

POLICIES = Path(__file__).parent / "policies"

# novel.yaml 里 chapter_title 声明为 {source: context.chapter.title}：
# Policy 只声明"从哪里来"，具体值在每次执行时由 context 提供。
# 同一份 Policy 换一个 context 就能标注不同的章节名。
CONTEXT = {"chapter": {"title": "风起"}}


def main() -> None:
    engine = ChunkEngine()

    # ---- 第一部分：字面分隔符 ----
    # novel.yaml 的 separators 是 ["\n\n", "\n", "。", "，", ""]：
    # 先按空行（\n\n）拆大块，块仍超长再退到换行、句号、逗号，
    # 最后的空字符串是字符级兜底，保证任何文本都能切到 chunk_size 以内。
    result = engine.execute(
        TEXT, Policy.from_file(POLICIES / "novel.yaml"), context=CONTEXT
    )
    print("=== literal separators ===")
    for c in result.chunks:
        # recursive 的 strategy_metadata 记录每个块实际用到了哪个分隔符、
        # 它在 separators 列表里的层级（0 最优先）。
        s = c.strategy_metadata
        print(
            f"{c.chunk_id} [{c.start_offset},{c.end_offset}) "
            f"sep={s['separator_used']!r} lvl={s['separator_level']} :: {c.content!r}"
        )

    # ---- 第二部分：正则分隔符 ----
    # novel_regex.yaml 用正则匹配"第X章"这样的章标题，
    # 并设置 keep_separator="next"：标题文字归入后一块，
    # 这样每个 Chunk 都以章标题开头，而不是以上一章的残句开头。
    headed = engine.execute(
        TEXT, Policy.from_file(POLICIES / "novel_regex.yaml"), context=CONTEXT
    )
    print("\n=== regex chapter separator (keep_separator='next') ===")
    for c in headed.chunks:
        print(f"{c.chunk_id} [{c.start_offset},{c.end_offset}) :: {c.content!r}")


if __name__ == "__main__":
    main()
