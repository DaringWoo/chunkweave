"""Quick tour of chunkweave usage patterns, simple to advanced."""

import sys
from collections.abc import Sequence
from typing import ClassVar

from chunkweave import (
    Chunk,
    ChunkEngine,
    ChunkMetadata,
    FlatConfig,
    RecursiveConfig,
    chunk_id_for,
)
from chunkweave.strategies import LegacyRecursiveChunker

sys.stdout.reconfigure(encoding="utf-8")

TEXT = "第一章 风起\n\n夜色降临，小镇灯火渐熄。远处传来汽笛声，惊起一片飞鸟。\n第二章 暗涌\n\n河水无声地流淌。没有人注意到桥下的影子在移动。"


def show(chunks, title):
    print(f"--- {title} ---")
    for c in chunks:
        org = c.metadata.organization
        lvl = f"L{org['level']} " if org else ""
        print(f"{c.chunk_id} {lvl}[{c.start_offset},{c.end_offset}) {c.content!r}")
    print()


# 1) Direct chunker — no engine, no dict, fully typed
chunks = LegacyRecursiveChunker(RecursiveConfig(chunk_size=40)).chunk(TEXT)
show(chunks, "1) RecursiveChunker directly")

engine = ChunkEngine()

# 2) Flat via dict config (the JSON-serializable form)
r = engine.chunk(
    TEXT,
    {
        "organization": "flat",
        "strategy": "recursive",
        "config": {"chunk_size": 40},
        "custom": {"doc": "demo"},
    },
)
show(r.chunks, "2) engine + flat dict")
print("custom metadata:", r.chunks[0].metadata.custom, "\n")

# 3) Same thing via config object — validation at construction
cfg = FlatConfig(strategy="recursive", config={"chunk_size": 40})
show(engine.chunk(TEXT, cfg).chunks, "3) engine + FlatConfig object")

# 4) Hierarchical: chapters -> sentences
hier = engine.chunk(
    TEXT,
    {
        "organization": "hierarchical",
        "levels": [
            {"strategy": "recursive", "config": {"chunk_size": 60}, "metadata": {"kind": "chapter"}},
            {"strategy": "sliding_window", "config": {"chunk_size": 20, "overlap": 5}},
        ],
    },
)
show(hier.chunks, "4) hierarchical two levels")
for root in hier.tree():
    print(f"tree root {root.chunk.chunk_id}: {len(root.children)} children")
print()


# 5) Custom strategy via register()
class WordChunker:
    metadata_keys: ClassVar[frozenset[str]] = frozenset({"word_count"})

    def __init__(self, config):
        self.max_words = config.get("max_words", 10)

    def chunk(self, text: str) -> Sequence[Chunk]:
        out, start, i = [], 0, 0
        while start < len(text):
            end = min(start + self.max_words, len(text))
            out.append(
                Chunk(
                    chunk_id=chunk_id_for(i),
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    metadata=ChunkMetadata(strategy={"word_count": end - start}),
                )
            )
            i += 1
            start = end
        return out


engine.register("words", lambda cfg: WordChunker(cfg))
show(
    engine.chunk(
        TEXT, {"organization": "flat", "strategy": "words", "config": {"max_words": 12}}
    ).chunks,
    "5) custom 'words' strategy",
)

# 6) Semantic with an injected provider
class BigramJaccard:
    def score(self, left: str, right: str) -> float:
        a = {left[i : i + 2] for i in range(len(left) - 1)} or {left}
        b = {right[i : i + 2] for i in range(len(right) - 1)} or {right}
        return len(a & b) / len(a | b)

engine.set_provider(BigramJaccard())
sem = engine.chunk(
    TEXT,
    {
        "organization": "flat",
        "strategy": "semantic",
        "config": {"threshold": 0.15, "chunk_size": 60},
    },
)
show(sem.chunks, "6) semantic + injected provider")
print("boundary scores:", [c.metadata.strategy["boundary_score"] for c in sem.chunks])
