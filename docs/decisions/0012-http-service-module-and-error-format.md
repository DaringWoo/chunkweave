# ADR 0012: HTTP 服务模块位置与统一错误格式

**Status:** accepted · **Date:** 2026-11-27

## Context

设计文档把 HTTP 服务列为后续工作；实施时需要决定两件未在
Spec 中展开的事：服务代码放在哪里，以及所有 HTTP 错误如何统一
响应格式。

备选方案：仓库根目录建独立 `server/` 包（不进 wheel，部署方另行
拷贝）；沿用各框架自带的默认错误体（字段名不一致）。

## Decision

- 服务模块放在包内 `src/chunkweave/server.py`，随 wheel 分发，
  延续扁平模块布局；对外只导出 `create_app`。仓库根目录 `server/`
  不进 wheel，放弃。
- HTTP 框架为可选依赖 `chunkweave[server]`；核心安装不包含
  Web 框架，`import chunkweave.server` 在无依赖时抛带安装提示的
  ImportError。
- 所有错误响应统一为
  `{"error": {"type": <错误类型名>, "path": <字段路径或 null>, "reason": <原因>}}`；
  422（请求校验/Policy/Context/Provider）、413（文本超长）、
  404/405（`HTTPError`）、500（`InternalError`，reason 固定为
  `internal server error`，不泄露异常细节）都走同一格式。
- 切块是同步 CPU 计算，路由用普通 `def` 由线程池执行；
  Provider 线程安全由部署方保证并写入文档。

## Consequences

- `pip install chunkweave[server]` 即可用 `create_app` 构建应用，
  无需额外源码。
- 客户端只需解析一种错误形状；500 响应不携带内部信息。
- 单一职责：服务只做适配，执行逻辑完全复用 `ChunkEngine.execute`。
