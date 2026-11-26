"""Typed errors: every failure mode carries a type, a path, and a reason.

Applications can catch the base ``ChunkweaveError`` or specific subclasses;
``path`` points at the offending policy/context location, which is what the
HTTP service surfaces in its error responses too.
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
    try:
        fn()
        print(f"{label}: unexpectedly succeeded")
    except (PolicyLoadError, PolicyValidationError) as e:
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

    # 1) Malformed YAML — loading fails before any validation.
    show("malformed yaml", lambda: Policy.from_yaml("api_version: [unclosed"))

    # 2) Unknown strategy — caught at validation, path points at the level.
    bad_strategy = VALID.replace("strategy: recursive", "strategy: nope")
    show(
        "unknown strategy",
        lambda: engine.execute(TEXT, Policy.from_yaml(bad_strategy)),
    )

    # 3) Unknown params are rejected, not silently ignored.
    bad_param = VALID.replace("chunk_size: 20", "chunk_size: 20, chunck_size: 30")
    show(
        "typo in param key",
        lambda: engine.execute(TEXT, Policy.from_yaml(bad_param)),
    )

    # 4) A business field colliding with a reserved system name.
    reserved = VALID.replace("document_id: {source:", "level: {source:")
    show(
        "reserved field name",
        lambda: Policy.from_yaml(reserved),
    )

    # 5) Missing context path — execution fails, nothing is silently None.
    show(
        "missing context path",
        lambda: engine.execute(TEXT, Policy.from_yaml(VALID), context={}),
    )

    # 6) semantic without a provider — fails before any chunking starts.
    semantic = VALID.replace("strategy: recursive", "strategy: semantic").replace(
        "params: {chunk_size: 20}", "params: {chunk_size: 20, threshold: 0.5}"
    )
    show(
        "semantic, no provider",
        lambda: engine.execute(TEXT, Policy.from_yaml(semantic)),
    )


if __name__ == "__main__":
    main()
