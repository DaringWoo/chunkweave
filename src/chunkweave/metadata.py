"""Custom metadata rules: reserved fields, conflict detection, assembly."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from .chunk import COMMON_FIELD_NAMES, ORGANIZATION_FIELD_NAMES, Chunk, ChunkMetadata
from .errors import ConfigError, MetadataConflictError


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
