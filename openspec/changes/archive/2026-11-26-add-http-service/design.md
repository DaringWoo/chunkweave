# Design

## Context

`POST /api/v1/chunks` 复用已交付的 `Policy → Compiler → IR → Runtime`
执行路径：HTTP 层只做请求解析、长度上限、`Policy.from_dict` 与
`engine.execute`，不实现任何切块逻辑。动机见 proposal.md。

## Goals / Non-Goals

**Goals:**

- HTTP 响应与 SDK `execute()` 序列化等价（`execution_id`、
  `execution_time_ms` 除外）。
- 统一错误格式 `{"error": {"type", "path", "reason"}}`，SDK 异常映射为
  422，内部异常屏蔽为 500。
- HTTP 框架为可选依赖，核心安装与 `import chunkweave` 不受影响。

**Non-Goals:**

- `policy_ref`、认证、Policy 管理后台、数据库、流式响应、异步
  Provider（见 proposal.md Non-Goals）。

## Decisions

### 模块位置与依赖

- **`src/chunkweave/server.py`**：服务模块进包内，随 wheel 分发并延续
  448d132 以来的扁平模块布局，不建 `server/` 子包。备选「仓库根目录
  `server/`」已放弃——不进 wheel，部署方无法 `pip install` 后启动。
- **extras**：`server = ["fastapi>=0.143", "uvicorn>=0.54"]`；`dev` 增加
  fastapi、uvicorn 与 `httpx>=0.28`（TestClient 需要），保证 HTTP 测试
  在开发与 CI 环境中都实际运行，不跳过。
- **导入保护**：`server.py` 顶部导入 fastapi 失败时抛出带安装提示的
  `ImportError`（提示 `chunkweave[server]`），满足可选依赖边界。

### 应用工厂与启动

- `create_app(engine: ChunkEngine | None = None, provider:
  SimilarityProvider | None = None, max_text_length: int | None = None)
  -> FastAPI`。`engine=None` 时内部建默认 `ChunkEngine`；`provider` 由
  部署方注入，供 `requires_provider` 层使用；`max_text_length` 缺省不
  限制。
- 启动：`uvicorn --factory chunkweave.server:create_app`，或由部署方
  自写入口以传入 Provider 与已注册自定义 Chunker 的引擎。
- 请求 MUST NOT 携带 Provider；`policy` 仅为 JSON 映射，经
  `Policy.from_dict` 校验，不可能携带可执行内容。

### 请求模型与路由

- `ChunkRequest`（`extra="forbid"`）：`text: StrictStr`、`policy:
  dict[str, Any]`、`context: dict[str, Any] | None = None`。未知顶层字段
  （含 `policy_ref`）由模型拒绝。
- 路由用普通 `def`（经线程池执行），因为切块是同步 CPU 计算；返回
  类型声明为 `ChunkResult`，`total` 计算字段自动进入响应体。
- 处理顺序：先 `max_text_length` 检查，再 `Policy.from_dict(policy)`，
  最后 `engine.execute(text, policy, context=..., provider=...)`。

### 异常处理（统一错误体）

统一错误体由辅助函数构造 `{error: {type, path, reason}}`：

| 来源异常 | 状态码 | type | path |
| --- | --- | --- | --- |
| `RequestValidationError` | 422 | `RequestValidationError` | loc 去掉开头的 `body` 后格式化 |
| `PolicyLoadError`/`PolicyValidationError`（含子类如 `UnregisteredStrategyError`） | 422 | 子类名 | 异常的 `.path`（与 SDK 一致） |
| `ContextResolutionError` | 422 | `ContextResolutionError` | Context 路径 |
| `ProviderMissingError` | 422 | `ProviderMissingError` | `null`，`reason` 说明服务端未配置 Provider |
| `TextTooLong`（长度上限，自定义判断非异常类亦可） | 413 | `TextTooLong` | `text` |
| Starlette `HTTPException`（未知路径 404、方法不允许 405 等框架错误） | 原状态码 | `HTTPError` | `null`，`reason` 取框架的 `detail` |
| 其他 `Exception`（含 Provider 抛出） | 500 | `InternalError` | `null`，固定通用文本 |

- 500 分支用 `logging.getLogger("chunkweave.server").exception(...)`
  记录异常详情，响应不携带异常消息或堆栈。
- `RequestValidationError` 覆盖缺字段、类型错误与未知顶层字段三种
  请求体校验失败。

### `Policy.from_dict`

放在 `policy.py`：`from_dict(data)` 对非映射抛 `PolicyLoadError`，对
映射走 `Policy.model_validate` 并把 `ValidationError` 转成
`PolicyValidationError`（沿用现有 `_format_loc` 字段路径格式化）。
`from_yaml` 改为在 `safe_load` 与根节点检查之后调用 `from_dict`，两者
共用同一套错误转换，不再各写一份。

### 线程安全

- 执行期间 Registry 只读（注册在部署期完成）；Chunker 在每次
  `execute` 内新建，无共享状态。
- Provider 由部署方保证线程安全，在 `docs/http-service.md` 中写明。

## Risks / Trade-offs

- [同步切块占用线程池] → 路由用 `def` 让 ASGI 框架放到线程池执行；大
  文本/高并发需部署方自行限流与调 worker，`max_text_length` 提供基本
  保护。
- [Provider 注入方式与并发] → Provider 为部署方对象，文档要求其线程
  安全；引擎不为并发安全兜底。
- [`TextTooLong` 新增公开错误名] → 仅 HTTP 层使用，不进 SDK 异常
  体系；type 字符串固定于错误映射表。
- [422 中暴露 Policy 字段路径] → 错误信息为契约的一部分（与 SDK
  path 一致），属有意设计；内部异常仍完全屏蔽。

## Migration Plan

纯新增能力，无迁移：核心安装行为不变；需要 HTTP 的部署方安装
`chunkweave[server]` 并以工厂方式启动。

## Open Questions

无。
