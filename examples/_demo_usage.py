"""Quick tour of chunkweave usage patterns, simple to advanced."""

import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from chunkweave import ChunkEngine, ChunkSpan, Policy, RecursiveParams
from chunkweave.strategies import RecursiveChunker

sys.stdout.reconfigure(encoding="utf-8")

TEXT = (
    "第一章 风起\n\n"
    "夜色降临，小镇灯火渐熄。远处传来汽笛声，惊起一片飞鸟。\n"
    "第二章 暗涌\n\n"
    "河水无声地流淌。没有人注意到桥下的影子在移动。"
)

POLICIES = Path(__file__).parent / "policies"


def show(chunks, title):
    print(f"--- {title} ---")
    for c in chunks:
        print(f"{c.chunk_id} L{c.level} [{c.start_offset},{c.end_offset}) {c.content!r}")
    print()


# 1) Direct chunker — params model in, ChunkSpan out, fully typed
spans = RecursiveChunker(RecursiveParams(chunk_size=40)).chunk(TEXT)
print("--- 1) RecursiveChunker directly ---")
for s in spans:
    print(f"[{s.start_offset},{s.end_offset}) {s.content!r}")
print()

engine = ChunkEngine()

# 2) Single level via a Policy file (the declarative form)
r = engine.execute(
    TEXT,
    Policy.from_file(POLICIES / "novel.yaml"),
    context={"chapter": {"title": "风起"}},
)
show(r.chunks, "2) execute + policy file")
print("metadata:", r.chunks[0].metadata, "\n")

# 3) Same thing built from a YAML string — validation at load time
policy = Policy.from_yaml(
    """
api_version: chunkweave/v1
policy: {id: demo-inline, name: 内联, version: 1.0.0}
pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params: {chunk_size: 40}
"""
)
show(engine.execute(TEXT, policy).chunks, "3) execute + inline Policy")

# 4) Two levels: sections -> windows
hier = engine.execute(
    TEXT,
    Policy.from_yaml(
        """
api_version: chunkweave/v1
policy: {id: demo-two, name: 两层, version: 1.0.0}
pipeline:
  levels:
    - name: chapter
      strategy: recursive
      params: {chunk_size: 60}
      # level metadata comes from metadata.fields, not per-level keys
    - name: window
      strategy: sliding_window
      params: {chunk_size: 20, overlap: 5}
metadata:
  fields:
    kind: {value: chapter}
"""
    ),
)
show(hier.chunks, "4) two-level pipeline")
by_id = {c.chunk_id: c for c in hier.chunks}
roots = [c for c in hier.chunks if c.parent_id is None]
for root in roots:
    kids = [c for c in hier.chunks if c.parent_id == root.chunk_id]
    print(f"root {root.chunk_id}: {len(kids)} children")
print()


# 5) Custom strategy via register(..., params_model=...)
class WordsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_words: StrictInt = Field(default=10, gt=0)


class WordChunker:
    def __init__(self, params: WordsParams) -> None:
        self.max_words = params.max_words

    def chunk(self, text: str) -> list[ChunkSpan]:
        out, start, i = [], 0, 0
        while start < len(text):
            end = min(start + self.max_words, len(text))
            out.append(
                ChunkSpan(
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    strategy_metadata={"word_count": end - start},
                )
            )
            i += 1
            start = end
        return out


engine.register(
    "words", lambda params, _p: WordChunker(params), params_model=WordsParams
)
words_policy = Policy.from_yaml(
    """
api_version: chunkweave/v1
policy: {id: demo-words, name: 自定义, version: 1.0.0}
pipeline:
  levels:
    - name: words
      strategy: words
      params: {max_words: 12}
"""
)
show(
    engine.execute(TEXT, words_policy).chunks,
    "5) custom 'words' strategy",
)

# 6) Semantic with a provider injected per execute() call
class BigramJaccard:
    def score(self, left: str, right: str) -> float:
        a = {left[i : i + 2] for i in range(len(left) - 1)} or {left}
        b = {right[i : i + 2] for i in range(len(right) - 1)} or {right}
        return len(a & b) / len(a | b)


sem = engine.execute(
    TEXT,
    Policy.from_file(POLICIES / "semantic.yaml"),
    provider=BigramJaccard(),
)
show(sem.chunks, "6) semantic + execute(provider=...)")
print(
    "boundary scores:",
    [c.strategy_metadata["boundary_score"] for c in sem.chunks],
)
