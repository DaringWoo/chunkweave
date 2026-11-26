"""Pre-flight validation and the compiled ExecutionPlan.

``validate()`` checks a policy without executing it; ``compile()`` exposes
the Execution IR — including the content-addressed ``policy_hash`` used for
traceability — so tooling can inspect what *would* run.
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

    # 1) validate() returns None on success, raises a typed error otherwise.
    engine.validate(policy)
    print("validate: OK")

    # 2) compile() shows the plan: strategies, filled-in defaults, fields.
    plan = engine.compile(policy)
    print(f"policy_hash: {plan.policy_hash}")
    for level in plan.levels:
        print(
            f"level[{level.index}] {level.name}: strategy={level.strategy} "
            f"params={level.params} requires_provider={level.requires_provider}"
        )
    for field in plan.metadata_fields:
        print(f"metadata field {field.name}: kind={field.kind} path={field.path}")

    # 3) The hash is content-addressed: same content, same hash —
    #    touching one param (or one metadata field) changes it.
    same = engine.compile(Policy.from_yaml(POLICY_YAML))
    changed = engine.compile(
        Policy.from_yaml(POLICY_YAML.replace("overlap: 3", "overlap: 4"))
    )
    print(f"\nsame content      -> same hash: {same.policy_hash == plan.policy_hash}")
    print(f"overlap 3 -> 4    -> same hash: {changed.policy_hash == plan.policy_hash}")

    # 4) validate() failing fast on an unknown strategy.
    bad = Policy.from_yaml(
        POLICY_YAML.replace('strategy: recursive', 'strategy: typo_strategy')
    )
    try:
        engine.validate(bad)
    except ChunkweaveError as e:
        print(f"\nvalidate rejects: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
