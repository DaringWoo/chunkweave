"""HTTP service: POST /api/v1/chunks over TestClient."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from chunkweave import ChunkEngine, ChunkSpan, Policy
from chunkweave.server import create_app

TEXT = "苹果富含维生素。香蕉也很好吃。微积分研究变化率。导数描述瞬时速度。"


def policy_dict(
    levels: list[dict[str, Any]],
    *,
    fields: dict[str, Any] | None = None,
    include: dict[str, Any] | None = None,
    policy_id: str = "http-test",
    version: str = "1.0.0",
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "api_version": "chunkweave/v1",
        "policy": {"id": policy_id, "name": "http", "version": version},
        "pipeline": {"levels": levels},
    }
    metadata: dict[str, Any] = {}
    if fields is not None:
        metadata["fields"] = fields
    if include is not None:
        metadata["include"] = include
    if metadata:
        data["metadata"] = metadata
    return data


def post(client: TestClient, body: dict[str, Any]):
    return client.post("/api/v1/chunks", json=body)


def single_level_body() -> dict[str, Any]:
    return {
        "text": TEXT,
        "policy": policy_dict(
            [{"name": "l0", "strategy": "recursive", "params": {"chunk_size": 40}}]
        ),
    }


def client_for(**kwargs) -> TestClient:
    return TestClient(create_app(**kwargs))


def test_single_level_success_and_fields():
    r = post(client_for(), single_level_body())
    assert r.status_code == 200
    body = r.json()
    for key in (
        "chunks", "policy_id", "policy_version", "policy_hash",
        "execution_id", "engine_version", "execution_time_ms", "total",
    ):
        assert key in body, key
    assert body["total"] == len(body["chunks"])
    for c in body["chunks"]:
        for key in (
            "chunk_id", "content", "parent_id", "level", "sequence",
            "start_offset", "end_offset", "strategy",
            "strategy_metadata", "metadata",
        ):
            assert key in c, key
    assert all(c["content"] == TEXT[c["start_offset"]:c["end_offset"]]
               for c in body["chunks"])


def _dump(result) -> dict[str, Any]:
    d = result.model_dump(mode="json")
    d.pop("execution_id")
    d.pop("execution_time_ms")
    return d


def test_http_equals_sdk_single_level():
    body = single_level_body()
    r = post(client_for(), body)
    sdk = _dump(
        ChunkEngine().execute(
            body["text"], Policy.from_dict(body["policy"])
        )
    )
    http = r.json()
    http.pop("execution_id")
    http.pop("execution_time_ms")
    assert http == sdk


def test_http_equals_sdk_multi_level_with_fields():
    p = policy_dict(
        [
            {"name": "segment", "strategy": "recursive",
             "params": {"chunk_size": 40, "separators": ["。"]}},
            {"name": "detail", "strategy": "sliding_window",
             "params": {"chunk_size": 15}},
        ],
        fields={
            "doc_kind": {"value": "demo"},
            "tenant": {"source": "context.request.tenant"},
        },
    )
    ctx = {"request": {"tenant": "acme"}}
    r = post(client_for(), {"text": TEXT, "policy": p, "context": ctx})
    assert r.status_code == 200
    sdk = _dump(
        ChunkEngine().execute(TEXT, Policy.from_dict(p), context=ctx)
    )
    http = r.json()
    http.pop("execution_id")
    http.pop("execution_time_ms")
    assert http == sdk


@pytest.mark.parametrize("body,path", [
    ({"policy": {}}, "text"),
    ({"text": TEXT}, "policy"),
    ({"text": 123, "policy": {}}, "text"),
    ({"text": TEXT, "policy": "not-a-dict"}, "policy"),
    ({"text": TEXT, "policy": {}, "context": 5}, "context"),
])
def test_request_validation_errors(body, path):
    r = post(client_for(), body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "RequestValidationError"
    assert err["path"] == path
    assert set(err) == {"type", "path", "reason"}


@pytest.mark.parametrize("field", ["policy_ref", "bogus"])
def test_unknown_top_level_field(field):
    body = single_level_body()
    body[field] = "x"
    r = post(client_for(), body)
    assert r.status_code == 422
    assert r.json()["error"]["path"] == field


def test_error_body_uniform_shape():
    r = client_for().get("/api/v1/does-not-exist")
    assert r.status_code == 404
    err = r.json()["error"]
    assert set(err) == {"type", "path", "reason"}
    assert err["type"] == "HTTPError"
    assert err["path"] is None


def test_policy_validation_error_mapping():
    p = policy_dict(
        [{"name": "l0", "strategy": "no-such-strategy", "params": {}}]
    )
    r = post(client_for(), {"text": TEXT, "policy": p})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "UnregisteredStrategyError"
    assert err["path"] == "pipeline.levels[0].strategy"


def test_policy_params_error_mapping():
    p = policy_dict(
        [{"name": "l0", "strategy": "sliding_window",
          "params": {"chunk_size": 0}}]
    )
    r = post(client_for(), {"text": TEXT, "policy": p})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "PolicyValidationError"
    assert err["path"].startswith("pipeline.levels[0].params")


def test_context_resolution_error_mapping():
    p = policy_dict(
        [{"name": "l0", "strategy": "recursive", "params": {"chunk_size": 50}}],
        fields={"doc": {"source": "context.document_id"}},
    )
    r = post(client_for(), {"text": TEXT, "policy": p})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "ContextResolutionError"
    assert err["path"] == "context.document_id"
    assert "doc" in err["reason"]


class WordsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_words: StrictInt = Field(default=4, gt=0)


class WordChunker:
    def __init__(self, params: WordsParams) -> None:
        self.max_words = params.max_words

    def chunk(self, text: str) -> list[ChunkSpan]:
        return [
            ChunkSpan(content=text, start_offset=0, end_offset=len(text),
                      strategy_metadata={"word_count": len(text.split())})
        ]


def test_custom_chunker_over_http():
    engine = ChunkEngine()
    engine.register("words", lambda p, _prov: WordChunker(p),
                    params_model=WordsParams)
    client = client_for(engine=engine)
    p = policy_dict(
        [{"name": "l0", "strategy": "words", "params": {"max_words": 3}}]
    )
    r = post(client, {"text": "a b c", "policy": p})
    assert r.status_code == 200
    assert r.json()["chunks"][0]["strategy_metadata"]["word_count"] == 3


class DemoProvider:
    def score(self, left: str, right: str) -> float:
        return 0.9 if left[:1] == right[:1] else 0.1


def semantic_body() -> dict[str, Any]:
    return {
        "text": TEXT,
        "policy": policy_dict(
            [{"name": "l0", "strategy": "semantic",
              "params": {"threshold": 0.5, "chunk_size": 50}}]
        ),
    }


def test_semantic_with_configured_provider():
    r = post(client_for(provider=DemoProvider()), semantic_body())
    assert r.status_code == 200
    assert r.json()["chunks"]


def test_semantic_without_provider_422():
    r = post(client_for(), semantic_body())
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "ProviderMissingError"
    assert err["path"] is None
    assert err["reason"] == (
        "strategy 'semantic' requires a similarity provider, "
        "but none is configured on this server"
    )


def test_max_text_length_413_before_chunking():
    client = client_for(max_text_length=10)
    body = single_level_body()
    # even an invalid policy would 422; length check must fire first
    body["policy"]["pipeline"]["levels"][0]["strategy"] = "no-such-strategy"
    r = post(client, body)
    assert r.status_code == 413
    err = r.json()["error"]
    assert err["type"] == "TextTooLong"
    assert err["path"] == "text"
    assert "10" in err["reason"] and str(len(body["text"])) in err["reason"]


def test_no_limit_by_default():
    r = post(client_for(), {"text": TEXT * 100, "policy": single_level_body()["policy"]})
    assert r.status_code == 200


@pytest.mark.parametrize("bad", [0, -1, "100", True, 1.5])
def test_max_text_length_invalid(bad):
    with pytest.raises(ValueError):
        create_app(max_text_length=bad)


def test_internal_error_hides_details(caplog):
    class BoomProvider:
        def score(self, left: str, right: str) -> float:
            raise RuntimeError("SECRET-sentence-marker")

    client = TestClient(
        create_app(provider=BoomProvider()), raise_server_exceptions=False
    )
    with caplog.at_level(logging.ERROR, logger="chunkweave.server"):
        r = post(client, semantic_body())
    assert r.status_code == 500
    err = r.json()["error"]
    assert err["type"] == "InternalError"
    assert err["path"] is None
    assert err["reason"] == "internal server error"
    assert "SECRET-sentence-marker" not in r.text
    assert any("SECRET-sentence-marker" in rec.getMessage()
               for rec in caplog.records)
