"""Organization execution: N-level top-down descent.

Flat is the single-level special case: one chunker, no organization fields
written. Hierarchical runs N levels; every chunk of level *i* is
independently chunked by the chunker of level *i+1*, parent results are
never merged before re-chunking, and local offsets become global by adding
the parent's ``start_offset``. A parent producing no children simply ends
that branch. ``chunk_id`` values are renumbered in breadth-first order.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from .metadata import attach_level_custom, validate_custom_across_levels
from .models import Chunk, ChunkMetadata, chunk_id_for
from .strategies import Chunker


def run(
    text: str,
    chunkers: Sequence[Chunker],
    engine_custom: Mapping[str, Any],
    level_metadata: Sequence[Mapping[str, Any]],
    *,
    write_organization: bool,
) -> list[Chunk]:
    """Execute the per-level descent over ``text``.

    ``chunkers`` holds one prepared chunker per level; ``level_metadata``
    carries each level's ``metadata`` mapping. With ``write_organization``
    off, chunks keep an empty ``organization`` group (flat); with it on,
    ``parent_id``/``level``/``sequence`` are written (hierarchical).
    """
    if not text:
        return []
    strategy_keys = [c.metadata_keys for c in chunkers]
    # Config-time rejection: validate before any chunking runs.
    validate_custom_across_levels(engine_custom, level_metadata, strategy_keys)

    counter = itertools.count()
    result: list[Chunk] = []

    def adopt(chunk: Chunk, level: int, parent_id: str | None, seq: int) -> Chunk:
        organization = (
            {"parent_id": parent_id, "level": level, "sequence": seq}
            if write_organization
            else {}
        )
        return Chunk(
            chunk_id=chunk_id_for(next(counter)),
            content=chunk.content,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            metadata=ChunkMetadata(
                organization=organization,
                strategy=dict(chunk.metadata.strategy),
            ),
        )

    frontier: list[Chunk] = []
    for seq, chunk in enumerate(chunkers[0].chunk(text)):
        frontier.append(adopt(chunk, 0, None, seq))
    result.extend(
        attach_level_custom(frontier, engine_custom, level_metadata, 0, strategy_keys[0])
    )
    frontier = result[: len(frontier)]

    for level in range(1, len(chunkers)):
        next_frontier: list[Chunk] = []
        for parent in frontier:
            for seq, child in enumerate(chunkers[level].chunk(parent.content)):
                adopted = adopt(child, level, parent.chunk_id, seq)
                # Local -> global offset conversion.
                adopted.start_offset += parent.start_offset
                adopted.end_offset += parent.start_offset
                next_frontier.append(adopted)
        attached = attach_level_custom(
            next_frontier, engine_custom, level_metadata, level, strategy_keys[level]
        )
        result.extend(attached)
        frontier = attached
        if not frontier:
            break
    return result
