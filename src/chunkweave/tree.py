"""Tree view over flat chunk results, rebuilt from ``parent_id`` on demand."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .chunk import Chunk


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
        self.chunks.sort(
            key=lambda c: (c.start_offset, c.metadata.organization.get("level", 0))
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
