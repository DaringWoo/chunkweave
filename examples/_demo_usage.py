"""chunkweave 用法速览：从最简单到最完整的 6 种用法。

1) 直接使用切块器（不用引擎）        4) 两层流水线
2) 加载 Policy 文件执行              5) 注册自定义策略
3) 内联 YAML 构建 Policy             6) semantic + 注入 Provider
"""

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
    """统一打印一批 Chunk 的关键字段。"""
    print(f"--- {title} ---")
    for c in chunks:
        print(f"{c.chunk_id} L{c.level} [{c.start_offset},{c.end_offset}) {c.content!r}")
    print()


# ---------------------------------------------------------------------------
# 1) 绕过引擎，直接用切块器：参数模型进、ChunkSpan 出，全程有类型。
#    适合单元测试策略行为，或者只要切分、不要编号/元数据的场景。
#    注意此时拿到的是 ChunkSpan 而不是 Chunk——没有 chunk_id/level，
#    那些是引擎在组织阶段赋予的。
# ---------------------------------------------------------------------------
spans = RecursiveChunker(RecursiveParams(chunk_size=40)).chunk(TEXT)
print("--- 1) RecursiveChunker directly ---")
for s in spans:
    print(f"[{s.start_offset},{s.end_offset}) {s.content!r}")
print()

engine = ChunkEngine()

# ---------------------------------------------------------------------------
# 2) 声明式主路径：Policy 文件 + execute()。
#    novel.yaml 里的 chapter_title 声明为 source: context.chapter.title，
#    所以执行时要传 context；metadata 会包含固定值和动态值。
# ---------------------------------------------------------------------------
r = engine.execute(
    TEXT,
    Policy.from_file(POLICIES / "novel.yaml"),
    context={"chapter": {"title": "风起"}},
)
show(r.chunks, "2) execute + policy file")
print("metadata:", r.chunks[0].metadata, "\n")

# ---------------------------------------------------------------------------
# 3) 同一份 Policy 也可以从内联 YAML 字符串构建。
#    from_yaml 在加载时就做结构和语义校验——传错在这里就会抛错，
#    而不是等到 execute() 才暴露。
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 4) 两层流水线：第 0 层 recursive 切大段，第 1 层 sliding_window 滑窗。
#    结果是扁平列表：父块子块都在里面，用 parent_id 重建层级。
#    元数据字段在 metadata.fields 里统一定义，而不是按层配置。
# ---------------------------------------------------------------------------
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
      # 层级自身的标注走 metadata.fields，层级配置里没有元数据键
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


# ---------------------------------------------------------------------------
# 5) 自定义策略：声明参数模型 + 实现 chunk() + register 三步。
# ---------------------------------------------------------------------------
class WordsParams(BaseModel):
    """"words" 策略的参数 Schema；extra="forbid" 让未知参数直接报错。"""

    model_config = ConfigDict(extra="forbid")

    max_words: StrictInt = Field(default=10, gt=0)


class WordChunker:
    """按字符数分组的极简切块器（示意用，并非真按词）。

    契约：chunk(text) 返回 ChunkSpan 列表，Offset 相对于传入 text。
    """

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


# 工厂签名固定为 (params, provider)：params 是校验后的 WordsParams 实例；
# 本策略不需要 provider，忽略第二个参数。
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


# ---------------------------------------------------------------------------
# 6) semantic：Provider 不进 Policy，按次注入。
#    这里用 bigram Jaccard 相似度做离线演示——真实的 Provider 会调 embedding
#    模型，但引擎看到的一样只是 [0, 1] 的分数。
# ---------------------------------------------------------------------------
class BigramJaccard:
    """用字符 bigram 的 Jaccard 相似度模拟语义相似度。"""

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
# boundary_score 是语义边界的"力度"：分数越低，那一刀切得越坚决；
# 第一个块没有前驱边界，固定为 None。
print(
    "boundary scores:",
    [c.strategy_metadata["boundary_score"] for c in sem.chunks],
)
