"""Hierarchical: recursive (paragraphs) -> sliding_window (fixed windows)."""

import sys

from chunkweave import ChunkEngine

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "神经网络由多层神经元构成，每层学习不同抽象级别的特征。"
    "训练通过反向传播完成，梯度逐层回传。\n\n"
    "Transformer 引入自注意力机制，彻底改变了序列建模方式。"
    "其核心是查询、键、值三者的点积注意力。\n\n"
    "大语言模型在此基础上堆叠数十层，参数规模达到千亿级。"
)


def main() -> None:
    engine = ChunkEngine()
    result = engine.chunk(
        TEXT,
        {
            "organization": "hierarchical",
            "levels": [
                {
                    "name": "paragraph",
                    "strategy": "recursive",
                    "config": {"chunk_size": 500, "separators": ["\n\n"]},
                    "metadata": {"granularity": "paragraph"},
                },
                {
                    "name": "window",
                    "strategy": "sliding_window",
                    "config": {"chunk_size": 25, "overlap": 5},
                },
            ],
            "custom": {"corpus": "nlp-intro"},
        },
    )
    for node in result.tree():
        p = node.chunk
        print(f"[paragraph] {p.chunk_id} [{p.start_offset},{p.end_offset}) {p.content[:20]!r}…")
        for child in node.children:
            c = child.chunk
            print(
                f"  └ {c.chunk_id} [{c.start_offset},{c.end_offset}) "
                f"seq={c.metadata.organization['sequence']} {c.content!r}"
            )
    print(f"\nflat view: {len(result.chunks)} chunks total")


if __name__ == "__main__":
    main()
