# ChunkWeave OpenSpec 规范迁移 Agent 提示词

> **任务类型：** OpenSpec 规范迁移与新 Change 创建\
> **执行范围：** 只修改 OpenSpec 规范及其 Change 文件，不修改 Python
> 源码\
> **目标：** 将现有 OpenSpec 从旧的 Config 驱动设计迁移到新的 YAML
> Policy 驱动架构，为后续代码重构建立唯一、明确、可审查的规范依据。

------------------------------------------------------------------------

# 0. 任务指令

你现在负责在当前打开的 ChunkWeave 仓库中，完成一次 OpenSpec 规范迁移。

本次任务不是代码重构，也不是重新实现 ChunkWeave。你必须先审计仓库中的
OpenSpec 文件，再根据项目现状和指定的 API Design 文档，创建一个新的
OpenSpec Change，并更新正式 Specs。

**本次只允许修改 `openspec/` 下的文件。不得修改
`src/`、`tests/`、`server/`、`pyproject.toml`、README
或其他项目代码和配置。**

如果需要记录审计结果，可以写入 `openspec/changes/<change-id>/` 内的
Change 文档，不要在本任务中实施代码变更。

## 0.1 设计依据

开始前，先定位并阅读以下设计文档：

1.  `docs/design/api-design.md`：新的 ChunkWeave 公共 API
    和目标架构设计，是本次规范迁移的主要设计输入。
2.  当前 `openspec/config.yaml`：OpenSpec 项目约定。
3.  当前 `openspec/specs/` 下所有正式 Spec。
4.  当前 `openspec/changes/` 下所有未归档 Change。
5.  `openspec/changes/archive/` 下与现有能力相关的历史
    Change，用于理解决策背景，不得将历史文档当作当前规范。

如果 `docs/design/api-design.md` 不存在： - 不要自行创建替代版本； -
不要凭记忆或本提示词补全设计文档； -
暂停迁移，报告缺失文件和需要用户提供的路径。

如果实际目录、Spec 名称或 Change
状态与本提示词中的预期不同，以仓库当前实际内容为准，并在审计报告中说明。

## 0.2 本次任务的核心原则

1.  正式 Spec 描述系统当前应满足的行为契约。
2.  新 Change 描述这次迁移将如何改变正式 Spec。
3.  历史 Archive 只保留历史，不直接改写。
4.  API Design 是设计输入；OpenSpec Change
    是规范变更载体；归档后更新的正式 Spec 才是后续实现的规范依据。
5.  不得把实现计划、目录结构或代码细节全部机械复制进 Spec。Spec
    应描述可验证的能力和行为。
6.  不得在本次任务中实现 Python 代码。
7.  不得为了让 Spec 看起来完整而虚构未讨论的功能。
8.  发现设计文档内部存在歧义或矛盾时，先记录问题，不得擅自选择一种解释并隐藏分歧。
9.  不得删除现有 Spec、Archive 或用户已有未提交内容。
10. 未经用户明确要求，不执行 Git commit、push、发布或其他远程操作。

------------------------------------------------------------------------

# 1. 第一步：OpenSpec 仓库审计

在写入任何文件之前，完成审计。

## 1.1 检查目录

检查并记录：

``` text
openspec/
├── config.yaml
├── specs/
├── changes/
└── changes/archive/
```

实际目录可能不同，以仓库为准。

## 1.2 检查正式 Spec

此前项目资料中出现过以下 Spec
名称。它们是审计线索，不代表当前仓库一定仍然使用这些名称：

  ----------------------------------------------------------------------------
  Spec                                重点检查内容
  ----------------------------------- ----------------------------------------
  `chunk-model`                       Chunk 数据模型、字段、Metadata
                                      结构、序列化

  `chunk-organization`                Flat / Hierarchical
                                      配置、父子关系、Offset、层级

  `chunking-api`                      Engine 公共入口、配置参数、返回结果

  `chunking-strategies`               Sliding Window、Recursive、Semantic
                                      的行为和输出契约

  `strategy-registry`                 策略注册、工厂、参数校验、扩展协议

  `package-distribution`              Python
                                      版本、依赖、打包、文档、测试和发布要求
  ----------------------------------------------------------------------------

逐份阅读实际存在的 Spec，提取： - 当前 Requirements； - 每个 Requirement
下的 Scenarios； - 关键术语和字段； - 对公共 API 的约束； - 与其他 Spec
的交叉引用； - 已经实现或仍未实现的能力（如果仓库资料能够证明）。

不要仅根据文件名判断冲突，必须阅读正文。

## 1.3 检查 Changes

检查： - `openspec/changes/` 下是否有活动 Change； - 每个 Change 的
proposal、design、tasks、spec delta； -
是否有尚未完成或与本次迁移冲突的工作。

如果存在活动 Change： - 不要擅自删除、覆盖或归档； -
分析它与本次迁移的关系； -
如果可能冲突，先记录并暂停可能覆盖其内容的操作。

## 1.4 检查 Archive

此前项目资料中出现过以下历史 Change 名称，作为检索线索：

-   `add-core-models-and-strategies`
-   `add-organization-and-api`
-   `add-packaging-and-release`

以实际 Archive
为准。阅读相关历史内容，了解旧架构为何如此设计、哪些行为要求仍有价值。

**不得修改或删除 `openspec/changes/archive/` 中的历史文件。**

## 1.5 生成审计结果

在新 Change 创建前，先形成审计摘要，写入新 Change 的 proposal 或单独的
`audit.md`。

至少包含：

  -----------------------------------------------------------------------
  文件 / Spec       现有契约          与新设计的关系    建议处理
  ----------------- ----------------- ----------------- -----------------
  实际 Spec 名称    摘要旧要求        无冲突 / 部分冲突 保留 / 修改 /
                                      / 直接冲突        拆分 / 新增

  -----------------------------------------------------------------------

必须区分： - **直接冲突**：新旧契约不能同时成立； -
**部分冲突**：部分要求需要调整，其他行为应保留； -
**无冲突**：可以继续作为当前规范； - **缺少依据**：现有资料不足以判断。

审计完成后再开始创建 Change。

------------------------------------------------------------------------

# 2. 新架构的目标契约

以下内容来自本次目标设计。正式写入 Spec 前，必须与
`docs/design/api-design.md` 核对；如有冲突，以设计文档为准，并记录差异。

## 2.1 产品边界

ChunkWeave 是声明式文本切块引擎，只处理已经清洗、标准化的文本。

属于 ChunkWeave： - YAML Policy DSL； - Policy 加载、解析和校验； -
Policy Compiler； - Execution IR； - Strategy Registry； - Sliding
Window、Recursive、Semantic 等切块策略； - 多层 Chunk 组织； - Metadata
生成； - Chunk 与 ChunkResult； - 执行追溯信息。

不属于 ChunkWeave： - PDF / Word / HTML 文档解析； - OCR； -
文本清洗和格式标准化； - Embedding； - Milvus / Qdrant 等向量数据库； -
RAG 检索； - RAGAS 评估。

不得将上述非职责范围扩展为本次 Spec 的新能力。

## 2.2 声明式 Policy

用户通过 YAML 描述： - Policy 身份与版本； - `pipeline.levels`； -
每一层的名称、策略和参数； - Metadata 字段定义； - Metadata
固定值或动态值来源； - 可选的策略元数据、组织元数据输出选项。

一个 level 表示一层切块： - 1 层：平铺； - 2 层：父子； - N
层：多级组织。

不再要求用户分别选择 Flat / Hierarchical 两套组织配置。

目标示例：

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

metadata:
  fields:
    document_type:
      value: novel

    document_id:
      source: context.document_id

    document_name:
      source: context.document_name

  include:
    strategy: true
    organization: true
```

Metadata 定义规则： - `value`：在 YAML Policy 中定义固定值； -
`source`：从运行时 Context 路径读取动态值； -
同一字段必须且只能配置一种来源； - 必需的 Context
路径缺失时，应给出明确错误； - 业务 Metadata 不得覆盖 Chunk 系统字段； -
Python `context` 只提供动态数据，不负责声明 Metadata 字段。

## 2.3 公共 Python API

目标使用方式：

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
```

目标公共方法： - `Policy.from_file(path)` -
`Policy.from_yaml(yaml_text)` - `ChunkEngine.validate(policy)` -
`ChunkEngine.compile(policy)` -
`ChunkEngine.execute(text, policy, context=None, provider=None)`

普通使用者通常只需调用 `execute()`；它内部完成必要的校验和编译。

Semantic Provider 通过依赖注入提供，不写入 YAML，也不作为普通 Metadata
序列化。

## 2.4 目标 Chunk 模型

目标 Chunk 具有明确的系统字段：

  字段                  含义
  --------------------- --------------------------------------------
  `chunk_id`            Chunk 标识
  `content`             文本内容
  `parent_id`           直接父 Chunk ID；根节点为 None
  `level`               层级，从 0 开始
  `sequence`            同一父节点下的顺序
  `start_offset`        输入文本中的全局起始字符偏移
  `end_offset`          输入文本中的全局结束字符偏移
  `strategy`            生成该 Chunk 的策略名称
  `strategy_metadata`   策略产生的额外信息
  `metadata`            根据 Policy 和 Context 生成的业务 Metadata

Offset 采用 Python 字符索引，左闭右开
`[start_offset, end_offset)`，相对于传入的清洗后文本。

最终 Chunk 采用统一模型。单层 Chunk 的
`parent_id=None`、`level=0`，不另设 Flat 专属模型。

## 2.5 ChunkSpan 与最终 Chunk 的职责分离

目标内部契约：

-   Strategy 负责如何切分文本；
-   Strategy 输出 `ChunkSpan`；
-   `ChunkSpan` 仅表达文本片段、局部/全局
    Offset（按内部协议明确）和策略元数据；
-   Organization 负责建立父子关系、层级和顺序；
-   Metadata Builder 根据 Policy 和 Context 生成业务 Metadata；
-   Runtime 统一构造最终 Chunk。

策略不得负责最终 `chunk_id`、`parent_id`、`level`、`sequence` 或业务
Metadata。

## 2.6 Policy / Compiler / IR / Runtime

目标分层：

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
Runtime
    |
    +---- Strategy Registry / Chunkers
    +---- Organization
    +---- Metadata Builder
    |
    v
ChunkResult
```

要求： - Policy Layer 负责解析和校验； - Compiler 将 Policy
转成已解析、已校验的 Execution IR； - 编译不执行切块； - Runtime 只消费
IR，不直接解析 YAML； - IR 是 Policy 和 Runtime 的衔接契约； - IR
不包含不可序列化的 Provider 实例； - Runtime 执行策略、组织 Chunk、生成
Metadata 和结果； - 不得把 IR 简化为原始 YAML 字典的无意义复制。

------------------------------------------------------------------------

# 3. 正式 Spec 的迁移要求

根据实际审计结果修改，不要机械照搬下面的文件清单。

## 3.1 `chunk-model`

若该 Spec 存在，重点更新： - 从 dataclass 迁移到 Pydantic V2
的目标模型要求（仅当 API Design 确认）； -
`parent_id`、`level`、`sequence` 成为 Chunk 系统字段； -
`strategy_metadata` 与业务 `metadata` 分离； - 统一单层和多层 Chunk
模型； - ChunkResult 保存扁平 `list[Chunk]` 和执行信息； - JSON / Python
序列化行为。

保留仍有效的要求，例如： - 文本内容与 Offset 对应关系； - Unicode
字符索引约定； - Chunk ID 唯一性； -
数据模型不可变性或可变性约束（以现有有效设计和 API Design 为准）。

不得因为模型字段变化而丢失有价值的旧行为要求。

## 3.2 `chunk-organization`

若该 Spec 存在，重点更新： - 统一使用 `pipeline.levels` 表达组织层级； -
一层就是平铺，不再要求独立 Flat 配置； - 多层执行按层级顺序进行； -
下一层分别处理每个父 Chunk； - 父子关系通过 `parent_id`； - Offset
转换为输入文本的全局字符偏移； - `level`、`sequence` 规则； -
空子节点、Overlap 和多层组织行为。

保留已经验证的组织算法行为，不要只留下架构口号。

## 3.3 `chunking-api`

若该 Spec 存在，重点更新： - 旧 `engine.chunk(text, config)` 迁移为
`engine.execute(text, policy, context=...)`； - Policy 加载方法； -
`validate()`、`compile()`、`execute()` 的职责； - `ChunkResult`
的执行追溯字段； - 统一结果序列化； - 旧 API 的弃用或移除策略。

是否保留兼容层必须依据当前版本、已有用户和 API Design
判断，不得擅自承诺长期兼容。

## 3.4 `chunking-strategies`

该 Spec 应以保留算法行为为首要目标。

保留现有策略的行为要求，包括实际 Spec 中已经定义的： - Sliding Window
窗口推进和 overlap； - Recursive separator 优先级和保留方式； -
Recursive fallback； - Semantic 阈值和 Provider 行为； -
批量与逐对评分路径（如果已有）； - 超长语义片段的兜底； - Unicode 和
Offset 语义。

只更新必要的输出契约： - 从直接构造最终 Chunk 改为输出 ChunkSpan； -
策略不负责最终组织和业务 Metadata。

不要凭空增加算法参数，也不要删掉现有算法场景。

## 3.5 `strategy-registry`

若该 Spec 存在，保留有效的 Registry 行为： -
策略名称到工厂/实现的映射； - 内置策略注册； - 自定义策略注册； -
重复注册处理； - 未知策略错误； - 扩展方式。

更新： - Chunker 输出契约适配 ChunkSpan； - Registry 提供策略参数 Schema
或等效校验能力，供 Policy Validator 使用； - 业务 Metadata
字段不再由策略声明； - Registry 不负责组织、YAML 解析和 Metadata 生成。

## 3.6 `package-distribution`

只修改确实与新设计冲突的规范，例如： - 文档交付位置； - 示例 Policy
文件； - 新公共 API 文档； - 新依赖约束（只有 API Design 明确要求时）。

保留与架构无关的： - Python 版本要求； - 包构建和发布要求； - CI； -
Ruff / pytest / 类型检查； - 依赖轻量化； - 版本管理和发布约束。

不要因为新增 Policy Engine 就无理由引入大型依赖。

------------------------------------------------------------------------

# 4. 新增 Spec 的评估

新架构增加了 Policy 和 Compiler 概念。请评估是否需要新增以下正式 Spec：

## 4.1 `policy-engine`

建议覆盖： - Policy YAML DSL； - Policy 文件和字符串加载； - Policy
Model； - 结构校验； - 策略参数校验； - Metadata DSL； - Context
动态值路径解析； - 明确的校验错误； - API 版本识别。

## 4.2 `policy-compiler`

建议覆盖： - Policy 到 Execution IR 的编译； - 编译前后的校验边界； - IR
的数据结构与职责； - 编译不执行切块； - 稳定的 Policy Hash； - Runtime
只依赖 IR。

是否拆分为两个 Spec，应根据现有 OpenSpec
的粒度和项目术语判断。不要为了凑数量新增 Spec。

如果 `policy-engine` 和 `policy-compiler`
的职责在当前项目规模下更适合放在一个 Spec 中，可以合并，但必须在 design
中解释原因。

Runtime 不必自动新增独立 Spec。优先判断现有 `chunk-organization` 或
`chunking-api` 是否能清晰承载 Runtime
的行为契约。只有职责明显过载或边界无法表达时，才提议新增
`chunk-runtime`。

------------------------------------------------------------------------

# 5. 新 Change 的创建要求

建议 Change ID：

``` text
refactor-to-policy-driven-engine
```

若该 ID 已存在，不得覆盖；检查其状态并选择不冲突的 ID，记录原因。

Change 至少包含 OpenSpec 当前版本和仓库约定要求的文件，例如： -
`proposal.md` - `design.md` - `tasks.md` -
`specs/<capability>/spec.md`（delta）

以仓库当前 OpenSpec 格式为准，不要假设固定文件布局。

## 5.1 Proposal

必须解释： - 当前旧架构的限制； - 为什么改为 YAML Policy 驱动； -
本次迁移的目标； - 影响的 Capabilities； - 不在本次范围内的功能； -
与历史 Change 的关系。

## 5.2 Design

必须说明： - Policy DSL 的结构； - Metadata `value` / `source` 规则； -
Context 的职责； - Chunk / ChunkSpan / ChunkResult 模型； - Policy /
Compiler / IR / Runtime 分层； - Registry 与策略输出协议； - 多层组织和
Offset； - 兼容性与迁移策略； - 重要设计取舍和未决问题。

Design 必须与 `docs/design/api-design.md` 一致。若发现不一致，列为 Open
Question，不得暗中改写设计输入。

## 5.3 Tasks

任务应按可验证阶段拆分： 1. OpenSpec 正式 Spec 迁移； 2. Policy DSL 与
Schema； 3. Chunk 数据模型； 4. ChunkSpan 和策略输出协议； 5. Compiler /
IR； 6. Runtime / Organization； 7. Metadata Builder； 8. 公共 API； 9.
测试与文档； 10. 后续 HTTP Service（如果 API Design
将其纳入本次变更范围）。

本次任务只创建规范和任务计划，不执行这些代码任务。

## 5.4 Spec Deltas

-   使用当前 OpenSpec 认可的 delta 格式；
-   对修改的 Capability 提供可验证的 Requirements 和 Scenarios；
-   删除旧要求时必须通过明确的 delta 删除语义表达；
-   不要把整个旧 Spec 粗暴替换成几句概述；
-   不得在 delta 中只写实现类名而不写用户可观察行为；
-   每个重要 Requirement 至少有能验证其行为的 Scenario；
-   术语应与 API Design 一致。

------------------------------------------------------------------------

# 6. OpenSpec 文档质量要求

## 6.1 Requirement 写法

Requirement 应表达系统必须满足的行为，避免纯实现细节。

优先采用： - WHEN / THEN； - GIVEN / WHEN / THEN； -
可观察输入和输出； - 明确错误条件； - 明确边界行为。

示例（仅示意）：

``` markdown
### Requirement: Policy Metadata Resolution

The system SHALL resolve metadata fields declared by a Policy.

#### Scenario: Resolve a fixed metadata value

- **WHEN** a Policy declares a field using `value`
- **THEN** each generated Chunk SHALL contain that fixed value in its business metadata.

#### Scenario: Resolve a required Context value

- **WHEN** a Policy declares a field using `source`
- **AND** the referenced Context path is missing
- **THEN** execution SHALL fail with an actionable validation error.
```

## 6.2 术语一致性

统一使用： - Policy - Context - Execution IR - ChunkSpan - Chunk -
ChunkResult - Chunker - Strategy Registry - Organization - Metadata
Builder - `pipeline.levels` - `params` - `strategy_metadata` -
`metadata`

不要混用旧术语，除非明确写在历史迁移说明中。

## 6.3 不要把实现提示词当成 Spec

本次 Change 应描述系统行为和架构约束，不应把 Coding Agent
的逐步操作指令复制进正式 Spec。

Agent Prompt、开发任务清单和正式行为规范是不同资产。

------------------------------------------------------------------------

# 7. 旧 Spec 与历史 Archive 的处理规则

1.  正式 Spec 中冲突的旧要求，通过新 Change 的 delta 修改。
2.  不冲突的旧要求保留。
3.  历史 Archive 一律只读，不修改、不删除、不重命名。
4.  不要把历史 Change 直接复制成新 Change。
5.  不要把旧 Spec 全部删除后只留下新架构标题。
6.  不要为了消除冲突而删除仍然有效的算法行为要求。
7.  新 Change 应明确说明它替代或调整了哪些旧契约。

------------------------------------------------------------------------

# 8. 本次任务的严格范围

允许： - 读取仓库文件； - 读取 API Design； - 读取 OpenSpec
Config、Specs、Changes、Archive； - 在 `openspec/changes/` 创建新的
Change； - 更新 `openspec/specs/` 正式 Spec（通过 Change delta
或仓库约定的流程）； - 创建 OpenSpec 审计报告和设计决策记录； - 运行
OpenSpec 校验或格式检查命令（如果项目已安装且命令可用）。

不允许： - 修改 Python 源码； - 修改测试代码； - 修改
`pyproject.toml`； - 修改 README； - 新增或升级 Python 依赖； - 修改历史
Archive； - 删除旧 Spec； - 执行代码重构； - 执行 Git commit / push； -
发布包。

如果 OpenSpec 工具的工作流要求先创建 Change，再通过归档更新正式
Spec，则遵守工具的正式流程，不要手工绕过。

------------------------------------------------------------------------

# 9. 验收标准

本次任务完成必须满足：

## 9.1 审计

-   已检查全部正式 Spec；
-   已检查全部活动 Change；
-   已检查相关历史 Archive；
-   每份 Spec 都有冲突分类和处理理由；
-   没有将推测写成仓库事实。

## 9.2 Change

-   创建一个新的、命名清晰的 Change；
-   Proposal 说明迁移动机和范围；
-   Design 与 API Design 一致；
-   Tasks 可执行、可验收；
-   Spec Deltas 覆盖全部必要契约变化；
-   新增 Policy / Compiler 能力有明确边界；
-   没有重复或过度拆分 Capability。

## 9.3 正式 Spec

-   旧冲突要求得到明确修改或删除；
-   仍然有效的算法要求得到保留；
-   新旧术语统一；
-   每个重要 Requirement 有可验证 Scenario；
-   历史 Archive 未被修改。

## 9.4 范围控制

-   没有修改任何 Python 源码；
-   没有修改测试代码；
-   没有修改包配置；
-   没有执行 Git commit 或 push。

## 9.5 工具校验

使用仓库当前安装的 OpenSpec CLI 或项目指定校验方式检查 Change。

如果工具不可用： - 不要伪造校验通过； - 报告尝试的命令和错误； -
进行人工格式检查； - 将工具校验标记为未完成。

------------------------------------------------------------------------

# 10. 最终交付报告

完成后给出简洁但可核验的报告：

1.  实际检查了哪些 Specs；
2.  哪些 Spec 存在直接冲突、部分冲突或无冲突；
3.  新建了哪个 Change；
4.  修改或新增了哪些正式 Spec；
5.  哪些旧要求被保留；
6.  哪些旧要求被替换或删除；
7.  新增了哪些 Capability，为什么；
8.  哪些设计问题仍需用户决定；
9.  OpenSpec 校验命令和实际结果；
10. 明确确认没有修改 Python 源码、测试、包配置或 Archive。

不要声称完成未执行的工作。

------------------------------------------------------------------------

# 11. 最终执行原则

本次工作是**规范迁移，不是代码实现**。

先理解现有 OpenSpec，再以 `docs/design/api-design.md`
为设计输入，通过一个新的 OpenSpec Change 完成正式规范的演进。

**不要改写历史，不要删除有效规范，不要提前动代码。先让 OpenSpec
准确描述新的 ChunkWeave，再进入下一阶段的代码重构。**
