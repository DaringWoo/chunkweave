"""Metadata Builder: resolve declared fields and assemble ``metadata``.

Business ``metadata`` holds exactly the fields declared by the Policy's
``metadata.fields`` (fixed ``value`` or ``source`` context path) plus the
reserved keys copied in by the include options. Every chunk gets an
independent deep copy.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from .compiler import ExecutionPlan
from .models import ContextResolutionError


def resolve_fields(
    plan: ExecutionPlan, context: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Resolve every declared metadata field once, before any chunking.

    ``value`` fields take their declared constant; ``source`` fields walk
    the field's ``path`` segments inside ``context``. Keys in ``context``
    that no field references are never read.
    """
    values: dict[str, Any] = {}
    for field in plan.metadata_fields:
        dotted = "context." + ".".join(field.path)
        if field.kind == "value":
            values[field.name] = field.value
            continue
        if context is None:
            raise ContextResolutionError(field.name, dotted, "no context provided")
        node: Any = context
        for depth, segment in enumerate(field.path):
            if not isinstance(node, Mapping):
                walked = ".".join(field.path[:depth])
                raise ContextResolutionError(
                    field.name,
                    dotted,
                    f"context{'.' + walked if walked else ''} is not a mapping",
                )
            if segment not in node:
                walked = ".".join(field.path[: depth + 1])
                raise ContextResolutionError(
                    field.name, dotted, f"missing key 'context.{walked}'"
                )
            node = node[segment]
        try:
            json.dumps(node)
        except (TypeError, ValueError) as e:
            raise ContextResolutionError(
                field.name, dotted, "value is not JSON-serializable"
            ) from e
        values[field.name] = node
    return values


def build_metadata(
    field_values: Mapping[str, Any],
    plan: ExecutionPlan,
    *,
    parent_id: str | None,
    level: int,
    sequence: int,
    level_name: str,
    strategy: str,
    strategy_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble one chunk's ``metadata`` dict (an independent deep copy)."""
    metadata = copy.deepcopy(dict(field_values))
    if plan.include_organization:
        metadata["parent_id"] = parent_id
        metadata["level"] = level
        metadata["sequence"] = sequence
        metadata["level_name"] = level_name
    if plan.include_strategy:
        metadata["strategy"] = strategy
        metadata["strategy_metadata"] = copy.deepcopy(dict(strategy_metadata))
    return metadata
