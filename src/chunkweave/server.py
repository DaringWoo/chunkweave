"""HTTP service: ``POST /api/v1/chunks`` over the same execution path as the SDK.

Optional module — requires the ``server`` extra::

    pip install 'chunkweave[server]'

Run it with ``uvicorn --factory chunkweave.server:create_app``, or write a
small entry point that calls :func:`create_app` with a configured engine
(custom chunkers registered) and provider (for ``semantic`` levels).
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException
except ImportError as e:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "chunkweave.server requires the 'server' extra; "
        "install it with: pip install 'chunkweave[server]'"
    ) from e

from pydantic import BaseModel, ConfigDict, StrictStr

from .engine import ChunkEngine
from .models import (
    ChunkResult,
    ContextResolutionError,
    PolicyLoadError,
    PolicyValidationError,
    ProviderMissingError,
)
from .policy import Policy, format_loc
from .strategies import SimilarityProvider

logger = logging.getLogger("chunkweave.server")


class ChunkRequest(BaseModel):
    """Request body for ``POST /api/v1/chunks``.

    ``policy`` is the Policy in mapping form (the same structure YAML
    parses into); a request can never carry a provider.
    """

    model_config = ConfigDict(extra="forbid")

    text: StrictStr
    policy: dict[str, Any]
    context: dict[str, Any] | None = None


class _TextTooLong(Exception):
    """Internal signal: request text exceeded ``max_text_length``."""

    def __init__(self, limit: int, actual: int) -> None:
        self.limit = limit
        self.actual = actual


def _error_response(
    status_code: int, error_type: str, path: str | None, reason: str
) -> JSONResponse:
    """Build the uniform ``{"error": {type, path, reason}}`` body."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "path": path, "reason": reason}},
    )


def create_app(
    engine: ChunkEngine | None = None,
    provider: SimilarityProvider | None = None,
    max_text_length: int | None = None,
) -> FastAPI:
    """Create the HTTP application.

    ``engine`` may be pre-configured (e.g. with custom chunkers
    registered); a default ``ChunkEngine`` is used otherwise. ``provider``
    is injected into every ``execute()`` call — it is the deployment's
    responsibility that it is thread-safe. ``max_text_length`` caps the
    request ``text`` length in Unicode code points; ``None`` means no
    limit and is the default.
    """
    if max_text_length is not None and (
        not isinstance(max_text_length, int)
        or isinstance(max_text_length, bool)
        or max_text_length <= 0
    ):
        raise ValueError(
            "max_text_length must be a positive int or None, "
            f"got {max_text_length!r}"
        )
    if engine is None:
        engine = ChunkEngine()
    app = FastAPI(title="chunkweave")

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0]
        loc = tuple(first.get("loc", ()))
        if loc[:1] == ("body",):
            loc = loc[1:]
        return _error_response(
            422,
            "RequestValidationError",
            format_loc(loc) if loc else None,
            str(first.get("msg", "invalid request body")),
        )

    @app.exception_handler(PolicyLoadError)
    async def _on_policy_load_error(
        _request: Request, exc: PolicyLoadError
    ) -> JSONResponse:
        return _error_response(422, type(exc).__name__, None, str(exc))

    @app.exception_handler(PolicyValidationError)
    async def _on_policy_validation_error(
        _request: Request, exc: PolicyValidationError
    ) -> JSONResponse:
        return _error_response(422, type(exc).__name__, exc.path or None, exc.reason)

    @app.exception_handler(ContextResolutionError)
    async def _on_context_error(
        _request: Request, exc: ContextResolutionError
    ) -> JSONResponse:
        return _error_response(
            422,
            type(exc).__name__,
            exc.path,
            f"cannot resolve metadata field {exc.field!r}: {exc.reason}",
        )

    @app.exception_handler(ProviderMissingError)
    async def _on_provider_missing(
        _request: Request, exc: ProviderMissingError
    ) -> JSONResponse:
        return _error_response(
            422,
            type(exc).__name__,
            None,
            f"strategy '{exc.strategy}' requires a similarity provider, "
            "but none is configured on this server",
        )

    @app.exception_handler(_TextTooLong)
    async def _on_text_too_long(
        _request: Request, exc: _TextTooLong
    ) -> JSONResponse:
        return _error_response(
            413,
            "TextTooLong",
            "text",
            f"text length {exc.actual} code points exceeds the configured "
            f"limit of {exc.limit}",
        )

    @app.exception_handler(HTTPException)
    async def _on_http_exception(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        reason = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_response(exc.status_code, "HTTPError", None, reason)

    @app.exception_handler(Exception)
    async def _on_unexpected(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("unhandled error during chunk request: %s", exc)
        return _error_response(500, "InternalError", None, "internal server error")

    @app.post("/api/v1/chunks")
    def post_chunks(request: ChunkRequest) -> ChunkResult:
        if max_text_length is not None and len(request.text) > max_text_length:
            raise _TextTooLong(max_text_length, len(request.text))
        policy = Policy.from_dict(request.policy)
        return engine.execute(
            request.text, policy, context=request.context, provider=provider
        )

    return app


__all__ = ["create_app"]
