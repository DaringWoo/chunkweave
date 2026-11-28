"""元数据生成：固定值、Context 动态取值、include 复制开关。

演示要点：
- metadata.fields 里每个字段二选一：value（固定值）或 source（运行时取值）；
- source 只声明路径，真正的值在每次 execute() 的 context 里给——
  同一份 Policy 因此能服务多篇文档、多个租户；
- include 开关控制"系统信息是否复制进 metadata"，而 Chunk 自身的属性
  （level/sequence/strategy 等）无论如何都完整保留。
  复制进 metadata 的意义：向量库一般只索引 metadata，过滤要靠它。
"""

import sys

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

TEXT = "苹果富含维生素。香蕉也很好吃。微积分研究变化率。导数是微积分的基础。"

POLICY_YAML = """
api_version: chunkweave/v1
policy: {id: meta-demo, name: 元数据演示, version: 1.0.0}
pipeline:
  levels:
    - name: sentence
      strategy: recursive
      params: {chunk_size: 20}
metadata:
  fields:
    document_id: {source: context.document_id}   # 运行时取值，每次执行可不同
    source_lang: {value: zh}                      # 固定值，所有执行都一样
    tenant: {source: context.tenant}
  include:
    strategy: true       # 把 strategy/strategy_metadata 复制进 metadata
    organization: true   # 把 parent_id/level/sequence/level_name 复制进 metadata
"""


def main() -> None:
    engine = ChunkEngine()
    policy = Policy.from_yaml(POLICY_YAML)

    # 同一份 Policy 执行两次，只是 context 不同：
    # document_id / tenant 随 context 变化，source_lang 固定为 zh。
    # 这正是"Policy 管规则、Context 管数据"的分工。
    for tenant, doc in [("acme", "doc-1"), ("globex", "doc-2")]:
        result = engine.execute(
            TEXT, policy, context={"document_id": doc, "tenant": tenant}
        )
        print(f"--- tenant={tenant} ---")
        for c in result.chunks[:2]:
            print(f"{c.chunk_id} {c.content!r}")
            print(f"  metadata = {c.metadata}")
    print()

    # 把两个 include 开关都关掉再跑一次（通过字符串替换快速构造变体）。
    no_include = Policy.from_yaml(
        POLICY_YAML.replace("strategy: true", "strategy: false").replace(
            "organization: true", "organization: false"
        )
    )
    result = engine.execute(
        TEXT, no_include, context={"document_id": "doc-1", "tenant": "acme"}
    )
    c = result.chunks[0]
    print("--- include flags off ---")
    # Chunk 对象本身的系统属性不受开关影响——不复制不等于丢失。
    print(f"chunk attrs intact: level={c.level} sequence={c.sequence} "
          f"strategy={c.strategy}")
    # metadata 只剩 Policy 显式声明的三个业务字段。
    print(f"metadata = {c.metadata}")


if __name__ == "__main__":
    main()
