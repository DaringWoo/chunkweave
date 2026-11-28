"""HTTP 服务：POST /api/v1/chunks，与 SDK 完全同一条执行路径。

演示要点：
- 用 FastAPI 的 TestClient 离线演示，无需真的起服务；
- 生产环境的启动方式是 uvicorn --factory chunkweave.server:create_app；
- 响应就是序列化后的 ChunkResult，与 SDK 输出逐字段一致
  （仅 execution_id/execution_time_ms 因次而异）；
- 所有错误统一为 {"error": {type, path, reason}} 格式。

需要先装服务端依赖：pip install 'chunkweave[server]'
"""

import sys

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

try:
    from fastapi.testclient import TestClient

    from chunkweave.server import create_app
except ImportError:
    # 核心安装不含 fastapi；server.py 的导入保护会给出同样的安装提示。
    print("this example requires the server extra: pip install 'chunkweave[server]'")
    raise SystemExit(0) from None

TEXT = "苹果富含维生素。香蕉也很好吃。微积分研究变化率。"

# HTTP 请求里的 policy 就是 YAML 解析后的同款字典结构——
# 服务端会用 Policy.from_dict() 走与 from_yaml 相同的校验路径。
POLICY = {
    "api_version": "chunkweave/v1",
    "policy": {"id": "http-demo", "name": "HTTP 演示", "version": "1.0.0"},
    "pipeline": {
        "levels": [
            {"name": "sentence", "strategy": "recursive", "params": {"chunk_size": 20}}
        ]
    },
}


def main() -> None:
    # create_app() 可注入 engine（带自定义策略）、provider（semantic 用）、
    # max_text_length（文本上限，默认不限）。这里全部用默认。
    client = TestClient(create_app())

    # 1) 正常请求：context 可省略或为 null。
    resp = client.post(
        "/api/v1/chunks", json={"text": TEXT, "policy": POLICY, "context": None}
    )
    print(f"POST /api/v1/chunks -> {resp.status_code}")
    body = resp.json()
    print(f"total={body['total']} policy_hash={body['policy_hash'][:24]}…")
    for c in body["chunks"]:
        print(f"  {c['chunk_id']} [{c['start_offset']},{c['end_offset']}) {c['content']!r}")

    # 2) 等价性验证：HTTP 响应与 SDK 的 model_dump() 去掉两个执行次数字段后
    #    应当完全相等——这正是"HTTP 只是薄包装"的含义。
    sdk = ChunkEngine().execute(TEXT, Policy.from_dict(POLICY)).model_dump(mode="json")
    for key in ("execution_id", "execution_time_ms"):
        body.pop(key)
        sdk.pop(key)
    print(f"http response == sdk result: {body == sdk}")

    # 3) 错误格式统一：type 是错误类型名，path 指向出错字段，reason 可读。
    #    - policy_ref 是刻意不支持的字段（请求体 extra="forbid"）；
    #    - 结构残缺的 policy 会带出与 SDK 一致的校验路径。
    for label, payload in [
        ("unknown field", {"text": TEXT, "policy": POLICY, "policy_ref": "x"}),
        ("bad policy", {"text": TEXT, "policy": {"pipeline": {}}, "context": None}),
    ]:
        err = client.post("/api/v1/chunks", json=payload)
        print(f"{label}: {err.status_code} {err.json()['error']}")


if __name__ == "__main__":
    main()
