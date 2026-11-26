# Proposal

## Why

设计文档（已归档 Change `refactor-to-policy-driven-engine` 的 design §8、§12 第 12 项）规划了 HTTP 服务：HTTP 调用方需要与 Python SDK 一致的执行能力，但当前只能通过 `ChunkEngine.execute` 在进程内调用。现在为独立部署提供 `POST /api/v1/chunks` 接口。

## What Changes

- 新增 `POST /api/v1/chunks`：JSON 请求 `{text, policy, context}`，返回与 SDK `execute()` 等价的 `ChunkResult` 序列化。
- 新增 `Policy.from_dict(data)`：从映射加载 Policy，供 HTTP 层复用同一套结构校验。
- 新增可选依赖 `server`：HTTP 服务经 `chunkweave[server]` 安装，核心安装不包含 HTTP 框架。
- 统一错误响应格式 `{"error": {"type", "path", "reason"}}`，SDK 校验/Context/Provider 错误映射为 422，内部异常映射为不泄露细节的 500。

## Capabilities

### New Capabilities

- `http-service`: HTTP 分块接口 `POST /api/v1/chunks` 的请求/响应契约、与 SDK 的结果等价性、统一错误格式、Provider 与自定义策略的服务端注入、文本长度上限与内部错误屏蔽。

### Modified Capabilities

- `policy-engine`: 新增「从映射加载」——`Policy.from_dict` 与 `from_yaml` 共用结构校验。
- `chunking-api`: 「统一公共入口」的 Policy 加载方式增加 `Policy.from_dict`。
- `package-distribution`: 「可选依赖边界」增加 `server` extras 的边界与导入提示；「文档可用性」交付清单增加 `docs/http-service.md`。

## Impact

- 新增模块 `src/chunkweave/server.py`（随 wheel 分发，扁平布局延续）。
- `pyproject.toml` 增加 `server` extras 与 dev 依赖；CI Install 步骤加装。
- `policy.py` 增加 `Policy.from_dict`，`from_yaml` 内部复用。
- 核心安装不变：未安装 `server` 时 `import chunkweave` 不受影响，`import chunkweave.server` 给出安装提示。
- 新增 `tests/test_server.py` 与 `docs/http-service.md`、ADR 0012；README 与 IMPLEMENTATION_REPORT 同步。

## Non-Goals

- `policy_ref`（按引用指定已发布 Policy）。
- 认证与鉴权。
- Policy 发布、版本管理与后台管理界面。
- 数据库或任何持久化。
- 流式响应。
- 异步 Provider 协议。
