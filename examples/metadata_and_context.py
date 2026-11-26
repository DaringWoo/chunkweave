"""Metadata generation: fixed values, context sources, and include flags.

Every chunk carries system attributes (chunk_id, offsets, ...) regardless of
include flags; the flags only control what is *copied into* ``metadata``,
which is what vector stores typically index.
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
    document_id: {source: context.document_id}   # runtime value per call
    source_lang: {value: zh}                      # fixed value for all calls
    tenant: {source: context.tenant}
  include:
    strategy: true       # copy strategy/strategy_metadata into metadata
    organization: true   # copy parent_id/level/sequence/level_name
"""


def main() -> None:
    engine = ChunkEngine()
    policy = Policy.from_yaml(POLICY_YAML)

    # Same policy, two tenants: context decides the business metadata.
    for tenant, doc in [("acme", "doc-1"), ("globex", "doc-2")]:
        result = engine.execute(
            TEXT, policy, context={"document_id": doc, "tenant": tenant}
        )
        print(f"--- tenant={tenant} ---")
        for c in result.chunks[:2]:
            print(f"{c.chunk_id} {c.content!r}")
            print(f"  metadata = {c.metadata}")
    print()

    # Turn both include flags off: attributes stay on the chunk,
    # but metadata only carries the declared business fields.
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
    print(f"chunk attrs intact: level={c.level} sequence={c.sequence} "
          f"strategy={c.strategy}")
    print(f"metadata = {c.metadata}")


if __name__ == "__main__":
    main()
