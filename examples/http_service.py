"""HTTP service: POST /api/v1/chunks through the same execution path.

Uses FastAPI's TestClient so the demo runs offline; in production you would
start it with ``uvicorn --factory chunkweave.server:create_app``. Requires
the server extra: pip install 'chunkweave[server]'.
"""

import sys

from chunkweave import ChunkEngine, Policy

sys.stdout.reconfigure(encoding="utf-8")

try:
    from fastapi.testclient import TestClient

    from chunkweave.server import create_app
except ImportError:
    print("this example requires the server extra: pip install 'chunkweave[server]'")
    raise SystemExit(0) from None

TEXT = "苹果富含维生素。香蕉也很好吃。微积分研究变化率。"

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
    client = TestClient(create_app())

    # 1) A normal request: the response is the serialized ChunkResult.
    resp = client.post(
        "/api/v1/chunks", json={"text": TEXT, "policy": POLICY, "context": None}
    )
    print(f"POST /api/v1/chunks -> {resp.status_code}")
    body = resp.json()
    print(f"total={body['total']} policy_hash={body['policy_hash'][:24]}…")
    for c in body["chunks"]:
        print(f"  {c['chunk_id']} [{c['start_offset']},{c['end_offset']}) {c['content']!r}")

    # 2) HTTP and SDK results are equivalent except execution identity fields.
    sdk = ChunkEngine().execute(TEXT, Policy.from_dict(POLICY)).model_dump(mode="json")
    for key in ("execution_id", "execution_time_ms"):
        body.pop(key)
        sdk.pop(key)
    print(f"http response == sdk result: {body == sdk}")

    # 3) Errors share one shape: {"error": {type, path, reason}}.
    for label, payload in [
        ("unknown field", {"text": TEXT, "policy": POLICY, "policy_ref": "x"}),
        ("bad policy", {"text": TEXT, "policy": {"pipeline": {}}, "context": None}),
    ]:
        err = client.post("/api/v1/chunks", json=payload)
        print(f"{label}: {err.status_code} {err.json()['error']}")


if __name__ == "__main__":
    main()
