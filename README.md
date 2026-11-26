# chunkweave

A declarative, policy-driven text chunking engine. You describe *what* you
want in a YAML Policy — pipeline levels, strategy parameters, metadata
rules — and the engine compiles it into an execution plan and produces
uniform `Chunk` objects with full traceability.

- **3 strategies**: `sliding_window`, `recursive`, `semantic`
  (provider-injected)
- **N-level pipelines**: every chunk is independently re-chunked by the next
  level — parent-child is the 2-level special case
- **Unified `Chunk` model**: system fields as attributes, strategy and
  business metadata as maps, global offsets
- **Traceability**: every `ChunkResult` carries `policy_id`,
  `policy_version`, `policy_hash`, `execution_id`, `engine_version` and
  `execution_time_ms`
- **Light core dependencies**: `pydantic` + `PyYAML`; the semantic
  similarity provider is injected per call via a protocol

> 中文概述：chunkweave 是一个声明式、Policy 驱动的文本切块引擎。用 YAML
> Policy 描述流水线层级、策略参数与元数据规则，引擎编译为执行计划后产出
> 统一的 Chunk。三种策略（滑动窗口、递归分隔符、语义注入）可任意组合成
> N 层流水线；执行结果带完整追溯信息。核心依赖仅 pydantic 与 PyYAML，
> 语义相似度由调用方按次注入。示例见 `examples/`，文档见 `docs/`。

**Scope**: chunkweave works on text that is already cleaned. It does not
parse documents, clean data, compute embeddings, talk to vector databases,
or implement RAG — bring your own text and provider.

## Install

```bash
pip install -e .            # from a checkout
pip install dist/chunkweave-0.1.0-py3-none-any.whl   # built wheel
```

Requires Python >= 3.11 and installs `pydantic>=2` and `PyYAML>=6`.

## Quick start

Write a Policy (`my_policy.yaml`):

```yaml
api_version: chunkweave/v1
policy:
  id: quickstart
  name: 快速上手
  version: 1.0.0
pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params: {chunk_size: 500}
    - name: window
      strategy: sliding_window
      params: {chunk_size: 200, overlap: 20}
metadata:
  fields:
    doc_id: {value: d1}                    # fixed value on every chunk
    tenant: {source: context.request.tenant}  # resolved from Context
```

Run it:

```python
from chunkweave import ChunkEngine, Policy

policy = Policy.from_file("my_policy.yaml")
# or: policy = Policy.from_yaml(yaml_string)

engine = ChunkEngine()
result = engine.execute(
    text,
    policy,
    context={"request": {"tenant": "acme"}},
    provider=None,  # only needed when a level requires one (e.g. semantic)
)

for c in result.chunks:
    print(c.chunk_id, c.level, c.sequence, c.parent_id,
          c.start_offset, c.end_offset, repr(c.content), c.metadata)

print(result.total, result.policy_id, result.policy_version,
      result.policy_hash, result.execution_id, result.execution_time_ms)
```

## Validate and compile

```python
engine.validate(policy)      # structural + semantic checks, returns None
plan = engine.compile(policy)  # serializable ExecutionPlan (Execution IR)
plan.model_dump_json()         # no runtime objects inside
```

Both check strategy names and `params` against the registry before any
chunking happens — errors surface as `PolicyValidationError` with a field
path like `pipeline.levels[0].params.overlap`.

## Semantic provider

Semantic chunking needs a similarity provider, injected **per call**:

```python
class MyProvider:
    def score(self, left: str, right: str) -> float: ...  # [0, 1]
    # optional: def score_batch(self, pairs): ...

result = engine.execute(text, policy, provider=MyProvider())
```

A level whose strategy declares `requires_provider` fails before any
chunking when no provider is supplied (`ProviderMissingError`). The
provider never appears in the Policy, the plan, or serialized results.

## Custom chunkers

```python
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from chunkweave import ChunkEngine, ChunkSpan

class WordsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_words: StrictInt = Field(default=4, gt=0)

class WordChunker:
    def __init__(self, params: WordsParams) -> None:
        self.max_words = params.max_words

    def chunk(self, text: str) -> list[ChunkSpan]:
        ...  # yield ChunkSpan(content, start_offset, end_offset,
        ...  #                strategy_metadata={...})

engine.register(
    "words",
    lambda params, provider: WordChunker(params),
    params_model=WordsParams,
    # requires_provider=True if the strategy needs a provider
)
```

The strategy is then referenced by name in `pipeline.levels[].strategy`;
its `params` are validated against `params_model`, rejecting undefined keys.

## HTTP service (optional)

An opt-in HTTP API exposes `POST /api/v1/chunks` with the same execution
path and result as the SDK:

```bash
pip install 'chunkweave[server]'
uvicorn --factory chunkweave.server:create_app --port 8000
```

```bash
curl -s -X POST http://localhost:8000/api/v1/chunks \
  -H 'Content-Type: application/json' \
  -d '{"text": "some text",
       "policy": {"api_version": "chunkweave/v1",
                  "policy": {"id": "demo", "name": "demo", "version": "1.0.0"},
                  "pipeline": {"levels": [
                    {"name": "l0", "strategy": "sliding_window",
                     "params": {"chunk_size": 10}}]}}}'
```

To inject a provider or pre-registered custom chunkers, create the app in
your own entry point:

```python
# serve.py
from chunkweave import ChunkEngine
from chunkweave.server import create_app

app = create_app(engine=ChunkEngine(), provider=MyProvider(),
                 max_text_length=1_000_000)
```

See `docs/http-service.md` for the request/response contract, error table
and `create_app` parameters.

## Serialization

```python
data = result.model_dump()        # JSON-safe dict, includes "total"
text = result.model_dump_json()   # stable JSON string
result2 = ChunkResult.model_validate(data)  # round-trip
```

## Docs & examples

| Path | Contents |
| --- | --- |
| `docs/configuration.md` | Policy YAML DSL reference |
| `docs/metadata.md` | metadata fields, Context, include semantics |
| `docs/organization/pipeline-levels.md` | 1/N-level execution rules |
| `docs/algorithms/` | sliding-window, recursive, semantic |
| `docs/design.md` | architecture: Policy → Compiler → IR → Runtime |
| `docs/http-service.md` | optional HTTP API (`chunkweave[server]`) |
| `docs/decisions/` | ADRs |
| `docs/migration.md` | old API → new API migration guide |
| `examples/` | 7 runnable scripts + `examples/policies/*.yaml` |
| `IMPLEMENTATION_REPORT.md` | build/verification report |

## Develop

```bash
pip install -e .[dev]
pytest -q          # tests
ruff check .       # lint
mypy src           # types
python -m build    # wheel + sdist
```

License: MIT.
