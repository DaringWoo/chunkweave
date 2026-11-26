# OpenSpec 审计报告

审计日期：2026-11-26。审计对象：`openspec/` 全部正式 Spec、活动 Change 与历史 Archive。设计输入：`docs/design/chunkweave_api_design.md`。

## 1. 审计范围与仓库实况

| 项 | 实况 |
|---|---|
| OpenSpec CLI | `openspec` 2.1.0，schema `spec-driven` |
| `openspec/config.yaml` | 仅声明 `schema: spec-driven`，无 `context`、`rules` |
| 正式 Spec | `chunk-model`（10 条 Requirement）、`chunk-organization`（7）、`chunking-api`（5）、`chunking-strategies`（11）、`package-distribution`（8）、`strategy-registry`（6） |
| 活动 Change | 审计前无（`openspec list` 输出 `No active changes found.`）；本 Change 是唯一活动 Change |
| Archive | `2026-11-25-add-core-models-and-strategies`、`2026-11-25-add-organization-and-api`、`2026-11-25-add-packaging-and-release`，三者 tasks 全部勾选 |
| 代码现状（只读参考） | `src/chunkweave/` 七个模块，dataclass 模型，`ChunkEngine.chunk(text, config)` 接受 `FlatConfig`/`HierarchicalConfig`，`set_provider()` 引擎级注入，`ChunkResult.tree()`，`chunk_id` 为 `chunk-0000` 广度优先编号，正则分隔符序列化为 `{"value": ..., "regex": true}`，核心依赖为空，版本 `0.1.0`，未发布 PyPI |

与迁移提示词预期的差异：

- 提示词要求的设计文档路径为 `docs/design/api-design.md`，仓库实际文件为 `docs/design/chunkweave_api_design.md`。用户在会话中直接提供了该文件，本次以它为唯一设计输入。
- 提示词列出的 6 个 Spec 名称与 3 个历史 Change 名称与仓库一致（Archive 目录带日期前缀）。

## 2. 正式 Spec 冲突分类

分类定义：**直接冲突**（新旧契约不能同时成立）、**部分冲突**（部分要求需调整，其余保留）、**无冲突**、**缺少依据**。

### 2.1 `chunk-model`

| Requirement | 现有契约摘要 | 与新设计的关系 | 处理 |
|---|---|---|---|
| 统一 Chunk 结果模型 | 统一 Chunk 含 `chunk_id`/`content`/Offset；`chunk_id` 唯一、确定 | 部分冲突：新模型把 `parent_id`/`level`/`sequence`/`strategy`/`strategy_metadata`/`metadata` 设为系统属性 | 修改 |
| Offset 与长度单位语义 | 码点索引、左闭右开、全局换算 | 无冲突（设计 §4.1 相同） | 保留 |
| 元数据四组结构 | Common/Organization/Strategy/Custom 四组；Flat 不带层级字段 | 直接冲突：设计改为系统字段 + `strategy_metadata` + `metadata`，单层 Chunk 也带 `parent_id=None`/`level=0` | 删除，以新 Requirement 替代 |
| Custom 元数据规则与组装 | 调用方传 custom、保留字段冲突拒绝、逐块深拷贝 | 直接冲突：业务 Metadata 字段改由 Policy 声明，Context 只提供值 | 删除；"不共享可变对象""值 JSON 可序列化"两条仍有效的行为迁入 `chunk-organization` 的 Metadata 生成要求 |
| Sliding Window / Recursive / Semantic 配置模型 | 各策略参数、缺省值、取值范围 | 部分冲突：参数改在 `pipeline.levels[].params` 声明；取值约束不变 | 修改（只改载体，不改参数语义） |
| 组织配置模型 | Flat 单策略、Hierarchical `levels` | 直接冲突：统一为 `pipeline.levels` | 删除，由 `policy-engine` 承接 |
| 配置校验快速失败 | 构造期报错、点名 `ConfigError` | 部分冲突：校验时机改为 Policy 校验（`validate`/`compile`/`execute` 切块前） | 修改 |
| 序列化稳定性 | 自研 JSON 往返、四组边界、正则可判别 | 部分冲突：改为 `model_dump()`/`model_dump_json()`；四组边界不再存在；执行追溯字段每次不同 | 修改 |

### 2.2 `chunk-organization`

| Requirement | 现有契约摘要 | 与新设计的关系 | 处理 |
|---|---|---|---|
| Flat 组织 | 单策略、不写组织字段 | 直接冲突：一层 `pipeline.levels` 即平铺，且写组织字段 | 删除，以"单层 Pipeline"替代 |
| Hierarchical 多层执行 | N 层、每父块独立下切、禁止合并 | 部分冲突：算法不变，载体改为 `pipeline.levels` | 重命名并修改 |
| 子块边界约束 | 子块不越父界；父层 overlap 允许重复覆盖 | 无冲突 | 保留 |
| 全局 Offset 换算 | 局部 Offset 加父块基址 | 无冲突 | 保留 |
| 组织元数据填充 | 组织层填 `parent_id`/`level`/`sequence`；支持按 `parent_id` 查子块 | 部分冲突：单层也必须填写；关系只通过扁平列表中的 `parent_id` 表达 | 修改 |
| 层级边界与终止行为 | 空输入、空 levels、单层 Hierarchical、分支终止、不死循环 | 部分冲突：空 levels 改为 Policy 校验错误；"单层 Hierarchical"概念消失 | 修改 |
| 元数据组装 | 四组组装、Custom 继承、层级附加元数据 | 直接冲突 | 删除，以 Metadata 生成要求替代 |

### 2.3 `chunking-api`

| Requirement | 现有契约摘要 | 与新设计的关系 | 处理 |
|---|---|---|---|
| 统一公共入口 | 单一入口完成 Flat/Hierarchical、注册、Provider、序列化 | 部分冲突：入口改为 `Policy` + `ChunkEngine.validate/compile/execute` | 修改 |
| 执行入口 | `organization=flat` 等配置一次性执行 | 直接冲突：改为 `execute(text, policy, context=None, provider=None)` | 修改 |
| 扩展入口 | 注册自定义 Chunker；引擎级注入 Provider | 部分冲突：Provider 改为每次执行注入 | 修改 |
| 结果视图 | 平铺集合按 `start_offset` 排序；Tree View | 直接冲突：设计把 `to_tree()` 列为可选便利方法（§4.4），用户确认从契约中移除 | 删除；排序要求迁入 `chunk-model` 的 ChunkResult 要求 |
| 序列化入口 | 配置与结果往返、Tree 可重建 | 部分冲突 | 修改 |

### 2.4 `chunking-strategies`

| Requirement | 处理 | 理由 |
|---|---|---|
| Sliding Window 参数与校验、窗口推进与边界、Recursive 分隔符优先级、Recursive 片段合并、分隔符保留与归属、Recursive 兜底与终止性、Recursive 必要 Overlap、Recursive Strategy Metadata、Semantic 边界判定与兜底 | 保留 | 算法行为与新设计无冲突，设计未改算法 |
| Semantic Provider 注入协议 | 修改 | 部分冲突：Provider 经 `execute(provider=...)` 注入，不写入 Policy、不进入 Execution IR |
| 结果顺序与元数据归属 | 修改 | 部分冲突：策略输出 ChunkSpan，不负责 `chunk_id` 与业务 Metadata |

### 2.5 `strategy-registry`

| Requirement | 处理 | 理由 |
|---|---|---|
| 策略协议 | 修改 | 部分冲突：输出改为 ChunkSpan；`metadata_keys` 原用于 Custom 冲突检测，该机制已删除；新增参数 Schema 声明 |
| 内置策略注册 | 保留 | 名称沿用 `sliding_window`/`recursive`/`semantic`（用户确认；设计 §7 示例中的 `sliding` 记为文档不一致） |
| 自定义 Chunker 注册 | 修改 | 部分冲突：注册条件从 `metadata_keys` 改为参数 Schema |
| 未注册策略错误 | 保留 | 无冲突；Policy 语义校验另在 `policy-engine` 规定 |
| 名称冲突行为 | 保留 | 无冲突 |
| Registry 职责边界 | 修改 | 部分冲突：补充不负责 YAML 解析与 Metadata 生成，允许提供参数 Schema |

### 2.6 `package-distribution`

| Requirement | 处理 | 理由 |
|---|---|---|
| 可安装性 | 修改 | 部分冲突：设计 §4 要求 Pydantic V2，YAML Policy 需要 YAML 解析器，核心依赖不再为空 |
| 构建产物、可重复 Benchmark、CI 流水线、发布边界 | 保留 | 与架构无关 |
| 可选依赖边界 | 修改 | 部分冲突：措辞引用 Flat/Hierarchical |
| 文档可用性 | 修改 | 部分冲突：配置与组织文档需改为 Policy DSL 与 `pipeline.levels` |
| 示例可运行 | 修改 | 部分冲突：6 个示例基于旧 API；新增 `examples/policies/` |

## 3. 新增 Capability 评估

| 候选 | 结论 | 理由 |
|---|---|---|
| `policy-engine` | 新增 | Policy DSL、加载、结构与语义校验、Metadata DSL 是一组独立的用户可见契约，现有 Spec 无法承载 |
| `policy-compiler` | 新增，与 `policy-engine` 分开 | 职责边界不同：前者回答"Policy 是否合法"，后者回答"合法 Policy 编译成什么"（Execution IR、Policy Hash、编译不执行切块）；现有 Spec 粒度为每个能力一份，合并会让一份 Spec 同时承担 DSL 和 IR 两类契约 |
| `chunk-runtime` | 不新增 | Runtime 的组织行为由 `chunk-organization` 承载，Metadata 生成并入同一 Spec（旧版"元数据组装"也在此），公共执行行为由 `chunking-api` 承载，未出现职责过载 |

## 4. 与历史 Change 的关系

- `add-core-models-and-strategies`：确立三种算法与 Registry。本次保留其全部算法 Requirement，只改输出契约（ChunkSpan）与参数载体。
- `add-organization-and-api`：确立 Flat/Hierarchical、四组元数据、Custom 继承、`engine.chunk(config)`、Tree View。本次替换其组织表达、元数据模型与公共 API，保留逐父块下切、子块不越界、全局 Offset 换算与终止行为。
- `add-packaging-and-release`：确立打包、文档、示例、CI。本次只修改依赖、文档与示例三条。
- Archive 只读，未修改。

## 5. 用户已确认的决定（2026-11-26）

1. 正式 Spec 更新方式：创建 Change 后执行 `openspec sync`，把 delta 合并进 `openspec/specs/`；Change 保持活动，tasks 留给后续代码重构。
2. 旧 API（`engine.chunk(text, config)`、`FlatConfig`/`HierarchicalConfig`、`set_provider`、Custom 元数据参数）直接替换，不保留兼容层，标为 BREAKING。
3. 内置策略名沿用 `sliding_window`。
4. Tree View 从契约中移除，父子关系只通过 `parent_id` 表达。

### 5.1 第二轮决定（2026-11-26，迁移计划复查后）

5. `include.strategy`/`include.organization` 采用重构提示词（`docs/refactor/chunkweave_refactor_agent_prompt.md` §4.4、§7.7）的语义：控制策略信息与组织信息是否复制进业务 `metadata`；Chunk 属性始终保留。
6. Policy 业务字段名与系统字段名或保留键同名时，校验拒绝。
7. 自定义 Chunker 在注册时声明参数 Schema：`register(name, factory, params_model=..., replace=False)`。
8. 更新重构提示词，以 OpenSpec 为规范依据。
9. Open Questions 按建议关闭：Q1 两种访问方式都支持；Q4 保持 `chunk_size` 必填；Q6 层名经 `include.organization` 进入 `metadata`；Q8 留给后续 Change；Q9 确认 `MAJOR.MINOR.PATCH`；Q12 确认严格拒绝。

## 6. 设计文档内部的歧义与矛盾

以下问题在 design.md 的 Open Questions 中逐条记录，写明 Spec 当前采取的处理方式。

| # | 问题 | 位置 | Spec 当前处理 |
|---|---|---|---|
| Q1 | `Policy` 模型的身份信息在 `policy.policy.id`，但 §5 示例访问 `policy.id`、`policy.version` | §5 | Policy 对象提供 `id`、`name`、`version` 直接访问 |
| Q2 | §7 `Chunker.chunk()` 返回 `list[Chunk]`，同节又建议返回 `ChunkSpan` | §7 | 按迁移提示词采用 ChunkSpan |
| Q3 | §7 示例注册名 `sliding`，现有为 `sliding_window` | §7 | 沿用 `sliding_window`（用户确认） |
| Q4 | §3.3 `semantic` 层只给 `threshold`，现有 Spec 要求 `semantic` 必填 `chunk_size` | §3.3 | 保留 `chunk_size` 必填；该示例按现有契约会校验失败 |
| Q5 | `include.organization` 关闭后应隐藏什么未定义：系统字段 `parent_id`/`level`/`sequence` 不得丢失（§3.4），而 Chunk 模型中没有其他组织信息 | §3.4 | 只规定系统字段始终保留；`include.organization` 的可观察效果待定 |
| Q6 | 层级 `name` 是否出现在 Chunk 上未定义（Chunk 模型无对应字段） | §3、§4.1 | 不规定 |
| Q7 | `ChunkResult.total` 在模型草图中是 `@property`（不会进入 `model_dump()`），但 §8.3 HTTP JSON 含 `total` | §4.2、§8.3 | `total` 出现在序列化结果中且等于 `len(chunks)` |
| Q8 | Semantic 依赖外部模型时"应记录模型标识、版本和关键参数"，Provider 协议未定义如何提供这些信息 | §11.2 | 不规定，留待后续 Change |
| Q9 | "Policy 版本格式有效"未给出格式 | §5 | 暂定 `MAJOR.MINOR.PATCH` 三段数字，需用户确认 |
| Q10 | §6 `execute()` 签名不含 Provider 参数；迁移提示词为 `execute(text, policy, context=None, provider=None)`；旧 Spec 要求 Provider 可注入 | §6 | 采用 `provider=None` 关键字参数 |
| Q11 | §1.1 称 "Execution Planner"、§13 称 `ExecutionPlan`、§9 称 Execution IR | §1.1、§9、§13 | 术语统一为 Execution IR，公共类型名 `ExecutionPlan` |
| Q12 | 未知字段（Policy 顶层、level、`params`、Metadata 字段配置中的未知键）如何处理未定义；现有代码静默忽略未知参数 | §3、§5 | 拒绝并报校验错误（延续"配置校验快速失败"原则），属行为变化，需用户确认 |
