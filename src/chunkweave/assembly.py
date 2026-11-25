"""Metadata assembly: merge the four metadata groups onto produced chunks.

Common metadata lives on :class:`Chunk` itself; organization fields are
written by the organization executors; strategy metadata comes from the
strategy; custom metadata is merged here from the engine-level ``custom``
plus each level's ``metadata`` (nearest level wins, deep-copied per chunk).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .chunk import Chunk
from .errors import MetadataConflictError
from .metadata import attach_custom_metadata, reserved_field_names


def custom_for_level(
    engine_custom: Mapping[str, Any],
    level_metadata: Sequence[Mapping[str, Any]],
    level: int,
) -> dict[str, Any]:
    """Custom metadata for chunks produced at ``level``.

    Engine-level ``custom`` propagates to every descendant; each level's
    ``metadata`` applies to its own chunks and is inherited by descendants,
    nearer levels overriding on key conflicts.
    """
    merged = dict(engine_custom)
    for i in range(level + 1):
        merged.update(level_metadata[i])
    return merged


def validate_custom_across_levels(
    engine_custom: Mapping[str, Any],
    level_metadata: Sequence[Mapping[str, Any]],
    strategy_keys_per_level: Sequence[frozenset[str]],
) -> None:
    """Config-time reserved-field validation for every level.

    The custom keys landing on a level's chunks are the engine custom plus
    the metadata of every level up to and including it; each such merged key
    set must not collide with that level's reserved fields (common +
    organization + its strategy's ``metadata_keys``).
    """
    accumulated: dict[str, Any] = dict(engine_custom)
    for meta, keys in zip(level_metadata, strategy_keys_per_level, strict=True):
        accumulated.update(meta)
        conflicts = set(accumulated) & reserved_field_names(keys)
        if conflicts:
            raise MetadataConflictError(conflicts)


def attach_level_custom(
    chunks: list[Chunk],
    engine_custom: Mapping[str, Any],
    level_metadata: Sequence[Mapping[str, Any]],
    level: int,
    strategy_keys: frozenset[str],
) -> list[Chunk]:
    """Attach the merged custom metadata for ``level`` to ``chunks``."""
    custom = custom_for_level(engine_custom, level_metadata, level)
    return attach_custom_metadata(chunks, custom, strategy_keys)
