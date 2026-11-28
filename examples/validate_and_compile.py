"""执行前检查：validate 预检 + compile 查看执行计划（Execution IR）。

演示要点：
- validate() 只校验不执行，失败时抛出带字段路径的类型化错误；
- compile() 返回 ExecutionPlan：一份纯数据、可序列化的执行计划，
  能看到每层策略、补齐默认值后的参数、以及内容寻址的 policy_hash；
- policy_hash 是追溯的锚点：内容相同 hash 相同，任何一处改动都会变。
"""

import sys

from chunkweave import ChunkEngine, Policy
from chunkweave.models import ChunkweaveError

sys.stdout.reconfigure(encoding="utf-8")

POLICY_YAML = """
api_version: chunkweave/v1
policy: {id: compile-demo, name: 编译演示, version: 1.0.0}
pipeline:
  levels:
    - name: parent
      strategy: recursive
      params: {chunk_size: 40}
    - name: child
      strategy: sliding_window
      params: {chunk_size: 15, overlap: 3}
metadata:
  fields:
    document_id: {source: context.document_id}
"""


def main() -> None:
    engine = ChunkEngine()
    policy = Policy.from_yaml(POLICY_YAML)

    # 1) validate() 成功时返回 None；失败抛出 PolicyValidationError 等类型化错误。
    #    适合在 CI 或配置上线前批量预检 Policy 文件。
    engine.validate(policy)
    print("validate: OK")

    # 2) compile() 把 Policy 编译成 Execution IR。
    #    注意 levels[*].params 里包含"补齐默认值后"的参数——
    #    YAML 里没写的项也能在这里看到生效值。
    plan = engine.compile(policy)
    print(f"policy_hash: {plan.policy_hash}")
    for level in plan.levels:
        print(
            f"level[{level.index}] {level.name}: strategy={level.strategy} "
            f"params={level.params} requires_provider={level.requires_provider}"
        )
    # 元数据字段也被编译成纯数据：kind 区分固定值/动态路径，
    # 动态路径已拆成段（如 ["context", "document_id"]）。
    for field in plan.metadata_fields:
        print(f"metadata field {field.name}: kind={field.kind} path={field.path}")

    # 3) policy_hash 按内容寻址：
    #    同样的内容再加载一次，hash 完全一致；
    #    只改一个参数（overlap 3 → 4），hash 就变。
    #    因此 hash 可以回答"两次执行用的是不是同一份配置"。
    same = engine.compile(Policy.from_yaml(POLICY_YAML))
    changed = engine.compile(
        Policy.from_yaml(POLICY_YAML.replace("overlap: 3", "overlap: 4"))
    )
    print(f"\nsame content      -> same hash: {same.policy_hash == plan.policy_hash}")
    print(f"overlap 3 -> 4    -> same hash: {changed.policy_hash == plan.policy_hash}")

    # 4) 拼错的策略名会在 validate 阶段被拦截，
    #    报错里列出当前可用的策略名，path 精确到出错的层级。
    bad = Policy.from_yaml(
        POLICY_YAML.replace('strategy: recursive', 'strategy: typo_strategy')
    )
    try:
        engine.validate(bad)
    except ChunkweaveError as e:
        print(f"\nvalidate rejects: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
