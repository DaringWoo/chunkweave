"""Hierarchical organization: N-level top-down descent."""

from __future__ import annotations

import itertools

from ..assembly import attach_level_custom, validate_custom_across_levels
from ..chunk import Chunk, ChunkMetadata, chunk_id_for
from ..config import HierarchicalConfig
from ..registry import Registry
from ..strategies.base import Chunker, ProviderAware, SimilarityProvider


class HierarchicalOrganization:
    """Executes each level's strategy per parent chunk.

    Every chunk of level *i* is independently chunked by the strategy of
    level *i+1*; parent results are never merged before re-chunking. Local
    offsets become global by adding the parent's ``start_offset``. A parent
    producing no children simply ends that branch. ``chunk_id`` values are
    renumbered in breadth-first order; ``parent_id``/``level``/``sequence``
    carry the hierarchy.
    """

    def __init__(
        self, registry: Registry, provider: SimilarityProvider | None = None
    ) -> None:
        self.registry = registry
        self.provider = provider

    def _inject(self, chunker: Chunker) -> None:
        if self.provider is not None and isinstance(chunker, ProviderAware):
            chunker.set_provider(self.provider)

    def run(self, text: str, config: HierarchicalConfig) -> list[Chunk]:
        if not text:
            return []
        levels = config.levels
        chunkers = [self.registry.create(lv.strategy, lv.config) for lv in levels]
        for chunker in chunkers:
            self._inject(chunker)
        level_meta = [dict(lv.metadata) for lv in levels]
        strategy_keys = [c.metadata_keys for c in chunkers]
        # Config-time rejection: validate before any chunking runs.
        validate_custom_across_levels(config.custom, level_meta, strategy_keys)

        counter = itertools.count()
        result: list[Chunk] = []

        def adopt(chunk: Chunk, level: int, parent_id: str | None, seq: int) -> Chunk:
            return Chunk(
                chunk_id=chunk_id_for(next(counter)),
                content=chunk.content,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                metadata=ChunkMetadata(
                    organization={
                        "parent_id": parent_id,
                        "level": level,
                        "sequence": seq,
                    },
                    strategy=dict(chunk.metadata.strategy),
                ),
            )

        frontier: list[Chunk] = []
        for seq, chunk in enumerate(chunkers[0].chunk(text)):
            adopted = adopt(chunk, 0, None, seq)
            frontier.append(adopted)
        result.extend(
            attach_level_custom(frontier, config.custom, level_meta, 0, strategy_keys[0])
        )
        frontier = result[: len(frontier)]

        for level in range(1, len(levels)):
            next_frontier: list[Chunk] = []
            for parent in frontier:
                for seq, child in enumerate(chunkers[level].chunk(parent.content)):
                    adopted = adopt(child, level, parent.chunk_id, seq)
                    # Local -> global offset conversion.
                    adopted.start_offset += parent.start_offset
                    adopted.end_offset += parent.start_offset
                    next_frontier.append(adopted)
            attached = attach_level_custom(
                next_frontier,
                config.custom,
                level_meta,
                level,
                strategy_keys[level],
            )
            result.extend(attached)
            frontier = attached
            if not frontier:
                break
        return result
