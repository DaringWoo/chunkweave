"""自定义切块策略：注册一个按词数分组的 "words" 策略。

演示要点：
- register(name, factory, *, params_model) 三要素：名字、工厂、参数模型；
- 参数模型用 Pydantic 声明，未知参数会被拒绝（extra="forbid"）；
- 工厂签名固定为 factory(params, provider)：params 是校验后的模型实例，
  provider 只有声明 requires_provider=True 的策略才用得到；
- 自定义策略和内置策略一样，可以出现在 pipeline 的任何层级。
"""

import re
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from chunkweave import ChunkEngine, ChunkSpan, Policy

sys.stdout.reconfigure(encoding="utf-8")

POLICIES = Path(__file__).parent / "policies"


class WordsParams(BaseModel):
    """"words" 策略的参数 Schema。

    注册时传入这个模型，引擎就会用它校验 YAML 里的 params：
    类型错误、未知键都会在编译前变成带路径的报错，而不是切块时才炸。
    """

    model_config = ConfigDict(extra="forbid")

    max_words: StrictInt = Field(default=4, gt=0)


class WordChunker:
    """第三方切块器：每最多 max_words 个词为一组。

    契约只有一个方法：chunk(text) -> list[ChunkSpan]。
    每个 ChunkSpan 的 Offset 相对于传入 text 的起点——
    多层流水线里传给下层的是父块内容，引擎负责换算全局 Offset。

    注意：每块从某词开头到最后一个词结尾，组间空白不被任何块覆盖
    （效果类似 keep_separator="none"），策略有权这样做。
    """

    def __init__(self, params: WordsParams) -> None:
        self.max_words = params.max_words

    def chunk(self, text: str) -> list[ChunkSpan]:
        # \S+ 匹配每个非空白词，span() 给出它在原文中的 [start, end)。
        word_spans = [m.span() for m in re.finditer(r"\S+", text)]
        spans: list[ChunkSpan] = []
        for i in range(0, len(word_spans), self.max_words):
            group = word_spans[i : i + self.max_words]
            start, end = group[0][0], group[-1][1]
            spans.append(
                ChunkSpan(
                    content=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    # strategy_metadata 是策略的私有便签，键值自定；
                    # include.strategy 开启时会被复制进业务 metadata。
                    strategy_metadata={"word_count": len(group)},
                )
            )
        return spans


def main() -> None:
    engine = ChunkEngine()
    # 注册后 "words" 与内置策略地位相同：可以在 YAML 里按名引用，
    # 重名注册默认会拒绝（除非显式 replace=True）。
    engine.register(
        "words",
        lambda params, _provider: WordChunker(params),
        params_model=WordsParams,
    )
    # words.yaml 把这个自定义策略放在第 0 层，
    # 第 1 层用内置 sliding_window 继续细切——两者可以自由组合。
    result = engine.execute(
        "the quick brown fox jumps over the lazy dog",
        Policy.from_file(POLICIES / "words.yaml"),
    )
    for c in result.chunks:
        print(
            f"{c.chunk_id} L{c.level} seq={c.sequence} "
            f"[{c.start_offset},{c.end_offset}) {c.content!r} "
            f"strat={c.strategy_metadata}"
        )


if __name__ == "__main__":
    main()
