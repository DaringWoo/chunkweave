"""Custom metadata rules: reserved fields, conflict detection, assembly.

Common metadata lives on :class:`Chunk` itself; organization fields are
written by the organization executor; strategy metadata comes from the
strategy; custom metadata is merged here from the engine-level ``custom``
plus each level's ``metadata`` (nearest level wins, deep-copied per chunk).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from .models import (
    COMMON_FIELD_NAMES,
    ORGANIZATION_FIELD_NAMES,
    Chunk,
    ChunkMetadata,
    ConfigError,
    MetadataConflictError,
)


def reserved_field_names(strategy_keys: Iterable[str] = ()) -> frozenset[str]:
    """Reserved metadata fields: common + organization + strategy-declared keys."""
    return COMMON_FIELD_NAMES | ORGANIZATION_FIELD_NAMES | frozenset(strategy_keys)


def _check_json_serializable(custom: Mapping[str, Any]) -> None:
    for key, value in custom.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                str(key), f"custom metadata value is not JSON serializable: {exc}"
            ) from exc


def validate_custom_metadata(
    custom: Mapping[str, Any], reserved: Iterable[str] = ()
) -> frozenset[str]:
    """Validate custom metadata keys and values.

    Returns the set of custom keys. Raises :class:`MetadataConflictError` when
    a key collides with a reserved field and :class:`ConfigError` when a value
    is not JSON serializable.
    """
    reserved_set = reserved_field_names(reserved)
    conflicts = set(custom) & reserved_set
    if conflicts:
        raise MetadataConflictError(conflicts)
    _check_json_serializable(custom)
    return frozenset(custom)


def attach_custom_metadata(
    chunks: Iterable[Chunk],
    custom: Mapping[str, Any] | None,
    strategy_keys: Iterable[str] = (),
) -> list[Chunk]:
    """Return a new list of chunks with ``custom`` merged into each custom group.

    Keys are validated against reserved fields (common + organization +
    ``strategy_keys``) before any chunk is produced. Every chunk receives an
    independent deep copy, and incoming custom values override existing custom
    keys on a chunk (nearest-source-wins ordering is the caller's
    responsibility). The input list and chunks are left unmodified.
    """
    if not custom:
        return list(chunks)
    validate_custom_metadata(custom, strategy_keys)
    out: list[Chunk] = []
    for chunk in chunks:
        merged_custom = copy.deepcopy(chunk.metadata.custom)
        merged_custom.update(copy.deepcopy(dict(custom)))
        new_meta = ChunkMetadata(
            organization=dict(chunk.metadata.organization),
            strategy=dict(chunk.metadata.strategy),
            custom=merged_custom,
        )
        out.append(replace(chunk, metadata=new_meta))
    return out


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
