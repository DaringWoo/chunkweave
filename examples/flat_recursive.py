"""Flat organization + recursive strategy with Chinese and regex separators."""

import re
import sys

from chunkweave import ChunkEngine

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "第一章 风起\n\n"
    "夜色降临，小镇灯火渐熄。远处传来汽笛声，惊起一片飞鸟。\n"
    "第二章 暗涌\n\n"
    "河水无声地流淌。没有人注意到桥下的影子在移动，直到脚步声越来越近。"
)


def main() -> None:
    engine = ChunkEngine()
    # Literal separators for paragraphs/sentences + a regex for chapter heads.
    result = engine.chunk(
        TEXT,
        {
            "organization": "flat",
            "strategy": "recursive",
            "config": {
                "chunk_size": 40,
                "separators": ["\n\n", "\n", "。", "，", ""],
            },
        },
    )
    print("=== literal separators ===")
    for c in result.chunks:
        s = c.metadata.strategy
        print(
            f"{c.chunk_id} [{c.start_offset},{c.end_offset}) "
            f"sep={s['separator_used']!r} lvl={s['separator_level']} :: {c.content!r}"
        )

    headed = engine.chunk(
        TEXT,
        {
            "organization": "flat",
            "strategy": "recursive",
            "config": {
                "chunk_size": 45,
                "separators": [re.compile(r"第[一二三四五六七八九十]+章")],
                "keep_separator": "next",
            },
        },
    )
    print("\n=== regex chapter separator (keep_separator='next') ===")
    for c in headed.chunks:
        print(f"{c.chunk_id} [{c.start_offset},{c.end_offset}) :: {c.content!r}")


if __name__ == "__main__":
    main()
