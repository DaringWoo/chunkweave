"""Result models and exception hierarchy."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, computed_field

RESERVED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "chunk_id",
        "content",
        "parent_id",
        "level",
        "sequence",
        "start_offset",
        "end_offset",
        "strategy",
        "strategy_metadata",
        "metadata",
        "level_name",
    }
)
"""Names a Policy ``metadata.fields`` entry must not use."""


def json_roundtrip_problem(value: Any) -> str | None:
    """Return why ``value`` is not losslessly representable as JSON, if any."""
    if value is None or isinstance(value, str | bool | int):
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return None
        return "non-finite floats are not valid JSON values"
    if isinstance(value, list):
        for item in value:
            problem = json_roundtrip_problem(item)
            if problem is not None:
                return problem
        return None
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return "object keys must be strings"
            problem = json_roundtrip_problem(item)
            if problem is not None:
                return problem
        return None
    return f"{type(value).__name__} is not a JSON value"


class ChunkweaveError(Exception):
    """Base class for all chunkweave errors."""


class PolicyLoadError(ChunkweaveError):
    """Raised when a Policy cannot be read or parsed from YAML."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PolicyValidationError(ChunkweaveError):
    """Raised when a Policy's structure or semantics are invalid."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        where = f" at {path}" if path else ""
        super().__init__(f"invalid policy{where}: {reason}")


class UnregisteredStrategyError(PolicyValidationError):
    """Raised when a strategy name is not registered."""

    def __init__(
        self, name: str, available: list[str] | None = None, path: str = ""
    ) -> None:
        self.name = name
        suffix = f" (available: {', '.join(sorted(available))})" if available else ""
        super().__init__(path, f"unregistered strategy {name!r}{suffix}")


class RegistryConflictError(ChunkweaveError):
    """Raised when registering a strategy under an already-used name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"strategy name already registered: {name!r} (pass replace=True to override)"
        )


class ProviderMissingError(ChunkweaveError):
    """Raised when a strategy requires a similarity provider but none was injected."""

    def __init__(self, strategy: str = "semantic") -> None:
        self.strategy = strategy
        super().__init__(
            f"strategy {strategy!r} requires an injected similarity provider; "
            "pass provider= to execute() before chunking"
        )


class ContextResolutionError(ChunkweaveError):
    """Raised when a metadata ``source`` cannot be resolved from the Context."""

    def __init__(self, field: str, path: str, reason: str) -> None:
        self.field = field
        self.path = path
        self.reason = reason
        super().__init__(
            f"cannot resolve metadata field {field!r} at {path}: {reason}"
        )


class ChunkSpan(BaseModel):
    """A strategy's raw output: a content slice plus its strategy metadata.

    Offsets are relative to the text the Chunker received, half-open
    ``[start_offset, end_offset)``, and ``content`` always equals
    ``text[start_offset:end_offset]``. The runtime later converts these into
    final :class:`Chunk` objects.
    """

    content: str
    start_offset: int
    end_offset: int
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A single chunk of text produced by the runtime.

    Offsets are global: Python string indexing semantics (Unicode code
    points), half-open ``[start_offset, end_offset)``, relative to the text
    passed to ``execute``. ``content`` always equals
    ``text[start_offset:end_offset]``. ``parent_id`` is ``None`` for root
    chunks; ``level`` starts at 0; ``sequence`` is the index among siblings.
    ``strategy_metadata`` holds strategy-produced fields; ``metadata`` holds
    the business fields declared by the Policy plus any include-option
    copies.
    """

    chunk_id: str
    content: str
    parent_id: str | None = None
    level: int
    sequence: int
    start_offset: int
    end_offset: int
    strategy: str
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkResult(BaseModel):
    """Result of an ``execute`` call.

    ``chunks`` is the flat list sorted by ``start_offset`` (parents before
    children at equal starts); ordering is produced by the runtime, not
    here. ``total`` is a computed serialization field equal to
    ``len(chunks)``; it is ignored on ``model_validate``.
    """

    chunks: list[Chunk]
    policy_id: str
    policy_version: str
    policy_hash: str
    execution_id: str
    engine_version: str
    execution_time_ms: float

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return len(self.chunks)


def chunk_id_for(index: int) -> str:
    """Deterministic sequential chunk id within one chunking call's output."""
    return f"chunk-{index:04d}"
