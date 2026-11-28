"""单层语义切分：相邻句子相似度低于阈值就切一刀。

演示要点：
- 引擎不做 embedding，相似度完全由注入的 SimilarityProvider 计算；
- 这里用确定性的假 Provider 代替真实模型，保证离线可运行、结果可复现；
- 真实部署时把 DemoProvider 换成调用 embedding 服务的实现即可，引擎代码不变。
"""

import sys
from pathlib import Path

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

# 前两句谈苹果、第三句转到香蕉（仍属水果话题）、后两句是微积分——
# 相似度在话题切换处应变低，触发切块边界。
TEXT = "苹果很甜。苹果是水果。香蕉也是水果。微积分很难。导数是微积分的基础。"

POLICIES = Path(__file__).parent / "policies"


class DemoProvider:
    """假 Provider：相邻单元首字相同则相似度 0.9，否则 0.2。

    真实实现通常是把两个文本传给 embedding 模型再算余弦相似度；
    这里用"首字相同"模拟"话题相同"，只是为了让示例离线可跑。
    """

    def score(self, left: str, right: str) -> float:
        return 0.9 if left and right and left[0] == right[0] else 0.2

    def score_batch(self, pairs):
        # 可选的批量接口：实现了它，引擎会把所有相邻对一次传入，
        # 对真实服务意味着一次 RPC 代替逐对调用。
        return [self.score(left, right) for left, right in pairs]


def main() -> None:
    engine = ChunkEngine()
    # semantic.yaml 的关键参数：
    #   threshold: 0.5         —— 相似度低于它就判为话题边界
    #   chunk_size: 50         —— 长度兜底，语义块超长会按 recursive 再切
    #   unit_separators: ["。] —— 语义单元按句号切，单元本身不可再拆
    # provider 不进 Policy（Policy 是可移植的配置，Provider 是运行环境的一部分），
    # 所以它在每次 execute() 时注入。
    result = engine.execute(
        TEXT,
        Policy.from_file(POLICIES / "semantic.yaml"),
        provider=DemoProvider(),
    )
    for c in result.chunks:
        # boundary_score 是导致这个块"开始"的那条边界的相似度：
        # 第一个块没有前驱边界，所以是 None；之后的块分数越低说明话题切得越坚决。
        print(
            f"{c.chunk_id} [{c.start_offset},{c.end_offset}) "
            f"boundary_score={c.strategy_metadata['boundary_score']} :: {c.content!r}"
        )


if __name__ == "__main__":
    main()
