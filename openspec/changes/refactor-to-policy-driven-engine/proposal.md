# Proposal

## Why

现有引擎由 Python 配置对象驱动：调用方必须在 Flat 与 Hierarchical 两套配置模型之间选择，业务元数据由调用方以 Custom 元数据参数逐次传入，配置不是可版本化的工程资产，执行结果缺少 Policy 身份与内容 Hash 等追溯信息，策略层直接构造最终 Chunk 导致切块、组织与元数据职责耦合。本次迁移按 `docs/design/chunkweave_api_design.md` 将引擎重构为 YAML Policy 驱动的声明式架构：Policy 声明切块方式与 Metadata 生成规则，Context 只提供动态值，Compiler 产出 Execution IR，Runtime 只消费 IR 执行。

## What Changes

- 引入 YAML Policy DSL：`api_version`、`policy`（`id`/`name`/`version`）、`pipeline.levels`（每层 `name`/`strategy`/`params`）、`metadata`（`fields` 的 `value`/`source` 与 `include` 选项）。
- 引入 Policy 加载与校验：`Policy.from_file(path)`、`Policy.from_yaml(yaml_text)`，区分结构校验、语义校验与执行期 Context 校验。
- 引入 Policy Compiler：`compile(policy)` 产出 Execution IR（公共类型名 `ExecutionPlan`），含 Policy 身份、稳定 `policy_hash`、经校验并补全缺省值的各层 `params`、Metadata 字段解析计划与 include 选项；编译不执行切块。
- 统一执行入口：`ChunkEngine.validate(policy)`、`compile(policy)`、`execute(text, policy, context=None, provider=None)`；`execute()` 内部完成校验与编译，结果携带 `policy_id`/`policy_version`/`policy_hash`/`execution_id`/`engine_version`/`execution_time_ms` 执行追溯信息。
- 统一组织表达：`pipeline.levels` 层数即组织层数，1 层平铺、2 层父子、N 层多级；策略输出 ChunkSpan（片段文本、相对输入的 Offset、`strategy_metadata`），Organization 统一填充 `parent_id`/`level`/`sequence`，业务 `metadata` 由 Metadata Builder 按 Policy 生成。
- 统一 Chunk 模型：所有 Chunk 携带 `chunk_id`、`content`、`parent_id`、`level`、`sequence`、`start_offset`、`end_offset`、`strategy`、`strategy_metadata`、`metadata` 系统与声明字段；`ChunkResult` 为扁平 `chunks` 列表加执行信息。
- Semantic Provider 改为按次注入：`execute(provider=...)`，不写入 Policy、不进入 Execution IR、不参与序列化。
- `metadata.include` 采用复制语义：保留键（`parent_id`/`level`/`sequence`/`level_name`/`strategy`/`strategy_metadata`）按开关复制进 `metadata`，缺省全启用，Chunk 属性始终完整保留；`metadata.fields` 字段名不得使用保留键，否则加载阶段报错。
- 自定义 Chunker 注册接口定为 `register(name, factory, params_model=..., requires_provider=..., replace=...)`：`params_model` 为参数 Schema，`requires_provider` 声明 Provider 需求，内置策略经同一机制注册。
- 异常体系调整：保留 `ChunkweaveError` 基类，新增 `PolicyLoadError`、`PolicyValidationError`（含子类 `UnregisteredStrategyError`）、`ContextResolutionError`，删除 `ConfigError`、`MetadataConflictError`。
- **BREAKING** 移除 `engine.chunk(text, config)` 入口、`FlatConfig`/`HierarchicalConfig` 配置模型、引擎级 `set_provider`、调用方传入的 Custom 元数据与 Tree View（`to_tree()` 及层级附加元数据、Custom 继承）；不保留兼容层。理由：当前版本 0.1.0 为 Alpha 且未发布 PyPI，无既有用户需要兼容（见 audit.md §5）。
- 序列化改为 `model_dump()`/`model_dump_json()` 并可往返重建；核心依赖新增数据校验库（Pydantic V2）与 YAML 解析库（PyYAML，仅安全解析）。
- 审计结论：6 份正式 Spec 的逐条冲突分类（直接冲突/部分冲突/无冲突）与用户已确认决定见 `audit.md`，本 Change 的 delta 按该分类执行。

### Non-Goals

- HTTP Service（`POST /api/v1/chunks`）：设计 §12 明确在前十项完成后再做，列为后续 Change。
- `policy_ref` 已发布 Policy 引用与 Policy Governance 后台。
- `get_chunk`/`get_level`/`to_tree` 等结果便利方法。
- 可选 Metadata 字段（`required: false` 语义）。
- 文档解析（PDF/Word/HTML）、OCR、文本清洗、Embedding、向量数据库与 RAG 检索。

## Capabilities

### New Capabilities

- `policy-engine`: YAML Policy DSL 结构、`Policy` 加载（文件/字符串）、结构与语义校验、Metadata 字段声明规则（`value`/`source` 互斥、Context 路径语法、include 选项）与 API 版本识别。
- `policy-compiler`: Policy 到 Execution IR 的编译契约（`ExecutionPlan` 内容、缺省值补全、编译不执行切块、IR 可序列化且不含运行时对象）、稳定 `policy_hash` 与 Runtime 只消费 IR 的依赖边界。

### Modified Capabilities

- `chunk-model`: Chunk 系统字段扩展（`parent_id`/`level`/`sequence`/`strategy`/`strategy_metadata`/`metadata`）、系统字段与业务 Metadata 分离、策略参数载体改为 `params`、校验时机与错误信息、`model_dump()` 序列化契约、新增 `ChunkResult` 模型与顺序要求；删除四组元数据结构与 Custom 元数据规则。
- `chunk-organization`: Flat/Hierarchical 合并为 `pipeline.levels` 多层 Pipeline 语义（「Hierarchical 多层执行」重命名为「多层 Pipeline 执行」）、单层即平铺、组织字段对单层同样填充、终止行为更新；元数据组装改为按 Policy 声明的业务 Metadata 生成与 Metadata 输出选项。
- `chunking-api`: 公共入口改为 `Policy` + `validate`/`compile`/`execute`；`execute` 只接受 Policy 对象；Provider 按次注入取代 `set_provider`；新增 `validate` 契约与执行追溯信息；删除结果视图（Tree View）。
- `chunking-strategies`: Semantic Provider 注入方式改为 `execute(provider=...)`；策略输出契约改为 ChunkSpan 且不负责系统字段与业务 `metadata`；其余算法行为不变。
- `strategy-registry`: 策略协议输出改为 ChunkSpan、删除 `metadata_keys` 声明、新增参数 Schema 声明要求；Registry 职责边界明确不含 YAML 解析与 Metadata 生成。
- `package-distribution`: 核心依赖边界更新（数据校验库与 YAML 解析库）、可选依赖边界措辞、文档与示例清单改为 Policy DSL 与 `examples/policies/`。

### 与历史 Change 的关系

- `2026-11-25-add-core-models-and-strategies`：确立三种算法与 Registry。本 Change 保留其全部算法行为要求，只改输出契约（ChunkSpan）与参数载体（`params`）。
- `2026-11-25-add-organization-and-api`：确立 Flat/Hierarchical、四组元数据、Custom 继承、`engine.chunk(config)` 与 Tree View。本 Change 替换其组织表达、元数据模型与公共 API，保留逐父块下切、子块不越界、全局 Offset 换算与终止行为。
- `2026-11-25-add-packaging-and-release`：确立打包、文档、示例与 CI。本 Change 只修改依赖、文档与示例三条要求。
- 分类明细见 `audit.md` §2；Archive 保持只读。

## Impact

- 受影响的代码：`src/chunkweave/` 全部模块将按新契约重构（本 Change 仅规范迁移，不含代码实现）。
- 受影响的公共 API：移除 `ChunkEngine.chunk`、`FlatConfig`、`HierarchicalConfig`、`set_provider`、`ChunkResult.tree()`；新增 `Policy.from_file`/`from_yaml`、`ChunkEngine.validate`/`compile`/`execute`、`ChunkEngine.register`、`ExecutionPlan`。
- 依赖变化：核心依赖新增 Pydantic V2 与 PyYAML（开发依赖加 `types-PyYAML`）；仍不引入大型模型库或 RAG 框架。
- 异常面变化：`ConfigError`、`MetadataConflictError` 移除，改为 `PolicyLoadError`/`PolicyValidationError`/`ContextResolutionError` 等按阶段可捕获的异常。
- 测试与基准：`tests/` 中绑定旧 API 的用例需迁移或删除，`benchmarks/` 移植到新 API。
- 文档与示例：`docs/configuration.md`、`docs/metadata.md`、组织方式文档与全部 `examples/` 需按新 API 重写，新增 `examples/policies/` YAML Policy。
- 版本与发布：仍为 0.1.0 Alpha、未发布 PyPI，BREAKING 无需兼容层与 deprecation 周期；不上传 PyPI、不创建远端 Release。
