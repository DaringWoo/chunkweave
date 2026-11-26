# Design

## Context

当前引擎为 0.1.0 Alpha、未发布 PyPI。架构为 Python 配置对象驱动：`ChunkEngine.chunk(text, config)` 接受 `FlatConfig`/`HierarchicalConfig`，元数据为 Common/Organization/Strategy/Custom 四组，Custom 由调用方逐次传入，Provider 经 `set_provider()` 引擎级注入，策略直接构造最终 Chunk，结果支持 `tree()` 视图与自研 JSON 序列化。目标架构见 `docs/design/chunkweave_api_design.md`：声明式 YAML Policy + Compiler + Execution IR + Runtime。本 Change 是规范迁移，不含代码实现。动机见 proposal.md「Why」；与现有 Spec 的逐条冲突分类及用户已确认决定见 `audit.md`。

## Goals / Non-Goals

**Goals:**

- 以 YAML Policy DSL 作为唯一的切块声明方式：组织层数由 `pipeline.levels` 层数表达，不再区分 Flat/Hierarchical 两套配置。
- 建立 Policy → Compiler → Execution IR → Runtime 的清晰分层，Runtime 只消费 IR。
- Metadata 定义权归 Policy：`value` 固定值、`source` Context 动态值；Context 只提供值。
- Chunk 统一携带系统字段 + `strategy_metadata` + 业务 `metadata`；ChunkResult 携带扁平 `chunks` 与执行追溯信息。
- 执行可追溯：`policy_id`/`policy_version`/`policy_hash`/`execution_id`/`engine_version`/`execution_time_ms`。

**Non-Goals:**

- HTTP Service（`POST /api/v1/chunks`）与 `policy_ref` 已发布 Policy 引用；设计 §12 明确在前十项完成后另行开发，列为后续 Change。
- `get_chunk`/`get_level`/`to_tree` 等结果便利方法与 Tree View。
- 可选 Metadata 字段（`required: false` 语义）。
- 文档解析、文本清洗、Embedding、向量库、RAG。
- 兼容层与 deprecation 周期（0.1.0 Alpha 未发布，直接替换）。

## Decisions

### Policy DSL 结构

采用 `api_version` + `policy`（`id`/`name`/`version`）+ `pipeline.levels`（每层 `name`/`strategy`/`params`）+ 可选 `metadata`（`fields`/`include`）四段顶层结构，与设计 §3、§5 一致。理由：把「切什么」（levels）、「怎么标注」（metadata）与「我是谁」（policy 身份）分开声明，Policy 可作为独立版本化资产。备选：将 `metadata.fields` 下放到各层——拒绝，因为业务字段应对所有层级 Chunk 一致生成（设计 §3.4 示例为单一层级效果），且层级附加元数据被明确移除。

`api_version` 固定为 `chunkweave/v1` 并显式校验，为将来 DSL 演进预留版本切换点；备选「不设 api_version」会让未来变更无判别依据。

### Metadata `value`/`source` 规则与 null 区分

每个字段必须且只能配置 `value` 或 `source` 之一；两者都有或都没有都在校验时报错。`value: null` 是合法固定值——模型层面必须区分「配置了 null」与「未配置 value」（设计 §5 明确要求，不能仅靠 `None` 判断）。实现上可用哨兵值或显式标记字段区分。备选「允许缺省字段补 null」拒绝：静默写入 `None` 会让缺失的 Context 路径与显式 null 无法区分（设计 §3.4、§11）。

### Context 职责

`execute(text, policy, context=None, provider=None)` 中的 `context` 只提供 `source` 引用路径的运行时值；`metadata` 键集合由 Policy `metadata.fields` 与 `include` 选项共同决定，Context 不能声明或改变键集合；未引用键不进入 `metadata`；`source` 路径缺失或 `context` 为 None 时 `execute()` 报错（不返回部分结果、不写 `None`）；解析到的值必须 JSON 可序列化。理由：与设计 §3.4 的职责表一致——Policy 定义字段、Context 提供动态值、Metadata Builder 负责生成。备选「Context 键全量合并进 metadata」拒绝：字段集合将随调用方变化，不可版本化。

### include 复制语义

`metadata.include` 控制把保留键**复制进**每个 Chunk 的 `metadata`，而不是隐藏 Chunk 属性：`include.organization: true` 时 `metadata` 含 `parent_id`、`level`、`sequence` 与 `level_name`（所在层 `name`）；`include.strategy: true` 时 `metadata` 含 `strategy` 与 `strategy_metadata`（与属性相等的独立副本，含嵌套映射）；两者缺省 `true`；关闭时仅 `metadata` 不含对应键。Chunk 属性（含 `strategy_metadata` 属性）无论开关都完整保留、不被清空。理由：向量库通常只存储 `metadata`，组织与策略信息必须进入 `metadata` 才能用于过滤与检索；这是对重构提示词 §4.4/§7.7「include 控制可选信息是否进入业务 Metadata」的定稿解释（对应 Q5、Q6）。备选「关闭时清空 `strategy_metadata` 属性」已放弃：属性是系统契约，不应被输出选项破坏。

### Metadata 字段保留键拒绝

`metadata.fields` 的字段名不得使用保留键：`chunk_id`、`content`、`parent_id`、`level`、`sequence`、`start_offset`、`end_offset`、`strategy`、`strategy_metadata`、`metadata`、`level_name`；违反时在加载阶段报含字段名的校验错误，与 `include` 取值无关；字段名必须为非空字符串。理由：保留键副本由引擎写入 `metadata`，若允许同名字段声明则存在两个写入方，语义不清；提前拒绝比冲突覆盖更可预测。备选「业务字段优先于保留键副本」拒绝：静默覆盖会让声明字段被引擎值替换，难以排查。

### Chunk / ChunkSpan / ChunkResult 模型（Pydantic V2）

采用 Pydantic V2 模型（设计 §4）：`Chunk` 含全部系统字段与两个映射字段；`ChunkSpan` 为策略输出的中间类型（`content`、相对输入文本的 `start_offset`/`end_offset`、`strategy_metadata`，字段名与 `Chunk` 一致），不进入公共序列化契约；`ChunkResult` 含扁平 `chunks` 与执行追溯字段。`total` 作为序列化输出中的计算字段：必须等于 `len(chunks)` 且出现在 `model_dump()`/`model_dump_json()` 结果中（设计 §8.3 的 HTTP JSON 含 `total`；实现上可用计算字段而非存储字段）。备选「`total` 仅为属性不进序列化」与设计 §8.3 矛盾（见已决定事项 Q7），故按「进序列化输出」定稿。

### Policy / Compiler / IR / Runtime 分层

沿用设计 §9 的分层：

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

Policy Layer 不执行切块；Runtime 不解析 YAML、不读取 Policy 原始字典，只消费 IR；IR 是衔接契约，包含 Policy 身份、`policy_hash`、经校验并补全缺省值的层 `params`、Metadata 字段解析计划与 include 选项，可序列化且不含 Provider 实例或可调用对象。`compile()` 供高级用户检查执行计划，非普通流程必需；`execute()` 内部完成校验与编译。备选「Runtime 直接消费 Policy 模型」拒绝：Policy 声明与执行计划耦合，无法表达「编译期补全/解析」与独立 Hash 语义。

### Registry 与策略参数 Schema、ChunkSpan 局部 Offset

策略协议改为返回 ChunkSpan 序列，Offset 相对该策略的输入文本（`start_offset`/`end_offset`，满足 `content == text[start_offset:end_offset]`）；每个策略声明参数 Schema（或等效校验能力）并声明是否需要 Provider，Registry 对外提供该 Schema 供 Policy 语义校验使用，替代被移除的 `metadata_keys` 声明。Runtime/Organization 负责把子层局部 Offset 加上父块基址换算为全局 Offset（沿用现有「全局 Offset 换算」契约）。备选「策略直接产出全局 Offset」拒绝：策略将不得不感知父块位置，破坏「策略单独可测、不依赖组织层」。

### 多层组织与 Offset

`pipeline.levels` 层数即组织层数：1 层平铺、2 层父子、N 层多级；第 i 层每个 Chunk 分别作为第 i+1 层输入，禁止合并再切；子块不越父界；父层 overlap 允许重复覆盖；分支无产出自然终止；默认不产生空 Chunk。这些算法行为沿用现有「多层执行/子块边界/全局换算/终止行为」契约，仅换载体。

### `chunk_id` 编号

沿用 ADR 0003：`chunk-NNNN` 顺序编号，层级结果由 Runtime 对全部输出做广度优先重编号，保证确定性生成与执行内唯一；层级信息只由 `parent_id`/`level`/`sequence` 表达，不编码进 `chunk_id`。

### `execution_id` 唯一

每次 `execute()` 生成全局唯一的 `execution_id`（UUID 类字符串）。理由：执行追溯需要区分两次相同输入的执行；`execution_id` 与 `execution_time_ms` 不参与序列化稳定性保证。备选「确定性派生」拒绝：两次相同执行将无法区分。

### Policy Hash 规范化方式

对解析后的 Policy 模型做规范化：键排序的 JSON → UTF-8 编码 → sha256，输出格式 `sha256:<64 位十六进制>`。规范化输入只含 Policy 模型自身的结构缺省值（如 `metadata.include`、空 `params`），不含编译期由策略 Schema 补全的参数缺省值，因此 Hash 不依赖 Registry 状态；省略 `include` 与显式写其缺省值、仅键顺序/空白/注释/引号风格不同的 YAML 得到相同 Hash；任一声明值变化得到不同 Hash；与 Context、text、Provider 无关。字段配置在规范化时只输出实际声明的那一个来源键，因此 `value: null` 与 `source: ...` 得到不同的规范化结果，「声明了 null」与「未声明 value」不会混淆。备选「对原始 YAML 文本 Hash」拒绝：等价 YAML 会得到不同 Hash。

### 未知字段严格拒绝

Policy 顶层、`policy`、`pipeline`、每个 level、`metadata`、`metadata.include` 与每个字段配置中的未知键报校验错误（含字段路径）；`value` 的内容不受此约束；`params` 未知参数由策略 Schema 拒绝。理由：延续「配置校验快速失败」原则，YAML 手误（如 `stragety:`）不应静默通过。这是相对现状的行为变化（现有代码静默忽略未知参数），用户已确认（见已决定事项 Q12）。

### Provider 按次注入

Semantic Provider 通过 `execute(provider=...)` 按次注入，不写入 Policy、不进入 Execution IR、不参与序列化；含 `semantic` 层而未提供 Provider 时在任何切块开始前报错。理由：Provider 是运行时对象不是声明内容；按次注入允许同一 Policy 换用不同 Provider。备选「引擎级 `set_provider`」拒绝：全局可变状态与 Policy 的不可变声明语义冲突（对应 audit Q10 采用带 `provider` 的签名）。

### 公共注册方法

公共注册入口为 `ChunkEngine.register(name, factory, *, params_model, requires_provider=False, replace=False)`，委托内部 Registry。`params_model` 是参数 Schema（Pydantic 模型类）：引擎用它校验该层 `params`，并拒绝模型中未定义的键（无论模型自身的 extra 配置如何）；`factory(params, provider)` 接收已校验的参数对象与 Provider（不需要 Provider 的策略得到 `None`），返回 Chunker，其 `chunk(text)` 返回 ChunkSpan 序列；`requires_provider=True` 的策略被引用而 `execute()` 未提供 `provider` 时，在任何切块开始前报错。内置三个策略经同一机制注册（`semantic` 为 `requires_provider=True`）。默认拒绝同名覆盖，`replace=True` 显式替换。理由：扩展入口属于公共 API 面，调用方不应实例化内部 Registry；参数 Schema 与 Provider 需求在注册时显式声明，让「缺 Provider」能在任何切块开始前失败。备选「注册时不声明 Provider 需求、执行时由策略自查」拒绝：错误会延迟到层执行时才出现，可能已产生部分切块。

### 兼容性与迁移策略

直接替换，不保留兼容层（0.1.0 Alpha 未发布 PyPI，用户已确认 BREAKING，见 audit.md §5）。旧 → 新映射：

| 旧 API | 新 API |
|---|---|
| `FlatConfig(strategy, ...)` | 单层 `pipeline.levels` |
| `HierarchicalConfig(levels=[...])` | `pipeline.levels`（多层） |
| `engine.chunk(text, config)` | `engine.execute(text, policy, context=None, provider=None)` |
| `custom={...}` 参数 | `metadata.fields`（`value`/`source`）+ `context` |
| `engine.set_provider(p)` | `engine.execute(..., provider=p)` |
| `result.tree()` | 按 `parent_id` 自行重建层级 |
| `result.to_json()` | `result.model_dump_json()` |
| `metadata_keys` 声明 | `register(..., params_model=...)` 参数 Schema 声明 |
| `ConfigError` | `PolicyValidationError`（加载阶段为 `PolicyLoadError`） |

### 依赖变化

核心依赖新增 `pydantic>=2` 与 `PyYAML`（数据校验库与 YAML 解析库），均为轻量依赖；开发依赖新增 `types-PyYAML`；不引入大型模型库或 RAG 框架。Semantic Provider 相关实现仍以可选依赖或零依赖方式提供。

### 实施决策

- [扁平模块布局] → 延续 448d132 的刻意扁平化，不建 `policy/`、`compiler/` 子包；最终为 `models.py`、`strategies.py`、`policy.py`、`compiler.py`、`metadata.py`、`organization.py`、`engine.py`。
- [新旧并存迁移顺序] → 第 1 批新增新契约（ChunkSpan、参数模型、新 Chunker、Policy 层），旧 API 继续可用；旧 dataclass 驱动包装器改名为 `LegacySlidingWindowChunker`/`LegacyRecursiveChunker`/`LegacySemanticChunker`，接收旧 config、委托新 Chunker、转回旧 `Chunk`，随旧 API 在第 2 批删除。
- [分隔符声明形式 `SeparatorSpec`] → `params` 保存可 JSON 序列化的声明形式（字面量字符串或 `{value, regex}` 映射），Chunker 构造时才编译为 `re.Pattern`；`regex: true` 的 pattern 在参数校验阶段必须能编译。
- [参数与 Policy 字段严格类型] → 整数字段拒绝 bool/字符串/float（`StrictInt`），`threshold` 拒绝 bool 与字符串、存为 float，`version` 拒绝 YAML 解析出的 `1.0` 浮点（`StrictStr` + `MAJOR.MINOR.PATCH` 正则）。
- [`MetadataFieldConfig` 只序列化声明的来源键] → 以 `model_fields_set` 判定 `value`/`source` 恰好声明一个，自定义序列化只输出该键；`{"value": null}` 与 `{"source": ...}` 可区分且 `model_dump()` 往返不漂移（Policy Hash 依赖这一点）。
- [入口参数类型检查] → `execute`/`compile`/`validate` 对非 `Policy` 实例（dict、YAML 字符串、路径）抛 `TypeError` 并提示用 `Policy.from_file`/`from_yaml` 加载；`execute` 对非 `str` 的 `text` 同样抛 `TypeError`。
- [`validate` 返回 None] → 只做编译与语义校验，不切块、不产 IR 给调用方；校验失败照常抛 `PolicyValidationError`。
- [`execution_id` 为 uuid4 字符串] → 每次 `execute` 生成 `str(uuid.uuid4())`。
- [`requires_provider` 记录在 IR] → `PlanLevel.requires_provider` 是布尔声明，不是 Provider 实例；IR `model_dump_json()` 完全可序列化，Provider 只在 `execute` 调用边界注入。
- [Context 在切块前解析] → `resolve_fields` 先于任何 Chunker 调用执行，空文本也照样解析，失败抛 `ContextResolutionError` 且不产出部分结果。
- [丢弃空 span] → Runtime 丢弃 `content` 为空的 `ChunkSpan`，编号只计保留的 span；某父块无子块时该分支终止。
- [排序由 Runtime 完成] → `organization.run` 末尾按 `(start_offset, level)` 稳定排序；`ChunkResult` 模型本身不排序。
- [`engine_version` 来源] → 函数内 `from . import __version__` 取得，避免循环导入，版本号不在第二处硬编码。

## Risks / Trade-offs

- [YAML 隐式类型坑] → `2024-01-01` 会被解析成日期（因不可 JSON 序列化报校验错误），`no`/`yes`/`on`/`off` 会被解析成布尔值；`docs/configuration.md` 与 `docs/metadata.md` 必须提醒用户给这类值加引号。
- [BREAKING 无兼容层，存量调用方代码全部失效] → 版本仍为未发布的 0.1.0 Alpha，迁移映射表在 Decisions 与后续文档中提供；若届时已有外部用户，需另开 Change 提供 deprecation。
- [Pydantic V2 引入首个核心依赖] → 其为轻量纯校验库且设计 §4 明确要求；`pip install` 契约已相应更新。
- [Policy Hash 依赖 Policy 模型的结构缺省值] → 若未来改变 Policy 模型的结构缺省值需另行评估 Hash 兼容性；`params` 内省略参数与显式写出其缺省值得到不同 Hash，这是有意保留的「声明值不同」语义。

## Open Questions

以下对应 `audit.md` §6 的 Q1–Q12。用户在复查后已做出决定，按「已决定事项」与「仍未决定」记录；决定即本 Change delta 已固化的行为。

### 已决定事项

- **Q1** Policy 身份信息访问路径（设计 §5 示例与模型结构不一致）→ `policy.id`/`policy.name`/`policy.version` 直接访问与 `policy.policy.id` 等嵌套路径**都支持**。
- **Q2** 策略返回 `list[Chunk]` 还是 `ChunkSpan` → 采用 ChunkSpan（`content`、`start_offset`、`end_offset`、`strategy_metadata`）。
- **Q3** 注册名 `sliding` vs `sliding_window` → 沿用 `sliding_window`。
- **Q4** `semantic` 层 `chunk_size` 是否必填 → 保持必填（重构提示词 §4.3 示例也写了 `chunk_size: 800`；设计 §3.3 示例按契约会校验失败）。
- **Q5** `include.organization` 的可观察效果 → 采用复制语义（见 Decisions「include 复制语义」），关闭时 `metadata` 不含 `parent_id`/`level`/`sequence`/`level_name` 四个键。
- **Q6** 层级 `name` 是否出现在 Chunk 上 → 层名以 `level_name` 键经 `include.organization` 进入 `metadata`；Chunk 不新增属性。
- **Q7** `ChunkResult.total` → 进入序列化输出（可用计算字段实现），等于 `len(chunks)`。
- **Q9** `policy.version` 格式 → `MAJOR.MINOR.PATCH` 三段非负整数。
- **Q10** `execute()` 签名 → `execute(text, policy, context=None, provider=None)`。
- **Q11** Execution IR / Execution Planner / `ExecutionPlan` 名称 → 术语统一为 Execution IR，公共类型名 `ExecutionPlan`。
- **Q12** 未知字段处理 → 严格拒绝并报含字段路径的校验错误（用户已确认）。

### 仍未决定

- **Q8** Semantic 依赖外部模型时「应记录模型标识、版本和关键参数」，Provider 协议未定义提供方式 → 留待后续 Change 扩展 Provider 协议。

### 已知限制

- OpenSpec 2.1.0 不允许在 MODIFIED 中删去既有 Scenario 标题（`validate` 报「omits scenario(s)」错误），因此正式 Spec 中 `Flat 一键执行`、`层级配置执行`、`组织配置非法报错`、`策略声明元数据键` 四个 Scenario 标题仍带旧术语，正文已是新契约；未来如有需要可用 REMOVED+换名 ADDED 清理。
