## Purpose

为 HTTP 调用方提供与 Python SDK 一致的分块执行能力：`POST /api/v1/chunks` 接受声明式 Policy 并返回 ChunkResult，复用同一执行路径。

## ADDED Requirements

### Requirement: 分块接口

服务 MUST 提供 `POST /api/v1/chunks`，接受 JSON 请求体 `{text, policy, context}`：`text` 为必填字符串；`policy` 为必填 JSON 对象（Policy 的映射形式）；`context` 为可选 JSON 对象或 `null`。成功时返回 200，响应体含 `chunks`、`policy_id`、`policy_version`、`policy_hash`、`execution_id`、`engine_version`、`execution_time_ms`、`total`；每个 chunk 的字段与 Python `Chunk` 的序列化形式一致。

#### Scenario: 单层 Policy 成功

- **WHEN** 发送含合法单层 Policy 的请求
- **THEN** 返回 200，响应含上述全部字段，且 `total == len(chunks)`

#### Scenario: 响应字段齐备

- **WHEN** 任一成功响应
- **THEN** 每个 chunk 均含 `chunk_id`、`content`、`parent_id`、`level`、`sequence`、`start_offset`、`end_offset`、`strategy`、`strategy_metadata`、`metadata`

### Requirement: 与 Python SDK 结果等价

对相同的 `text`、`policy`、`context`，HTTP 响应 MUST 等于 SDK `execute()` 结果的 JSON 序列化（`execution_id`、`execution_time_ms` 除外）；服务 MUST 复用同一执行路径，不另设切块逻辑。

#### Scenario: 单层结果等价

- **WHEN** 用同一单层 Policy 分别经 HTTP 与 SDK 执行
- **THEN** 两端 chunks 内容、Offset、策略与业务元数据逐项相等

#### Scenario: 多层与元数据来源等价

- **WHEN** 用含 `metadata.fields`（`value` 与 `source`）的多层 Policy 分别经 HTTP 与 SDK 执行
- **THEN** 父子关系、`level`/`sequence` 与 `metadata` 逐项相等

### Requirement: 请求体校验

请求体缺少 `text` 或 `policy`，或 `text` 不是字符串、`policy` 不是 JSON 对象、`context` 既不是 JSON 对象也不是 `null`，或出现未知顶层字段（包括 `policy_ref`，本版本不支持）时，服务 MUST 返回 422 及统一错误格式，`path` 指向出错的请求字段。

#### Scenario: 缺少必填字段

- **WHEN** 请求体缺 `text` 或 `policy`
- **THEN** 返回 422，`error.path` 为对应字段名

#### Scenario: 未知顶层字段被拒

- **WHEN** 请求体含 `policy_ref` 或其他未声明字段
- **THEN** 返回 422，`error.path` 指向该字段

### Requirement: 统一错误响应格式

所有错误响应体 MUST 为 `{"error": {"type": <错误类型名>, "path": <字段路径或 null>, "reason": <原因>}}`；`type` 取错误类型名，`path` 指向出错的字段位置，`reason` 给出可读原因。

#### Scenario: 错误体结构统一

- **WHEN** 任一路径返回错误响应
- **THEN** 响应体均为 `error.type`/`error.path`/`error.reason` 三键结构

### Requirement: Policy 与 Context 错误映射

Policy 结构或语义校验失败（含未注册策略）MUST 返回 422，`type` 为 `PolicyValidationError` 或 `UnregisteredStrategyError`，`path` 为 Policy 内的字段路径（与 SDK 一致）。Context 路径缺失或值不可序列化 MUST 返回 422，`type` 为 `ContextResolutionError`，`path` 为 Context 路径，`reason` 含字段名。

#### Scenario: Policy 校验失败映射

- **WHEN** `policy` 中 `pipeline.levels[0].strategy` 引用未注册策略
- **THEN** 返回 422，`type` 为 `UnregisteredStrategyError`，`path` 为 `pipeline.levels[0].strategy`

#### Scenario: Context 缺失映射

- **WHEN** `metadata.fields` 的 `source` 路径在 `context` 中缺失
- **THEN** 返回 422，`type` 为 `ContextResolutionError`，`path` 为对应 `context.*` 路径

### Requirement: 服务端注入 Provider 与自定义策略

请求 MUST NOT 携带 Provider 或可执行内容；部署方经 `create_app(engine=None, provider=None, max_text_length=None)` 注入已注册自定义 Chunker 的引擎与 Semantic Provider。引用 `requires_provider` 策略而未配置 Provider 时返回 422。

#### Scenario: 自定义 Chunker 经 HTTP 引用

- **WHEN** 部署方注入注册了自定义策略的引擎，请求引用该策略
- **THEN** 返回 200，切块按自定义策略产出

#### Scenario: 已配置 Provider 执行 semantic

- **WHEN** `create_app` 配置了 Provider 且 Policy 含 semantic 层
- **THEN** 返回 200

#### Scenario: 未配置 Provider

- **WHEN** `create_app` 未配置 Provider 且 Policy 含 `requires_provider` 层
- **THEN** 返回 422，`type` 为 `ProviderMissingError`，`reason` 说明服务端未配置 Provider

### Requirement: 文本长度上限

配置了 `max_text_length` 时，`text` 的 Unicode 码点数超过上限 MUST 返回 413，`type` 为 `TextTooLong`，在任何切块之前拒绝；未配置时不限制。

#### Scenario: 超限拒绝

- **WHEN** `max_text_length` 已配置且 `text` 码点数超限
- **THEN** 返回 413，`type` 为 `TextTooLong`，未执行切块

#### Scenario: 未配置不限制

- **WHEN** 未配置 `max_text_length`
- **THEN** 任意长度的 `text` 进入正常校验与执行流程

### Requirement: 内部错误不泄露细节

未预期的异常（包括 Provider 抛出的异常）MUST 返回 500，`type` 为 `InternalError`，`path` 为 `null`，`reason` 为固定的通用文本，MUST NOT 包含异常消息或堆栈；服务端 MUST 记录该异常。

#### Scenario: Provider 异常屏蔽

- **WHEN** 部署的 Provider 在执行中抛出异常
- **THEN** 返回 500，`reason` 不含异常文本，服务端日志记录异常详情
