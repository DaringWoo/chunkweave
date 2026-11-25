"""Result models and exception hierarchy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

COMMON_FIELD_NAMES: frozenset[str] = frozenset(
    {"chunk_id", "content", "start_offset", "end_offset"}
)
ORGANIZATION_FIELD_NAMES: frozenset[str] = frozenset({"parent_id", "level", "sequence"})


class ChunkweaveError(Exception):
    """Base class for all chunkweave errors."""


class ConfigError(ChunkweaveError):
    """Raised when a strategy or organization configuration is invalid."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"invalid config field {field!r}: {reason}")


class UnregisteredStrategyError(ChunkweaveError):
    """Raised when a strategy name is not registered."""

    def __init__(self, name: str, available: list[str] | None = None) -> None:
        self.name = name
        suffix = f" (available: {', '.join(sorted(available))})" if available else ""
        super().__init__(f"unregistered strategy: {name!r}{suffix}")


class RegistryConflictError(ChunkweaveError):
    """Raised when registering a strategy under an already-used name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"strategy name already registered: {name!r} (pass replace=True to override)"
        )


class MetadataConflictError(ChunkweaveError):
    """Raised when custom metadata collides with a reserved field name."""

    def __init__(self, keys: set[str]) -> None:
        self.keys = set(keys)
        super().__init__(
            "custom metadata conflicts with reserved fields: " + ", ".join(sorted(self.keys))
        )


class ProviderMissingError(ChunkweaveError):
    """Raised when a strategy requires a similarity provider but none was injected."""

    def __init__(self, strategy: str = "semantic") -> None:
        self.strategy = strategy
        super().__init__(
            f"strategy {strategy!r} requires an injected similarity provider; "
            "call set_provider() or pass provider= before chunking"
        )


@dataclass
class ChunkMetadata:
    """Metadata carried by a chunk, split into disjoint groups.

    ``organization`` holds fields the organization layer writes
    (``parent_id``, ``level``, ``sequence``); ``strategy`` holds fields a
    chunking strategy declares via ``metadata_keys``; ``custom`` holds
    caller-supplied metadata. Common fields (``chunk_id``, ``content``,
    ``start_offset``, ``end_offset``) live directly on :class:`Chunk`.
    """

    organization: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization": self.organization,
            "strategy": self.strategy,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChunkMetadata:
        return cls(
            organization=dict(data.get("organization") or {}),
            strategy=dict(data.get("strategy") or {}),
            custom=dict(data.get("custom") or {}),
        )


@dataclass
class Chunk:
    """A single chunk of text.

    Offsets use Python string indexing semantics (Unicode code points),
    half-open ``[start_offset, end_offset)``, relative to the text passed to
    the chunking call that produced it. ``content`` always equals
    ``text[start_offset:end_offset]``.
    """

    chunk_id: str
    content: str
    start_offset: int
    end_offset: int
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            content=str(data["content"]),
            start_offset=int(data["start_offset"]),
            end_offset=int(data["end_offset"]),
            metadata=ChunkMetadata.from_dict(data.get("metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> Chunk:
        return cls.from_dict(json.loads(payload))


def chunk_id_for(index: int) -> str:
    """Deterministic sequential chunk id within one chunking call's output."""
    return f"chunk-{index:04d}"


@dataclass
class ChunkNode:
    """A chunk plus its children; the tree is derived, never cached."""

    chunk: Chunk
    children: list[ChunkNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ChunkResult:
    """Result of a chunking call.

    ``chunks`` is the flat collection sorted by ``start_offset`` (parents
    before children at equal starts). ``tree()`` recomputes the nested view
    from ``parent_id`` every call so the two views can never drift.
    """

    chunks: list[Chunk]

    def __post_init__(self) -> None:
        self.chunks = sorted(
            self.chunks,
            key=lambda c: (c.start_offset, c.metadata.organization.get("level", 0)),
        )

    def tree(self) -> list[ChunkNode]:
        nodes = {c.chunk_id: ChunkNode(c) for c in self.chunks}
        roots: list[ChunkNode] = []
        for chunk in self.chunks:
            parent_id = chunk.metadata.organization.get("parent_id")
            parent = nodes.get(parent_id) if parent_id is not None else None
            if parent is None:
                roots.append(nodes[chunk.chunk_id])
            else:
                parent.children.append(nodes[chunk.chunk_id])
        return roots

    def to_dict(self) -> dict[str, Any]:
        return {"chunks": [c.to_dict() for c in self.chunks]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChunkResult:
        return cls(chunks=[Chunk.from_dict(d) for d in data["chunks"]])

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> ChunkResult:
        return cls.from_dict(json.loads(payload))
