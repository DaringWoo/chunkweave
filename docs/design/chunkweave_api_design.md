# ChunkWeave 完整接口设计方案

> **项目定位：** Declarative Document Chunking Engine（声明式文档切块引擎）  
> **核心目标：** 输入清洗后的文本和 YAML Policy，由统一引擎执行切块、层级组织和元数据生成，输出结构化的 Python Chunk 对象列表。

---

## 1. 产品定位与职责边界

ChunkWeave 只负责对**已经清洗、标准化的文本**执行切块。它不负责文档解析、文本清洗、Embedding、向量数据库或 RAG 检索。

### 1.1 职责范围

| 属于 ChunkWeave | 不属于 ChunkWeave |
|---|---|
| YAML DSL | PDF / Word / HTML 解析 |
| Policy Parser | OCR |
| Policy Validator | 文本清洗 |
| Execution Planner | 格式标准化 |
| Chunking Strategies | Embedding |
| Chunk Organization | Milvus / Qdrant |
| Metadata Generation | RAG 检索 |
| Policy 版本与执行信息记录 | RAGAS 评估 |

### 1.2 在 RAG 数据处理链路中的位置

```text
原始文档
   |
   v
Document Processing
   |  PDF / Word 解析、OCR、文本清洗
   v
Cleaned Text
   |
   v
ChunkWeave
   |  YAML Policy -> Parser -> IR -> Runtime
   v
Chunk Objects
   |
   v
Embedding
   |
   v
Vector Database
```

各环节可以由不同工程实现，通过明确的数据契约组合，不互相承担对方的职责。

---

## 2. 公共 API：用户如何调用

公共 API 的核心入口为 `ChunkEngine.execute()`。普通用户不需要了解 Registry、Organization、IR 等内部实现。

### 2.1 加载策略并执行

```python
from chunkweave import ChunkEngine, Policy

policy = Policy.from_file("policies/novel.yaml")

engine = ChunkEngine()

result = engine.execute(
    text=cleaned_text,
    policy=policy,
    context={
        "document_id": "doc-001",
        "document_name": "西游记",
        "source": "upload",
    },
)

chunks = result.chunks
```

这里的 `context` 只提供当前文档的动态数据，不负责定义要生成哪些 Metadata 字段。字段定义、固定值和动态值的映射规则全部由 YAML Policy 声明。

### 2.2 遍历 Chunk

```python
for chunk in result.chunks:
    print(chunk.chunk_id)
    print(chunk.content)
    print(chunk.parent_id)
    print(chunk.level)
    print(chunk.sequence)
    print(chunk.start_offset)
    print(chunk.end_offset)
    print(chunk.metadata)
```

每个 `chunk` 都是 Python 对象，可以通过属性访问，而不是要求调用方使用嵌套字典下标。

### 2.3 获取执行信息

```python
print(result.total)
print(result.policy_id)
print(result.policy_version)
print(result.execution_id)
print(result.execution_time_ms)
```

### 2.4 统一层级模型

不单独设计 Flat 和 Hierarchical 两套组织 API。

- 一个 level：平铺切块。
- 两个 levels：父子组织。
- 三个或更多 levels：多级组织。

组织层级统一由 Policy 中的 `pipeline.levels` 表达。

---

## 3. YAML Policy DSL

YAML 是用户声明文档切块方式的策略文件。它描述处理阶段、每层采用的策略及参数，以及最终 Chunk Metadata 的生成规则，而不是暴露内部 Python 调用细节。

### 3.1 单层：平铺切块

```yaml
api_version: chunkweave/v1

policy:
  id: novel
  name: Novel Chunking
  version: 1.0.0

pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params:
        chunk_size: 500
        overlap: 50
```

单个 level 表示只执行一次切块，不建立父子层级。

### 3.2 两层：父子组织

```yaml
api_version: chunkweave/v1

policy:
  id: novel
  name: Novel Chunking
  version: 1.0.0

pipeline:
  levels:
    - name: parent
      strategy: recursive
      params:
        chunk_size: 2000
        overlap: 100

    - name: child
      strategy: recursive
      params:
        chunk_size: 500
        overlap: 50
```

执行逻辑：

```text
Original Text
     |
     v
Recursive(2000)
     |
     v
Parent Chunks
     |
     v
Recursive(500) applied to each parent
     |
     v
Child Chunks
```

### 3.3 多层混合策略

```yaml
api_version: chunkweave/v1

policy:
  id: technical-doc
  name: Technical Documentation
  version: 1.0.0

pipeline:
  levels:
    - name: section
      strategy: recursive
      params:
        chunk_size: 4000
        overlap: 100

    - name: paragraph
      strategy: recursive
      params:
        chunk_size: 1500
        overlap: 50

    - name: sentence
      strategy: semantic
      params:
        threshold: 0.7
```

每个 level 可以独立选择策略和参数。引擎按层级顺序执行，并建立组织关系。

### 3.4 自定义 Metadata

**Metadata 字段的定义权属于 YAML Policy。** Python 调用代码不负责声明要生成哪些 Metadata 字段，只负责提供当前文档的动态值。

例如，一份小说 Policy 可以这样定义：

```yaml
api_version: chunkweave/v1

policy:
  id: novel
  name: Novel Chunking
  version: 1.0.0

pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params:
        chunk_size: 500
        overlap: 50

metadata:
  fields:
    document_type:
      value: novel

    language:
      value: zh

    category:
      value: literature

    document_id:
      source: context.document_id

    document_name:
      source: context.document_name

    source:
      source: context.source

  include:
    strategy: true
    organization: true
```

这里有两种 Metadata 值的来源：

| 配置 | 含义 | 示例 |
|---|---|---|
| `value` | 在 YAML 中声明的固定值 | `document_type: novel` |
| `source` | 从执行时传入的 Context 中读取动态值 | `context.document_id` |

`value` 和 `source` 对同一个字段应当二选一，不应同时配置。

Python 调用时只提供动态数据：

```python
result = engine.execute(
    text=cleaned_text,
    policy=policy,
    context={
        "document_id": "doc-001",
        "document_name": "西游记",
        "source": "upload",
    },
)
```

最终每个 Chunk 的 `metadata` 可以得到：

```python
{
    "document_type": "novel",
    "language": "zh",
    "category": "literature",
    "document_id": "doc-001",
    "document_name": "西游记",
    "source": "upload",
}
```

建议明确以下职责：

| 位置 | 职责 |
|---|---|
| YAML Policy | 定义生成哪些 Metadata 字段，以及固定值和动态值的映射规则 |
| Python `context` 参数 | 提供当前文档的动态属性值 |
| Metadata Builder | 根据 Policy 和 Context 生成最终 Metadata |

`include.strategy` 和 `include.organization` 用于控制是否输出相应的可选策略信息和组织信息。系统必需字段，例如 `chunk_id`、`parent_id`、`level`，不应因关闭这些选项而丢失。

建议执行时如果 Policy 引用了不存在的 Context 路径，默认报出明确的校验错误，而不是静默写入 `None`。如果未来确实需要可选字段，可以再增加显式的 `required: false` 语义。

---

## 4. 核心数据模型

建议第一版使用 Pydantic V2。它提供类型校验、嵌套模型和序列化能力，适合 Python SDK，也方便后续提供 FastAPI 服务。

### 4.1 Chunk：单个切块对象

建议字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `chunk_id` | `str` | 当前 Chunk 的标识 |
| `content` | `str` | Chunk 文本内容 |
| `parent_id` | `str \| None` | 父 Chunk ID；根节点为 `None` |
| `level` | `int` | 层级，从 0 开始 |
| `sequence` | `int` | 在同一父节点下的顺序 |
| `start_offset` | `int` | 在输入文本中的起始位置 |
| `end_offset` | `int` | 在输入文本中的结束位置 |
| `strategy` | `str` | 产生该 Chunk 的策略名称 |
| `strategy_metadata` | `dict[str, Any]` | 策略执行产生的额外信息 |
| `metadata` | `dict[str, Any]` | 按 YAML Policy 规则生成的业务元数据 |

建议模型：

```python
from typing import Any
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    content: str

    parent_id: str | None = None
    level: int
    sequence: int

    start_offset: int
    end_offset: int

    strategy: str
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

字段分层原则：

- 系统组织字段直接作为属性。
- 策略特有信息放在 `strategy_metadata`。
- 业务 Metadata 由 YAML Policy 定义字段，执行时由 Context 提供动态值。

Offset 约定：

- 相对于传入的清洗后文本。
- 使用 Python 字符索引，而不是 UTF-8 字节偏移。
- 区间采用左闭右开 `[start_offset, end_offset)`。
- 子块 Offset 应转换为输入文本中的全局位置，而不是相对于父块的位置。

### 4.2 ChunkResult：一次执行的结果

`ChunkResult` 是一次切块任务的结果容器，包含 Chunk 对象列表和本次执行的信息。它不是 Chunk 的父类。

建议字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `chunks` | `list[Chunk]` | 本次生成的所有 Chunk 对象 |
| `policy_id` | `str` | 使用的策略 ID |
| `policy_version` | `str` | 策略版本 |
| `policy_hash` | `str` | 实际策略内容的哈希 |
| `execution_id` | `str` | 本次执行的唯一标识 |
| `engine_version` | `str` | ChunkWeave 引擎版本 |
| `execution_time_ms` | `float` | 执行耗时 |
| `total` | `int` | Chunk 数量，可通过 `len(chunks)` 计算 |

建议模型：

```python
from pydantic import BaseModel


class ChunkResult(BaseModel):
    chunks: list[Chunk]

    policy_id: str
    policy_version: str
    policy_hash: str

    execution_id: str
    engine_version: str
    execution_time_ms: float

    @property
    def total(self) -> int:
        return len(self.chunks)
```

`chunks: list[Chunk]` 表示列表中的元素是真正的 Python `Chunk` 对象，可以直接访问 `chunk.content` 等属性。

### 4.3 序列化

使用 Pydantic V2 的标准方法：

```python
# 转换为 Python dict
data = result.model_dump()

# 转换为 JSON 字符串
json_data = result.model_dump_json()
```

Core 内部使用 Python 对象；跨进程或 HTTP 传输时再转换为 JSON。

### 4.4 可选便利方法

可以根据实际使用需求增加：

```python
chunk = result.get_chunk("chunk-001")

level_chunks = result.get_level(1)

tree = result.to_tree()
```

这些不是第一版必须实现的能力。核心组织关系由 `parent_id` 表达，核心输出保持扁平的 `list[Chunk]`。

---

## 5. Policy 对象设计

Policy 是 YAML 在 Python 中的结构化表示。

用户主要通过以下方法加载：

```python
policy = Policy.from_file("novel.yaml")

policy = Policy.from_yaml(yaml_text)
```

使用时可以访问：

```python
print(policy.id)
print(policy.version)
print(policy.pipeline.levels)
print(policy.metadata.fields)
```

建议的模型结构：

```python
from typing import Any
from pydantic import BaseModel, Field


class PolicyInfo(BaseModel):
    id: str
    name: str
    version: str


class LevelConfig(BaseModel):
    name: str
    strategy: str
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    levels: list[LevelConfig]


class MetadataFieldConfig(BaseModel):
    value: Any | None = None
    source: str | None = None


class MetadataIncludeConfig(BaseModel):
    strategy: bool = True
    organization: bool = True


class MetadataConfig(BaseModel):
    fields: dict[str, MetadataFieldConfig] = Field(default_factory=dict)
    include: MetadataIncludeConfig = Field(default_factory=MetadataIncludeConfig)


class Policy(BaseModel):
    api_version: str
    policy: PolicyInfo
    pipeline: PipelineConfig
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
```

`MetadataFieldConfig` 需要额外做互斥校验：`value` 与 `source` 必须且只能配置一个。真实实现还应处理合法的 `None` 固定值与字段缺失之间的区别，避免简单地仅靠 `None` 判断字段是否配置。

实际实现还需要校验：

- `levels` 非空。
- 策略名称已经注册。
- 策略参数符合对应策略的 Schema。
- 层级配置有效。
- Policy 版本格式有效。
- Metadata 字段定义合法。
- `source` 引用的 Context 路径在执行时存在。

建议区分结构校验和语义校验：

| 校验类型 | 检查内容 |
|---|---|
| 结构校验 | YAML 格式、字段、类型、必填项 |
| 语义校验 | 策略是否存在、参数是否合法、层级配置是否有效、Metadata 映射定义是否合法 |
| 执行期校验 | Policy 引用的 Context 路径是否有对应值 |

---

## 6. ChunkEngine 接口设计

核心公共方法：

| 方法 | 作用 |
|---|---|
| `execute()` | 执行切块策略 |
| `validate()` | 校验 Policy |
| `compile()` | 将 Policy 转换为执行计划 |

示例：

```python
engine = ChunkEngine()

# 校验策略
engine.validate(policy)

# 编译为执行计划，供调试或检查
plan = engine.compile(policy)

# 执行策略
result = engine.execute(
    text=cleaned_text,
    policy=policy,
    context={
        "document_id": "doc-001",
        "document_name": "西游记",
        "source": "upload",
    },
)
```

普通用户只需要调用 `execute()`。它内部自动完成校验和编译。

`compile()` 主要用于高级用户检查执行计划，不是普通使用流程的必需步骤。

参数职责：

| 参数 | 职责 |
|---|---|
| `text` | 已经清洗、标准化的文本 |
| `policy` | 定义切块方式、组织层级和 Metadata 生成规则 |
| `context` | 提供 Policy 引用的动态数据，不负责定义 Metadata 字段 |

建议 `execute()` 接受已经加载的 `Policy` 对象，不在同一个参数中混用文件路径、YAML 字符串和 Policy 对象。

---

## 7. Strategy Registry 扩展接口

用户在 YAML 中选择策略，Registry 根据策略名称找到具体实现。

例如：

```yaml
strategy: recursive
params:
  chunk_size: 500
  overlap: 50
```

Registry 注册策略：

```python
registry.register("recursive", RecursiveChunker)
registry.register("semantic", SemanticChunker)
registry.register("sliding", SlidingWindowChunker)
```

切块器遵守统一协议：

```python
from typing import Protocol


class Chunker(Protocol):

    def chunk(self, text: str, **params) -> list[Chunk]:
        ...
```

建议实际 Runtime 内部让策略返回统一的中间结果类型，例如 `ChunkSpan`，再由 Organization 负责生成最终 `Chunk`。这样具体策略不需要承担完整的父子关系和业务元数据管理。

---

## 8. HTTP Service 接口

Core Python Package 和 HTTP Service 共用相同的核心执行逻辑。

第一版主要执行接口：

```http
POST /api/v1/chunks
```

### 8.1 直接传入 Policy

请求示例：

```json
{
  "text": "清洗后的文档文本……",
  "policy": {
    "api_version": "chunkweave/v1",
    "policy": {
      "id": "novel",
      "name": "Novel Chunking",
      "version": "1.0.0"
    },
    "pipeline": {
      "levels": [
        {
          "name": "paragraph",
          "strategy": "recursive",
          "params": {
            "chunk_size": 500,
            "overlap": 50
          }
        }
      ]
    },
    "metadata": {
      "fields": {
        "document_type": {
          "value": "novel"
        },
        "language": {
          "value": "zh"
        },
        "document_id": {
          "source": "context.document_id"
        },
        "document_name": {
          "source": "context.document_name"
        }
      },
      "include": {
        "strategy": true,
        "organization": true
      }
    }
  },
  "context": {
    "document_id": "doc-001",
    "document_name": "西游记"
  }
}
```

### 8.2 引用已发布的 Policy

生产环境可以支持：

```json
{
  "text": "清洗后的文档文本……",
  "policy_ref": {
    "id": "novel",
    "version": "1.0.0"
  },
  "context": {
    "document_id": "doc-001",
    "document_name": "西游记"
  }
}
```

两种调用方式：

- 开发和测试：直接传入 Policy。
- 生产环境：引用已发布的 Policy 版本。

### 8.3 返回结果

```json
{
  "execution_id": "run-001",
  "policy_id": "novel",
  "policy_version": "1.0.0",
  "policy_hash": "sha256:...",
  "engine_version": "0.1.0",
  "execution_time_ms": 25.6,
  "total": 1,
  "chunks": [
    {
      "chunk_id": "chunk-001",
      "content": "第一段文本",
      "parent_id": null,
      "level": 0,
      "sequence": 0,
      "start_offset": 0,
      "end_offset": 500,
      "strategy": "recursive",
      "strategy_metadata": {},
      "metadata": {
        "document_type": "novel",
        "language": "zh",
        "document_id": "doc-001",
        "document_name": "西游记"
      }
    }
  ]
}
```

HTTP 返回 JSON；Python SDK 返回 `ChunkResult` 对象。

---

## 9. 内部架构

建议采用 Policy、Compiler、Runtime 分层。

```text
                 YAML Policy
                      |
                      v
              Policy Loader
                      |
                      v
               Policy Model
                      |
                      v
              Policy Validator
                      |
                      v
              Policy Compiler
                      |
                      v
              Execution IR
                      |
                      v
               Runtime Engine
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Registry   Organization  Metadata
          |
          v
       Chunkers
          |
          v
      ChunkResult
```

模块职责：

| 模块 | 职责 |
|---|---|
| Policy Loader | 加载 YAML |
| Policy Parser | 解析 YAML |
| Policy Validator | 结构与语义校验 |
| Policy Compiler | 转换成 IR |
| Execution IR | 统一表达执行计划 |
| Strategy Registry | 策略注册与创建 |
| Chunkers | 执行具体切块算法 |
| Organization | 建立层级关系 |
| Metadata Builder | 根据 Policy 和 Context 生成 Metadata |
| ChunkResult | 返回执行结果 |

重要原则：

- Policy Layer 不直接执行切块。
- Runtime 不直接解析 YAML。
- Policy 和 Runtime 通过 IR 衔接。
- Metadata Builder 不自行决定业务字段；字段定义来自 Policy，动态值来自 Context。
- 普通使用者不需要了解这些内部模块。

---

## 10. 建议的项目目录

```text
chunkweave/
│
├── pyproject.toml
├── README.md
│
├── src/
│   └── chunkweave/
│       ├── __init__.py
│       ├── engine.py
│       │
│       ├── policy/
│       │   ├── loader.py
│       │   ├── parser.py
│       │   ├── validator.py
│       │   └── models.py
│       │
│       ├── compiler/
│       │   ├── compiler.py
│       │   └── ir.py
│       │
│       ├── strategies/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── recursive.py
│       │   ├── sliding_window.py
│       │   └── semantic.py
│       │
│       ├── runtime/
│       │   ├── executor.py
│       │   └── organization.py
│       │
│       ├── metadata/
│       │   └── builder.py
│       │
│       ├── models/
│       │   ├── chunk.py
│       │   └── result.py
│       │
│       ├── exceptions.py
│       └── constants.py
│
├── server/
│   ├── main.py
│   └── routes/
│       └── chunks.py
│
├── examples/
│   └── policies/
│       ├── novel.yaml
│       ├── markdown.yaml
│       └── technical.yaml
│
└── tests/
```

这是目标结构，不要求 MVP 一次性建立全部模块。

---

## 11. 关键设计约束

| 问题 | 建议 |
|---|---|
| 层级数量 | 1 到 N 层 |
| 组织方式 | 通过层级自动形成父子关系 |
| 切块策略 | 每层独立指定 |
| 策略参数 | 放在对应层级的 `params` 中 |
| Metadata 字段定义 | 统一放在 YAML Policy |
| Metadata 动态值 | 通过 Python `context` 参数提供 |
| Metadata 生成 | Metadata Builder 根据 Policy 和 Context 执行 |
| 系统字段 | 直接作为 Chunk 属性，不由业务 Metadata 覆盖 |
| Offset | 相对于输入文本的全局字符偏移 |
| Chunk ID | 每次执行内唯一，建议确定性生成 |
| 父子关系 | 第一版使用 `parent_id` |
| ChunkResult | 保存扁平的 Chunk 对象列表和执行信息 |
| 序列化 | Pydantic `model_dump()` / `model_dump_json()` |
| Embedding | 不属于引擎 |
| 文档清洗 | 不属于引擎 |

还需要明确：

1. 默认不产生空 Chunk。
2. Semantic 策略如果依赖外部模型，应记录模型标识、版本和关键参数。
3. Overlap 会让相邻 Chunk 的原文范围交叉，但第一版建议每个子 Chunk 只有一个父节点。
4. Policy 版本、内容 Hash、引擎版本应共同用于执行追溯。
5. Policy 引用的 Context 路径缺失时，默认明确报错；可选字段需要在 DSL 中显式声明。
6. Policy 固定值与 Context 动态值发生冲突时，不采用隐式覆盖；每个字段只允许声明一种来源。

---

## 12. MVP 开发路线

| 阶段 | 工作内容 | 预期产物 |
|---|---|---|
| 1 | 设计 YAML DSL | Policy 格式规范 |
| 2 | 定义 Pydantic Policy Model | 配置模型 |
| 3 | 实现 Policy Validator | 策略校验器 |
| 4 | 设计 Execution IR | 统一执行计划 |
| 5 | 实现 Strategy Registry | 策略注册机制 |
| 6 | 实现 Recursive Chunker | 第一种切块算法 |
| 7 | 实现 Organization Runtime | 1 到 N 层组织 |
| 8 | 实现 Metadata Builder | 根据 Policy 和 Context 生成元数据 |
| 9 | 实现 Chunk / ChunkResult | 公共结果模型 |
| 10 | 实现 ChunkEngine.execute() | Python SDK |
| 11 | 编写单元测试 | 可验证的执行结果 |
| 12 | 包装 FastAPI | HTTP 服务 |
| 13 | Policy Governance | 版本与执行记录 |

建议先完成前十项并通过测试，再开发 HTTP 服务。第一版的治理能力可以先记录 Policy 版本、Hash 和执行信息，不必急于开发独立后台。

---

## 13. 最终公共接口速查

| 名称 | 类型 | 职责 |
|---|---|---|
| `Policy` | Model | 描述切块策略及 Metadata 生成规则 |
| `ChunkEngine` | Class | 执行策略 |
| `Chunk` | Model | 表示单个 Chunk |
| `ChunkResult` | Model | 表示一次执行结果 |
| `Chunker` | Protocol | 统一切块算法接口 |
| `ExecutionPlan` | Model | 表示编译后的执行计划 |

核心调用：

```python
from chunkweave import ChunkEngine, Policy

policy = Policy.from_file("novel.yaml")

engine = ChunkEngine()

result = engine.execute(
    text=cleaned_text,
    policy=policy,
    context={
        "document_id": "doc-001",
        "document_name": "西游记",
        "source": "upload",
    },
)

for chunk in result.chunks:
    print(chunk.content)
    print(chunk.parent_id)
    print(chunk.level)
    print(chunk.metadata)
```

### 当前建议冻结的三个决策

| 设计问题 | 推荐决定 |
|---|---|
| 组织表达方式 | 只使用 `pipeline.levels`，一层就是平铺 |
| Metadata 结构 | 字段定义在 YAML；固定值用 `value`，动态值用 `source`；动态值由 `context` 提供 |
| ChunkResult 输出 | 只保存扁平 `list[Chunk]`，通过 `parent_id` 表达关系 |

---

## 14. 设计总结

ChunkWeave 的核心不是提供尽可能多的切块算法，而是提供一种统一的策略描述和执行机制。

用户通过 YAML 声明文档应该如何切分、如何组织，以及每个 Chunk 应该带有哪些 Metadata 字段；引擎将 Policy 转换为统一 IR，调用对应策略，完成层级组织和 Metadata 生成；最终返回可直接通过属性访问的 Python Chunk 对象列表。

Policy 是独立的、可版本化的工程资产。ChunkWeave 是独立的切块执行引擎。文档解析、清洗、Embedding 和向量数据库都由外部工程负责。

**核心设计哲学：Policy defines how to chunk and what metadata to produce; Context supplies runtime values; Engine executes the policy; Chunk represents the result.**
