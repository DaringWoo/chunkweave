# Tasks

## 1. Policy.from_dict

- [x] 1.1 在 `policy.py` 实现 `Policy.from_dict(data)`：非映射抛 `PolicyLoadError`，映射走 `model_validate` 并复用现有 `ValidationError → PolicyValidationError`（含字段路径）转换；`from_yaml` 改为 `safe_load` + 根节点检查后调用 `from_dict`；验收：`tests/test_policy.py` 新增用例覆盖「合法映射」「未知字段带路径」「非映射被拒」，`from_yaml` 既有测试全部通过
- [x] 1.2 在 `__init__.py` 与文档层面确认 `from_dict` 可达（`Policy.from_dict` 公共方法，无需新增导出）；验收：`python -c "from chunkweave import Policy; Policy.from_dict({...})"` 可用

## 2. 依赖与 CI

- [x] 2.1 `pyproject.toml` 增加 `server = ["fastapi>=0.143", "uvicorn>=0.54"]` extras，`dev` 增加 fastapi、uvicorn、`httpx>=0.28`；验收：`pip install -e .[server]` 成功，`import chunkweave.server` 可用
- [x] 2.2 CI Install 步骤改为安装 `.[server]`（或等价 dev 依赖集），保证 HTTP 测试在 CI 实际运行不跳过；验收：CI 步骤含 server extras 安装

## 3. server.py

- [x] 3.1 实现 `src/chunkweave/server.py`：顶部 fastapi 导入保护（失败抛带 `chunkweave[server]` 提示的 `ImportError`）、`create_app(engine=None, provider=None, max_text_length=None)`、`ChunkRequest` 请求模型（`extra="forbid"`，`text: StrictStr`、`policy: dict`、`context: dict | None`）；验收：未安装 server extras 的环境中 `import chunkweave.server` 给出安装提示
- [x] 3.2 实现路由 `POST /api/v1/chunks`（普通 `def`，返回 `ChunkResult`）：先 `max_text_length` 检查（超限 413 `TextTooLong`），再 `Policy.from_dict`，再 `engine.execute(..., provider=...)`；验收：`test_server.py` 中成功路径返回 200 且 `total == len(chunks)`
- [x] 3.3 实现统一异常处理器与错误体辅助函数：`RequestValidationError`/`PolicyLoadError`/`PolicyValidationError`/`ContextResolutionError`/`ProviderMissingError` → 422，长度超限 → 413，Starlette `HTTPException`（404/405 等）→ 原状态码 `HTTPError`，其他 `Exception` → 500（`logging.getLogger("chunkweave.server")` 记录，通用文本）；验收：各错误路径的 `type`/`path`/`reason` 与 spec 一致

## 4. 测试

- [x] 4.1 新增 `tests/test_server.py`，用 TestClient 覆盖 `http-service` Spec 的每个 Scenario：单层成功与字段齐备、SDK 等价（单层、多层含 `value`/`source` 两例）、请求体校验（缺字段、类型错误、未知顶层字段含 `policy_ref`）、统一错误体结构、Policy 校验失败与 Context 错误映射、自定义 Chunker 与 Provider 注入（含未配置 Provider 的 422）、`max_text_length` 413、Provider 异常 → 500 且 `reason` 不含异常文本、未知路径 404 也是统一错误体；验收：`pytest tests/test_server.py` 全绿

## 5. 文档

- [x] 5.1 新增 `docs/http-service.md`：接口说明、请求与响应示例、错误表、`create_app` 参数、启动方式（`uvicorn --factory` 与自写入口注入 Provider）、Provider 线程安全要求；验收：文档内示例经实际运行验证
- [x] 5.2 README 增加 HTTP 服务小节（`chunkweave[server]` 安装与最小调用）；验收：README 代码块实际运行成功
- [x] 5.3 `IMPLEMENTATION_REPORT.md` 删去「HTTP Service 未实现」，补充 HTTP 测试数与验证结果；验收：报告数字与实际运行一致
- [x] 5.4 新增 ADR 0012（服务模块位置 `src/chunkweave/server.py` 与统一错误格式）；验收：ADR 格式与既有 ADR 一致

## 6. 门禁

- [x] 6.1 全量校验：`ruff check .`、`mypy src`、`pytest -q`、全部 `examples/*.py`、`python -m build` 与 `twine check`；验收：全部通过
- [x] 6.2 核心边界验证：干净 venv 只装核心包，`pip list` 无 fastapi，`import chunkweave` 正常，`import chunkweave.server` 给出安装提示；验收：三项实测通过
- [x] 6.3 服务实测：另一干净 venv 装 `.[server]`，`uvicorn --factory` 实际启动服务，POST 一个单层 Policy 请求拿到 200，随后停止服务并删除两个 venv；验收：拿到 200 响应
- [x] 6.4 `openspec validate --all --strict`；验收：全部通过

## Workflow follow-up

- 代码任务完成后经用户同意才归档本 Change；归档用 `openspec archive add-http-service`（delta 首次落地，正常应用 ADDED/MODIFIED 即可）。
