"""Runtime organization: N-level top-down descent over the ExecutionPlan.

A single level is flat output; N levels descend parent by parent: every
chunk of level *i* is independently chunked by the level *i+1* chunker,
parent results are never merged before re-chunking, and span offsets become
global by adding the parent's ``start_offset``. Empty spans are dropped
before ``chunk_id``/``sequence`` numbering; a parent producing no children
simply ends that branch. ``chunk_id`` values are numbered in breadth-first
order.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from .compiler import ExecutionPlan
from .metadata import build_metadata
from .models import Chunk, ChunkSpan, chunk_id_for
from .strategies import Chunker


def run(
    text: str,
    plan: ExecutionPlan,
    chunkers: Sequence[Chunker],
    field_values: Mapping[str, Any],
) -> list[Chunk]:
    """Execute the per-level descent over ``text`` and return sorted chunks."""
    if not text:
        return []

    counter = itertools.count()
    result: list[Chunk] = []

    def make_chunk(
        span: ChunkSpan, level: int, parent_id: str | None, seq: int, base: int
    ) -> Chunk:
        plan_level = plan.levels[level]
        return Chunk(
            chunk_id=chunk_id_for(next(counter)),
            content=span.content,
            parent_id=parent_id,
            level=level,
            sequence=seq,
            start_offset=base + span.start_offset,
            end_offset=base + span.end_offset,
            strategy=plan_level.strategy,
            strategy_metadata=dict(span.strategy_metadata),
            metadata=build_metadata(
                field_values,
                plan,
                parent_id=parent_id,
                level=level,
                sequence=seq,
                level_name=plan_level.name,
                strategy=plan_level.strategy,
                strategy_metadata=span.strategy_metadata,
            ),
        )

    frontier: list[Chunk] = []
    for seq, span in enumerate(s for s in chunkers[0].chunk(text) if s.content):
        frontier.append(make_chunk(span, 0, None, seq, 0))
    result.extend(frontier)

    for level in range(1, len(chunkers)):
        next_frontier: list[Chunk] = []
        for parent in frontier:
            children = [
                s for s in chunkers[level].chunk(parent.content) if s.content
            ]
            for seq, span in enumerate(children):
                next_frontier.append(
                    make_chunk(span, level, parent.chunk_id, seq, parent.start_offset)
                )
        result.extend(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return sorted(result, key=lambda c: (c.start_offset, c.level))
