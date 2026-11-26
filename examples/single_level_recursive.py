"""Single level + recursive strategy with Chinese and regex separators."""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "第一章 风起\n\n"
    "夜色降临，小镇灯火渐熄。远处传来汽笛声，惊起一片飞鸟。\n"
    "第二章 暗涌\n\n"
    "河水无声地流淌。没有人注意到桥下的影子在移动，直到脚步声越来越近。"
)

POLICIES = Path(__file__).parent / "policies"

# ``source`` fields resolve from the per-execution context.
CONTEXT = {"chapter": {"title": "风起"}}


def main() -> None:
    engine = ChunkEngine()
    # Literal separators for paragraphs/sentences.
    result = engine.execute(
        TEXT, Policy.from_file(POLICIES / "novel.yaml"), context=CONTEXT
    )
    print("=== literal separators ===")
    for c in result.chunks:
        s = c.strategy_metadata
        print(
            f"{c.chunk_id} [{c.start_offset},{c.end_offset}) "
            f"sep={s['separator_used']!r} lvl={s['separator_level']} :: {c.content!r}"
        )

    headed = engine.execute(
        TEXT, Policy.from_file(POLICIES / "novel_regex.yaml"), context=CONTEXT
    )
    print("\n=== regex chapter separator (keep_separator='next') ===")
    for c in headed.chunks:
        print(f"{c.chunk_id} [{c.start_offset},{c.end_offset}) :: {c.content!r}")


if __name__ == "__main__":
    main()
