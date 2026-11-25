"""Unified chunk result model and metadata grouping."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

COMMON_FIELD_NAMES: frozenset[str] = frozenset(
    {"chunk_id", "content", "start_offset", "end_offset"}
)
ORGANIZATION_FIELD_NAMES: frozenset[str] = frozenset({"parent_id", "level", "sequence"})


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
