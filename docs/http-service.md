# HTTP 服务

chunkweave 提供可选的 HTTP 服务，对外暴露 `POST /api/v1/chunks`，执行
路径与 Python SDK 完全相同（Policy → Compiler → IR → Runtime），
响应与 `execute()` 的序列化结果一致。

## 安装与启动

HTTP 服务是可选依赖，核心安装不包含 Web 框架：

```bash
pip install 'chunkweave[server]'
```

启动（工厂模式，不能注入 Provider 或自定义引擎时使用）：

```bash
uvicorn --factory chunkweave.server:create_app --port 8000
```

需要 Provider（semantic 层）或自定义 Chunker 时，自写入口注入：

```python
# serve.py
from chunkweave import ChunkEngine
from chunkweave.server import create_app

class MyProvider:
    def score(self, left: str, right: str) -> float: ...

engine = ChunkEngine()
# engine.register(...)  # 需要时注册自定义策略
app = create_app(engine=engine, provider=MyProvider())
```

```bash
uvicorn serve:app --port 8000
```

## `create_app` 参数

```python
create_app(
    engine: ChunkEngine | None = None,
    provider: SimilarityProvider | None = None,
    max_text_length: int | None = None,
) -> FastAPI
```

| 参数 | 说明 |
| --- | --- |
| `engine` | 预先配置的引擎（可含自定义 Chunker 注册）；`None` 时内部建默认引擎 |
| `provider` | 注入到每次 `execute()` 调用的 Similarity Provider；部署方保证其**线程安全**（请求经线程池并发执行） |
| `max_text_length` | `text` 的 Unicode 码点数上限；`None`（缺省）不限制。必须是正整数或 `None`，否则 `create_app` 抛 `ValueError` |

## 接口

### `POST /api/v1/chunks`

请求体（JSON，不允许其他顶层字段，包括 `policy_ref`）：

```json
{
  "text": "苹果富含维生素。香蕉也很好吃。",
  "policy": {
    "api_version": "chunkweave/v1",
    "policy": {"id": "demo", "name": "示例", "version": "1.0.0"},
    "pipeline": {
      "levels": [
        {"name": "l0", "strategy": "recursive", "params": {"chunk_size": 40}}
      ]
    },
    "metadata": {
      "fields": {
        "doc_kind": {"value": "demo"},
        "tenant": {"source": "context.request.tenant"}
      }
    }
  },
  "context": {"request": {"tenant": "acme"}}
}
```

- `text`：必填，字符串。
- `policy`：必填，JSON 对象——Policy 的映射形式（与 YAML 解析后的结构相同）。
- `context`：可选，JSON 对象或 `null`。
- Provider MUST NOT 出现在请求中；服务端注入由 `create_app` 完成。

成功响应（200）与 `ChunkResult.model_dump(mode="json")` 一致：
`chunks`、`policy_id`、`policy_version`、`policy_hash`、`execution_id`、
`engine_version`、`execution_time_ms`、`total`。

### curl 示例

```bash
curl -s -X POST http://localhost:8000/api/v1/chunks \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "苹果富含维生素。香蕉也很好吃。",
    "policy": {
      "api_version": "chunkweave/v1",
      "policy": {"id": "demo", "name": "示例", "version": "1.0.0"},
      "pipeline": {"levels": [
        {"name": "l0", "strategy": "recursive", "params": {"chunk_size": 40}}
      ]}
    }
  }'
```

## 错误响应

所有错误响应统一为：

```json
{"error": {"type": "<错误类型名>", "path": "<字段路径或 null>", "reason": "<原因>"}}
```

| 情形 | 状态码 | `type` | `path` |
| --- | --- | --- | --- |
| 缺 `text`/`policy`、类型错误、未知顶层字段（含 `policy_ref`） | 422 | `RequestValidationError` | 出错字段名 |
| Policy 结构/语义校验失败 | 422 | `PolicyValidationError` | Policy 内字段路径（与 SDK 一致） |
| 未注册策略 | 422 | `UnregisteredStrategyError` | `pipeline.levels[i].strategy` |
| Context 路径缺失/值不可序列化 | 422 | `ContextResolutionError` | `context.*` 路径 |
| 策略需要 Provider 而服务端未配置 | 422 | `ProviderMissingError` | `null` |
| `text` 超过 `max_text_length` | 413 | `TextTooLong` | `text` |
| 未匹配路径/方法等框架错误 | 404/405 等 | `HTTPError` | `null` |
| 未预期异常（含 Provider 抛出） | 500 | `InternalError` | `null`，`reason` 为 `internal server error` |

500 响应不携带异常消息或堆栈；服务端在 `chunkweave.server` logger 上
记录异常详情。
