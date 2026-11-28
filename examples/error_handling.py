"""错误处理：每种失败都有类型、路径、原因三要素。

演示要点：
- 所有错误都继承 ChunkweaveError，可以按基类统一捕获，也可按子类细分；
- PolicyValidationError 系（含 UnregisteredStrategyError）带 path/reason，
  path 与 YAML 中的位置一一对应，如 pipeline.levels[0].params.xxx；
- ContextResolutionError 带 field/path/reason，指出哪个字段的哪条路径缺失；
- HTTP 服务的错误响应正是由这些属性序列化而来——这里看到的就是 API 里看到的。
"""

import sys

from chunkweave import ChunkEngine, Policy
from chunkweave.models import (
    ContextResolutionError,
    PolicyLoadError,
    PolicyValidationError,
    ProviderMissingError,
)

sys.stdout.reconfigure(encoding="utf-8")

TEXT = "苹果富含维生素。香蕉也很好吃。"

VALID = """
api_version: chunkweave/v1
policy: {id: err-demo, name: 错误演示, version: 1.0.0}
pipeline:
  levels:
    - name: sentence
      strategy: recursive
      params: {chunk_size: 20}
metadata:
  fields:
    document_id: {source: context.document_id}
"""


def show(label, fn) -> None:
    """执行 fn 并按错误类型打印三要素；没报错说明示例本身写错了。"""
    try:
        fn()
        print(f"{label}: unexpectedly succeeded")
    except (PolicyLoadError, PolicyValidationError) as e:
        # PolicyLoadError 是加载期错误（YAML 语法、根类型），没有 path；
        # PolicyValidationError 是校验期错误，path/reason 都有。
        print(f"{label}: {type(e).__name__}")
        print(f"  path   = {getattr(e, 'path', None)}")
        print(f"  reason = {getattr(e, 'reason', str(e))}")
    except ContextResolutionError as e:
        print(f"{label}: {type(e).__name__}")
        print(f"  field={e.field} path={e.path} reason={e.reason}")
    except ProviderMissingError as e:
        print(f"{label}: {type(e).__name__}: {e}")


def main() -> None:
    engine = ChunkEngine()

    # 1) YAML 语法错误：加载阶段就失败，还未进入结构校验。
    show("malformed yaml", lambda: Policy.from_yaml("api_version: [unclosed"))

    # 2) 未注册的策略名：path 指向出错的那一层的 strategy 键，
    #    reason 列出当前可用的策略（含自定义注册的）。
    bad_strategy = VALID.replace("strategy: recursive", "strategy: nope")
    show(
        "unknown strategy",
        lambda: engine.execute(TEXT, Policy.from_yaml(bad_strategy)),
    )

    # 3) 参数名笔误：未知参数一律拒绝而不是静默忽略——
    #    否则 chunck_size 这种 typo 会让 chunk_size 悄悄用默认值。
    bad_param = VALID.replace("chunk_size: 20", "chunk_size: 20, chunck_size: 30")
    show(
        "typo in param key",
        lambda: engine.execute(TEXT, Policy.from_yaml(bad_param)),
    )

    # 4) 业务字段名撞上系统保留字段（level 等 11 个）：
    #    在加载时拒绝，与 include 开关无关——否则复制组织信息时会撞键。
    reserved = VALID.replace("document_id: {source:", "level: {source:")
    show(
        "reserved field name",
        lambda: Policy.from_yaml(reserved),
    )

    # 5) context 缺少 source 声明的路径：明确报错，绝不静默填 None。
    #    （可选字段需要在 DSL 中显式声明，本例的 document_id 是必填。）
    show(
        "missing context path",
        lambda: engine.execute(TEXT, Policy.from_yaml(VALID), context={}),
    )

    # 6) semantic 策略但没传 provider：在开始切块前就失败，
    #    不会切到一半才炸。这也是"Provider 不进 Policy"的必然结果——
    #    配置里没有 provider，运行时又没人给，只能报错。
    semantic = VALID.replace("strategy: recursive", "strategy: semantic").replace(
        "params: {chunk_size: 20}", "params: {chunk_size: 20, threshold: 0.5}"
    )
    show(
        "semantic, no provider",
        lambda: engine.execute(TEXT, Policy.from_yaml(semantic)),
    )


if __name__ == "__main__":
    main()
