# ChunkWeave 架构重构 Agent 执行提示词

> 用途：将本提示词交给具备仓库读写、终端执行和测试能力的 Coding
> Agent，让它在**现有 ChunkWeave 仓库内**完成架构重构。
>
> 执行模式：允许 Agent
> 自主检查、规划、修改、测试和提交阶段性结果；遇到不可逆操作、需求冲突或外部凭据缺失时必须停止并说明，不得擅自猜测。

------------------------------------------------------------------------

## 0. 最高优先级任务指令

你现在负责对**当前打开的 ChunkWeave 仓库进行渐进式架构重构**。

这不是新建项目任务，也不是从零生成一套替代代码。必须在当前仓库内完成改造，保留已经实现且验证有效的切块算法和组织逻辑，逐步将旧配置驱动架构迁移到新的
**YAML Policy → Compiler → Execution IR → Runtime** 架构。

### 必须遵守

1.  第一件事是检查当前仓库，不要立即写代码。
2.  不要删除旧代码后从头生成。
3.  不要一次性大面积覆盖文件。按阶段、小步迁移，每阶段都运行相关测试。
4.  先建立现有行为基线，再重构。尽可能保留算法行为、边界条件和公开能力。
5.  不得为了匹配目标目录而制造空模块、空抽象或无意义封装。
6.  不得擅自扩大项目职责：第一版不实现文档解析、OCR、文本清洗、Embedding、向量数据库、RAG
    检索或 RAGAS。
7.  不得把 YAML 解析逻辑放进 Runtime；Runtime 只消费编译后的执行计划。
8.  不得让策略算法负责父子关系、最终 Chunk ID 或业务 Metadata 组装。
9.  不得让 Python `context` 决定 Metadata
    字段定义；字段定义及来源规则属于 YAML Policy。
10. 所有公开 API、配置和返回模型都必须有类型标注及必要文档。
11. 不得静默吞掉异常、静默忽略未知配置字段，或在缺失必需 Context
    时静默写入 `None`。
12. 不要提交密钥、真实凭据、个人路径或测试数据中的敏感信息。
13. 不要在没有用户明确要求时执行 `git push`、发布
    PyPI、删除远程分支、重写 Git 历史等远程或不可逆操作。
14. 如果仓库现状与本提示词或设计文档冲突，先记录差异，优先保留已有可验证行为，并选择最小风险实现；不能自行解决的冲突写入决策记录。
15. 本任务的验收依据是实际测试和可运行示例，不是目录看起来完整。

### 0.1 规范依据：OpenSpec

-   本仓库的正式规范是 `openspec/specs/*/spec.md`，已同步 OpenSpec Change
    `refactor-to-policy-driven-engine` 的全部 delta。
-   实施依据依次为：正式 Spec、该 Change 的
    `design.md`（含已决定事项）、本提示词、`docs/design/chunkweave_api_design.md`。
-   任何内容与本提示词或设计文档冲突时，以正式 Spec 为准。
-   如果你认为正式 Spec 有误：停止并报告，不得自行在代码里另行其是。经用户同意后，按
    openspec-update-change 流程修订该 Change 的 delta 与正式 Spec，保持一致。
-   实施进度通过勾选 `openspec/changes/refactor-to-policy-driven-engine/tasks.md`
    的任务记录；实施中作出的新设计决策写入该 Change 的 `design.md`。
-   全部任务完成后，经用户同意，执行
    `openspec archive refactor-to-policy-driven-engine --skip-specs` 归档（delta
    已同步，必须带 `--skip-specs`，否则 ADDED 会重复应用）。

------------------------------------------------------------------------

## 1. 项目定位与职责边界

ChunkWeave 是一个 **Declarative Document Chunking
Engine（声明式文档切块引擎）**。

输入： - 已经解析、清洗和标准化的文本； - YAML Policy； - 可选的运行时
`context`； - 可选的外部相似度 Provider（供 Semantic 策略使用）。

输出： - 扁平的 `list[Chunk]`； - `ChunkResult` 执行结果对象； -
可追溯的 Policy、执行和引擎信息。

ChunkWeave 负责： - YAML DSL； - Policy Loader / Model / Validator； -
Policy Compiler； - Execution IR； - Strategy Registry； - Chunking
Strategies； - Chunk Organization； - Metadata Generation； - 执行信息与
Policy Hash。

ChunkWeave 不负责： - PDF、Word、HTML 等文档解析； - OCR； -
文本清洗与格式标准化； - Embedding； - Milvus、Qdrant 等向量数据库； -
RAG 检索； - RAGAS 评估。

不得把以上非职责范围加入核心运行时依赖。

------------------------------------------------------------------------

## 2. 开工前：仓库审计与基线建立

在修改代码之前完成以下工作。

### 2.1 检查仓库

检查并记录： - 完整目录树； - `pyproject.toml`、Python
版本、依赖管理工具和 lock 文件； - 当前包结构及实际导出的公共 API； -
所有策略实现、配置模型、组织逻辑、元数据逻辑、结果模型； -
测试目录、测试覆盖范围、CI、Ruff / pytest / 类型检查配置； -
README、示例和现有使用方式； - Git 工作区状态、当前分支和最近提交。

**不要假设仓库与提示词中列出的文件完全相同。以当前仓库实际内容为准。**

### 2.2 运行现有测试

-   运行完整测试套件。
-   运行项目已有的 lint、format check、type check（如果配置了）。
-   保存命令、结果和失败摘要。
-   对现有失败进行分类：重构前已有失败、环境问题、待确认问题。
-   不得把重构前已有失败错误归因于本次改动。

如果项目没有测试，先为现有核心行为补充基线测试，再开始结构迁移。

### 2.3 建立行为基线

至少检查并测试以下已有能力：

**Sliding Window** - `overlap=0`、正常 overlap、非法 overlap； -
文本短于、等于、大于窗口； - 最后一个窗口； - 空文本； - 中文、Emoji 和
Offset。

**Recursive** - 多级 separator 优先级； - separator 的
`previous`、`next`、`none`； - separator 不匹配时的降级行为； -
超长片段的字符级 fallback； - overlap； - 空文本； - 中文、Emoji 和
Offset。

**Semantic** - Provider 注入； - Provider 缺失时明确报错； -
相邻单元相似度阈值切分； - `score_batch` 与逐对 `score` 两种路径； -
Provider 返回数量不匹配； - 超长语义块的二次切分； -
空文本和单单元文本。

**Organization** - 单层平铺； - 两层父子； - 三层或更多层； -
每个父块独立生成子块； - 子块 local offset 转换为输入文本 global
offset； - 父块无子块； - `parent_id`、`level`、`sequence` 正确； -
overlap 造成范围交叉时仍维持约定的父子关系。

**Metadata** - 自定义字段； - 字段继承和覆盖顺序； -
系统保留字段冲突； - 策略保留字段冲突； - JSON 序列化合法性； - 每个
Chunk 的 Metadata 不发生可变对象串扰。

------------------------------------------------------------------------

## 3. 目标公共 API

普通用户不需要知道 Registry、IR、Runtime 等内部模块。

目标调用方式：

``` python
from chunkweave import ChunkEngine, Policy

policy = Policy.from_file("examples/policies/novel.yaml")

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
    print(chunk.chunk_id)
    print(chunk.content)
    print(chunk.parent_id)
    print(chunk.level)
    print(chunk.sequence)
    print(chunk.start_offset)
    print(chunk.end_offset)
    print(chunk.metadata)

print(result.total)
print(result.policy_id)
print(result.policy_version)
print(result.policy_hash)
print(result.execution_id)
print(result.execution_time_ms)
```

公共 API 至少提供：

-   `Policy.from_file(path)`
-   `Policy.from_yaml(yaml_text)`
-   `ChunkEngine.validate(policy)`
-   `ChunkEngine.compile(policy)`
-   `ChunkEngine.execute(text, policy, context=None, provider=None)`

要求： - `execute()` 内部自动完成必要的校验和编译。 - `compile()`
返回可检查的执行计划。 - `validate()` 不执行切块。 - `execute()`
接受已加载的 `Policy` 对象，不要混用文件路径、YAML 字符串和 Policy
对象。 - `context` 只提供动态值，不声明 Metadata 字段。 - Semantic
Provider 通过明确的依赖注入方式传入，不写入 YAML，也不序列化 Provider
实例。

若仓库已有公共
API，先评估是否需要兼容。当前版本若仍处于早期开发阶段，可以在 README
中明确新 API；但不要无理由保留两套长期并行 API。任何删除旧 API
的决定都必须有迁移说明和测试。

------------------------------------------------------------------------

## 4. YAML Policy DSL

### 4.1 单层：平铺切块

``` yaml
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

一个 level 表示一次切块，不建立父子层级。

### 4.2 两层：父子组织

``` yaml
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

每个父 Chunk 独立执行下一层策略。下一层的 offset
必须转换为相对于原始输入文本的全局字符 offset。

### 4.3 多层混合策略

``` yaml
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
        chunk_size: 800
```

每一层独立指定策略和参数。策略名称必须由 Registry
解析，策略参数必须由对应策略的配置 Schema 校验。

### 4.4 Metadata DSL

``` yaml
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

Metadata 字段规则： - `value`：YAML 中声明的固定值。 -
`source`：从执行时传入的 Context 路径读取动态值。 -
同一字段必须且只能声明一种来源。 - 不允许 `value` 与 `source`
同时出现。 - 必需的 Context 路径缺失时，默认抛出清晰异常，不允许静默填入
`None`。 - 如果将来支持可选字段，应通过明确 DSL 语义表达，例如
`required: false`，不要用隐式容错。 - `include.strategy` 和
`include.organization` 控制保留键是否**复制进**每个 Chunk 的
`metadata`：`include.organization: true` 时 `metadata` 含
`parent_id`、`level`、`sequence`（值等于对应 Chunk 属性）与
`level_name`（所在层的 `name`）；`include.strategy: true` 时
`metadata` 含 `strategy` 与 `strategy_metadata`（与对应 Chunk
属性相等的独立副本）；两者缺省 `true`，关闭时仅 `metadata` 不含对应键；Chunk
属性（含 `strategy_metadata` 属性）无论开关都完整保留、不被清空。 -
`metadata.fields` 字段名不得使用保留键：`chunk_id`、`content`、
`parent_id`、`level`、`sequence`、`start_offset`、`end_offset`、
`strategy`、`strategy_metadata`、`metadata`、`level_name`，违反时加载阶段报错。 -
系统字段不能被业务 Metadata 覆盖。 - 策略元数据、组织字段、业务
Metadata 必须有清晰边界。

注意：上面是目标 DSL。实现前先将它转成明确的 Schema，并补充 YAML
示例和校验测试。不要凭直觉增加未定义的字段或语法。

------------------------------------------------------------------------

## 5. 核心数据模型

第一版使用 Pydantic V2（如果仓库现有依赖或 Python
版本存在实际冲突，先记录并提出最小调整方案，不要静默升级整个工具链）。

### 5.1 ChunkSpan：策略输出

策略层不应直接构造最终 Chunk。建议引入内部中间结果：

``` python
from pydantic import BaseModel, Field
from typing import Any

class ChunkSpan(BaseModel):
    content: str
    start_offset: int
    end_offset: int
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)
```

`ChunkSpan` 只表达算法产生的文本片段和策略元数据，不包含： -
`chunk_id` - `parent_id` - `level` - `sequence` - 业务 `metadata`

策略只负责切分，不负责最终组织和业务元数据。

### 5.2 Chunk：最终 Chunk

``` python
from pydantic import BaseModel, Field
from typing import Any

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

字段原则： - `chunk_id`：本次执行内唯一。 - `content`：Chunk 文本。 -
`parent_id`：根 Chunk 为 `None`。 - `level`：从 0 开始。 -
`sequence`：同一父节点下的顺序；根层按根级顺序。 - `start_offset` /
`end_offset`：相对于输入文本的全局 Python 字符索引，左闭右开
`[start, end)`。 - `strategy`：生成此 Chunk 的策略名称。 -
`strategy_metadata`：算法产出的额外信息。 - `metadata`：Policy Builder
按 YAML 规则生成的业务元数据。

系统字段和业务 Metadata 不得混用。

### 5.3 ChunkResult：执行结果

``` python
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

要求： - 核心输出保持扁平 `list[Chunk]`。 - 父子关系只通过 `parent_id`
表达。 - 可按需提供 `to_tree()`
等便利方法，但树形结构不是唯一或主要存储形式。 - `total` 必须出现在
`model_dump()` 输出中（例如用计算字段实现），等于 `len(chunks)`。 -
使用 Pydantic V2 的
`model_dump()` / `model_dump_json()`。 - `policy_hash` 应基于规范化后的
Policy 内容计算，确保同一内容在不同运行中产生稳定 Hash。 -
`execution_id` 每次执行唯一。 - `execution_time_ms` 使用单调时钟测量。 -
`engine_version` 从包版本获取，不硬编码多个地方。

------------------------------------------------------------------------

## 6. Strategy 与 Registry

### 6.1 迁移现有策略

优先复用当前仓库已有算法实现： - Sliding Window； - Recursive； -
Semantic。

不要为了新目录结构而重写已经验证正确的算法。允许修改它们的输入输出适配层，但算法边界行为应由基线测试保护。

建议最终策略协议：

``` python
from typing import Protocol, Any

class Chunker(Protocol):
    def chunk(self, text: str) -> list[ChunkSpan]:
        ...
```

如果具体策略需要 Provider，应采用独立、明确的 Provider
注入协议。不要要求所有策略都依赖 Provider。

注册接口定稿为：

``` python
engine.register(name, factory, *, params_model, requires_provider=False, replace=False)
```

`params_model` 是参数 Schema（Pydantic 模型类），引擎用它校验该层
`params` 并拒绝模型中未定义的键（无论模型自身 extra 配置）；
`factory(params, provider)` 接收已校验参数对象与 Provider（不需要
Provider 的策略得到 `None`），返回 Chunker；`requires_provider=True`
的策略被引用而 `execute()` 未提供 `provider` 时，在任何切块开始前报错。
内置三个策略经同一机制注册（`semantic` 为 `requires_provider=True`）。

### 6.2 Registry 职责

Registry 只负责： - 注册策略工厂； - 根据策略名称查找策略； -
根据参数创建策略实例； - 检查重复注册； -
对未知策略提供包含可用名称的异常。

Registry 不负责： - YAML 解析； - Policy 校验； - 层级组织； - Metadata
生成； - 最终 Chunk ID 分配。

保留自定义 Chunker 注册能力。注册冲突行为必须明确，默认拒绝覆盖；如支持
`replace=True`，必须显式传入。

### 6.3 策略参数校验

每种内置策略拥有自己的参数 Schema： - `sliding_window` - `recursive` -
`semantic`

不要把所有策略参数塞进一个无约束的大字典后直接执行。Policy Validator
应依据 Registry 提供的策略定义或配置模型完成参数校验。

------------------------------------------------------------------------

## 7. Policy / Compiler / IR / Runtime 分层

这是本次重构的核心架构。

``` text
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
    +----------+-------------+
    |          |             |
    v          v             v
 Registry  Organization  Metadata Builder
    |
    v
 Chunkers
    |
    v
 ChunkResult
```

### 7.1 Policy Loader

负责： - 从文件加载 YAML； - 从 YAML 字符串加载； - 安全解析 YAML； -
将解析结果交给 Policy Model； - 对 YAML
语法错误、文件读取错误提供清晰异常。

使用安全 YAML Loader，不执行任意 Python 对象构造。

### 7.2 Policy Model

使用 Pydantic V2 表达： - `api_version` - Policy 基础信息 -
`pipeline.levels` - 每层的 `name`、`strategy`、`params` - Metadata
fields - Metadata include 规则

尽可能拒绝未知字段，避免配置拼写错误被静默忽略。

### 7.3 Policy Validator

分三类校验：

**结构校验** - YAML 结构合法； - 必填字段齐全； - 字段类型正确； -
levels 非空； - Metadata 字段定义合法； - `value` / `source` 互斥。

**语义校验** - 策略名称已经注册； - 每种策略的参数合法； - 策略配置
Schema 匹配； - 层级配置有效； - 不允许系统字段被 Metadata 覆盖； -
`api_version` 受支持。

**执行期校验** - Policy 引用的 Context 路径存在； -
必需动态值存在且符合约定； - Provider 依赖已提供； -
所有校验错误应指出字段路径和原因。

### 7.4 Execution IR

IR 是 Policy 和 Runtime 的唯一衔接契约。

要求： - IR 是纯 Python/Pydantic 数据结构； - Runtime 不读取 YAML； -
Runtime 不依赖 Policy 原始字典； - IR
包含运行所需的层级顺序、策略名称、已验证参数、Metadata 规则和必要的
Policy 元信息； - IR 不包含不可序列化的 Provider 实例； - IR
的结构清晰、可测试、可检查； - 编译过程不执行切块； - IR 不应只是把 YAML
原样复制一遍，必须体现已解析、已校验的执行计划。

### 7.5 Runtime Executor

负责： - 接收 Execution IR、输入文本、Context 和依赖； - 调用 Registry
创建策略； - 按 levels 顺序执行； - 调用 Organization 建立层级； - 调用
Metadata Builder 组装业务 Metadata（含 include
选项启用的保留键副本）； - 生成最终 Chunk； - 构建 ChunkResult。

Runtime 不得解析 YAML，也不得自行决定业务 Metadata 字段。

### 7.6 Organization

统一使用 levels： - 1 层：平铺； - 2 层：父子； - 3 层及以上：多级。

执行要求： - 第一层策略处理完整输入文本； -
后续每层策略分别处理上一层每一个父 Chunk 的 content； - 子块 offset
从父块局部坐标转换为输入文本全局坐标； - `parent_id` 指向直接父
Chunk； - `level` 从 0 开始； - `sequence` 在同一父节点下从 0 开始； -
不能把不同父块的内容合并后再执行下一层； - 允许某个父 Chunk 没有子块； -
输出为扁平列表，排序规则必须确定并测试； - Overlap 可导致不同 Chunk
的范围交叠，但第一版每个子 Chunk 只允许一个直接父节点。

### 7.7 Metadata Builder

职责： - 根据 Policy 编译得到的 Metadata 规则生成业务 Metadata； - 从
Context 路径读取动态值； - 写入 YAML 固定值； - 按 include
复制语义把保留键写入业务 Metadata：`include.organization` 控制
`parent_id`/`level`/`sequence`/`level_name` 四键，`include.strategy`
控制 `strategy`/`strategy_metadata` 两键（与 Chunk 属性相等的独立副本），两者缺省
`true`，Chunk 属性始终完整保留； - 字段名使用保留键时在加载阶段报错（保留键集合见
§4.4）； - 保证每个 Chunk 的 Metadata
不共享可变对象； - 对缺失路径、非法值、字段冲突提供明确异常。

禁止： - 在 Builder 内硬编码业务字段名或小说、技术文档等业务类型； - 从
Chunk content 推测 Context； - 允许业务 Metadata 覆盖系统字段； -
静默忽略错误。

------------------------------------------------------------------------

## 8. 目标目录结构

以当前仓库的 `src` 布局和命名约定为准，合理迁移到类似结构：

``` text
chunkweave/
├── pyproject.toml
├── README.md
├── src/
│   └── chunkweave/
│       ├── __init__.py
│       ├── engine.py
│       ├── policy/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   ├── models.py
│       │   └── validator.py
│       ├── compiler/
│       │   ├── __init__.py
│       │   ├── compiler.py
│       │   └── ir.py
│       ├── strategies/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── recursive.py
│       │   ├── sliding_window.py
│       │   └── semantic.py
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── executor.py
│       │   └── organization.py
│       ├── metadata/
│       │   ├── __init__.py
│       │   └── builder.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── chunk.py
│       │   └── result.py
│       ├── exceptions.py
│       └── constants.py
├── server/
│   ├── main.py
│   └── routes/
│       └── chunks.py
├── examples/
│   └── policies/
│       ├── novel.yaml
│       ├── markdown.yaml
│       └── technical.yaml
└── tests/
```

目录只是目标参考，不要求机械照搬。MVP
不需要为了完整目录而创建空文件。优先保证职责边界和可测试性。

------------------------------------------------------------------------

## 9. HTTP Service 的实施边界

优先完成稳定的 Core Python SDK，再包装 FastAPI。

Core 和 HTTP Service 必须调用同一套
`ChunkEngine`，不能复制一份切块执行逻辑。

第一版 HTTP 接口可以提供：

``` http
POST /api/v1/chunks
```

请求支持直接传入 Policy：

``` json
{
  "text": "清洗后的文档文本",
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
        "document_id": {
          "source": "context.document_id"
        }
      }
    }
  },
  "context": {
    "document_id": "doc-001"
  }
}
```

第一版不必实现 Policy 数据库、用户认证、后台管理、Policy
发布工作流。`policy_ref` 可作为后续能力，不要为了它引入数据库。

------------------------------------------------------------------------

## 10. 测试要求与验收标准

### 10.1 单元测试

必须覆盖： - Policy YAML 加载； - Policy 结构校验； -
策略注册和未知策略； - 策略参数 Schema； - IR 编译； - Metadata
固定值； - Metadata Context 动态值； - Context 路径缺失； - `value` 与
`source` 同时配置； - 系统字段冲突； - 三种策略； -
单层、两层、多层组织； - global offset； - 空文本； - ChunkResult
元信息； - Policy Hash 稳定性； - JSON 序列化和反序列化； - Provider
注入及错误。

### 10.2 集成测试

至少实现以下端到端用例：

1.  加载 `novel.yaml`，对中文小说文本执行 Recursive 单层切块。
2.  使用两层 Policy 生成 Parent / Child，并验证 parent_id 和全局
    offset。
3.  使用三层 Policy 混合不同策略。
4.  使用 Metadata Policy 固定值与 Context 动态值，验证最终
    Chunk.metadata。
5.  Semantic 策略通过测试 Provider 执行。
6.  同一 Policy 内容多次编译得到相同 Policy Hash。
7.  非法 Policy 在执行切块之前失败。
8.  FastAPI 请求与 Python SDK 对同一输入、Policy 得到等价 Chunk
    结果（如果 HTTP 阶段已实施）。

### 10.3 验收门槛

最终必须满足： - 所有原有可用算法行为有测试保护； - 新增核心测试通过； -
lint 通过； - 项目已有类型检查通过（如已配置）； -
没有无解释的跳过测试； - README 示例可以运行； - 三份示例 Policy
可以加载并执行； - 公共 API 文档完整； - Runtime 不依赖 YAML Parser； -
策略不负责组织关系和业务 Metadata； - Python Context 不定义 Metadata
字段； - 不存在第二套重复的核心执行逻辑。

如果某项因环境或依赖无法验证，明确列出，不能声称全部通过。

------------------------------------------------------------------------

## 11. 分阶段实施计划

必须按阶段执行。每阶段完成后更新进度记录，运行对应测试，再进入下一阶段。

### Phase 0 --- Audit & Baseline

产物： - 引用 `openspec/changes/refactor-to-policy-driven-engine/audit.md`，只补充代码层面的审计； -
`docs/refactor/baseline.md` - 当前架构图； - 旧模块与目标模块映射； -
现有测试结果； - 风险和待决问题。

此阶段只审计和补必要的基线测试，不进行大规模重构。

### Phase 1 --- Core Contracts

工作： - 定义 `ChunkSpan`； - 定义最终 `Chunk`、`ChunkResult`； - 定义
`Chunker` Protocol； - 定义异常体系； - 为现有策略添加适配层； -
确保算法测试通过。

验收：策略输出不再承担最终组织和业务 Metadata 职责。

### Phase 2 --- Policy Layer

工作： - Policy Pydantic 模型； - YAML Loader； - 结构校验； -
策略参数语义校验； - Metadata DSL 校验； - 示例 YAML。

验收：合法 Policy 可加载，非法 Policy 有明确错误。

### Phase 3 --- Compiler & IR

工作： - 定义 Execution IR； - Policy → IR 编译； - 规范化 Policy
Hash； - 编译过程单元测试。

验收：Compiler 不执行切块，Runtime 不需要解析 YAML。

### Phase 4 --- Runtime & Organization

工作： - Registry 迁移； - Runtime Executor； - N 层 Organization； -
全局 Offset； - 最终 Chunk 构造； - Metadata Builder。

验收：单层、两层和三层端到端测试通过。

### Phase 5 --- Public API

工作： - `ChunkEngine.validate()`； - `ChunkEngine.compile()`； -
`ChunkEngine.execute()`； - 公共导出； - Provider 注入； - 旧 API
迁移说明。

验收：README 中的公共 API 示例可运行。

### Phase 6 --- Examples & Documentation

工作： - `novel.yaml`； - `markdown.yaml`； - `technical.yaml`； -
README； - API 使用说明； - Policy DSL 文档； - 架构说明； - 迁移说明。

验收：新用户可以仅依靠文档完成安装、加载 Policy、执行切块和读取结果。

### Phase 7 --- FastAPI Service（仅在 Core 稳定后）

工作： - FastAPI 请求/响应模型； - `POST /api/v1/chunks`； - 调用 Core
Engine； - 错误映射； - API 集成测试。

验收：HTTP 与 Python SDK 使用同一执行逻辑。

如果时间或仓库现状不允许完成所有阶段，优先完成 Phase
0--6。不得为了声称完成而降低核心验收标准。Phase 7 可以作为独立后续阶段。

------------------------------------------------------------------------

## 12. Git 与文件安全

-   开始前检查 `git status`。
-   用户已有未提交修改时，不得覆盖或清理。
-   不执行 `git reset --hard`、`git clean -fd`、强制 checkout
    等破坏性命令。
-   不删除旧实现，直到新实现测试通过且迁移路径明确。
-   大规模文件移动前先建立清晰的迁移计划。
-   每个阶段保持工作区处于可解释状态。
-   如果需要提交 Git commit，可以在本地创建阶段性提交，但不得
    push，除非用户明确要求。
-   不修改与 ChunkWeave 无关的文件。

------------------------------------------------------------------------

## 13. Agent 工作方式

你应自主完成可安全完成的工作，不要每完成一个文件就向用户提问。

每个阶段： 1. 说明本阶段目标和将改动的模块； 2. 检查依赖关系； 3.
实施最小必要修改； 4. 运行测试和静态检查； 5. 修复本阶段引入的问题； 6.
更新进度文档； 7. 总结本阶段实际完成情况； 8. 再进入下一阶段。

遇到以下情况必须暂停并报告，不得猜测： -
仓库中存在用户未提交的冲突修改，且无法安全绕开； - 现有设计与目标 DSL
存在实质冲突； - 算法基线测试显示旧实现存在影响新契约的严重缺陷； -
需要新增重量级依赖或大幅升级工具链； -
需要删除用户数据或执行不可逆操作； - 外部服务、API Key
或模型凭据缺失； - 无法判断某个行为是 bug 还是现有公开契约。

如果只是普通实现细节，可以依据本提示词和项目现有风格作出最小、可测试的决定，并在决策记录中说明。

### 进度记录文件

进度通过勾选 `openspec/changes/refactor-to-policy-driven-engine/tasks.md`
的任务记录（勾选时注明测试命令及结果）；未解决问题与下一阶段计划在该
Change 的讨论中同步。

设计决策写入 `openspec/changes/refactor-to-policy-driven-engine/design.md`：

记录： - 设计决策； - 与设计文档存在的差异； - 采用的解决方式； -
选择理由； - 可能的后续影响。

------------------------------------------------------------------------

## 14. 最终交付报告

全部工作结束后，输出一份真实、可核验的总结，至少包括：

1.  重构前后的架构差异；
2.  实际保留的旧算法和逻辑；
3.  新增、修改、删除的文件；
4.  新公共 API 使用示例；
5.  YAML DSL 示例；
6.  Policy → IR → Runtime 的实际执行流程；
7.  测试总数、通过数、失败数、跳过数；
8.  Ruff / 类型检查结果；
9.  尚未完成的功能；
10. 已知限制和风险；
11. 如何安装、运行测试和执行示例；
12. 是否实施了 FastAPI 阶段；
13. 是否创建 Git commit（如有，列出 commit ID；不得声称已 push）。

**禁止虚报测试结果、虚报文件修改、虚报功能完成。**

------------------------------------------------------------------------

## 15. 最终设计原则（不可违背）

-   Policy defines how to chunk and what metadata to produce.
-   Context supplies runtime values.
-   Compiler transforms Policy into Execution IR.
-   Runtime executes IR.
-   Strategy decides how to split text.
-   Organization decides how chunks relate to each other.
-   Metadata Builder creates business metadata.
-   Chunk represents one final chunk.
-   ChunkResult represents one execution.
-   ChunkWeave operates on cleaned text only.

**最重要的工程要求：在现有项目上渐进式重构，保留经过验证的算法能力，以测试证明每一步迁移正确。不要为了追求新架构而推倒重写。**
