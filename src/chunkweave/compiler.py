"""Policy compiler: semantic validation and Execution IR (``ExecutionPlan``).

Compilation checks each level's strategy name against the Registry and
validates ``params`` against that strategy's ``params_model``, then emits a
pure, JSON-serializable plan. No chunking happens here.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from .models import PolicyValidationError, UnregisteredStrategyError
from .policy import Policy, format_loc

if TYPE_CHECKING:
    from .engine import Registry


class PlanLevel(BaseModel):
    """One compiled pipeline level."""

    index: int
    name: str
    strategy: str
    params: dict[str, Any] = Field(default_factory=dict)
    requires_provider: bool = False


class PlanField(BaseModel):
    """One compiled metadata field: fixed value or resolved context path."""

    name: str
    kind: Literal["value", "source"]
    value: Any = None
    path: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """The Execution IR produced by compiling a Policy.

    Pure serializable structure: no provider, no callables, no runtime
    objects. ``levels[i].params`` holds the declared form with the params
    model's defaults filled in.
    """

    api_version: str
    policy_id: str
    policy_name: str
    policy_version: str
    policy_hash: str
    levels: list[PlanLevel]
    metadata_fields: list[PlanField] = Field(default_factory=list)
    include_strategy: bool = True
    include_organization: bool = True


def policy_hash(policy: Policy) -> str:
    """Stable ``sha256:<64 hex>`` hash of the normalized Policy model.

    Normalization is key-sorted JSON over ``policy.model_dump(mode="json")``
    (UTF-8, compact separators), so YAML key order, whitespace, comments and
    quoting style do not affect the hash, while any declared-value change
    does. Strategy params defaults, context, text and provider are excluded.
    """
    canonical = json.dumps(
        policy.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_policy(policy: Policy, registry: Registry) -> ExecutionPlan:
    """Validate ``policy`` semantically and produce its ExecutionPlan."""
    levels: list[PlanLevel] = []
    for i, level in enumerate(policy.pipeline.levels):
        try:
            spec = registry.get(level.strategy)
        except UnregisteredStrategyError:
            raise UnregisteredStrategyError(
                level.strategy,
                registry.names(),
                path=f"pipeline.levels[{i}].strategy",
            ) from None
        known = set(spec.params_model.model_fields)
        for key in level.params:
            if key not in known:
                raise PolicyValidationError(
                    f"pipeline.levels[{i}].params.{key}",
                    f"unknown parameter {key!r} for strategy "
                    f"{level.strategy!r} (level {level.name!r})",
                )
        try:
            validated = spec.params_model.model_validate(level.params)
        except ValidationError as e:
            first = e.errors()[0]
            loc = format_loc(first["loc"])
            path = f"pipeline.levels[{i}].params" + (f".{loc}" if loc else "")
            raise PolicyValidationError(
                path,
                f"strategy {level.strategy!r} (level {level.name!r}): "
                f"{first['msg']}",
            ) from e
        levels.append(
            PlanLevel(
                index=i,
                name=level.name,
                strategy=level.strategy,
                params=validated.model_dump(mode="json"),
                requires_provider=spec.requires_provider,
            )
        )

    fields: list[PlanField] = []
    for name, field_cfg in policy.metadata.fields.items():
        if field_cfg.is_context:
            assert field_cfg.source is not None
            fields.append(
                PlanField(
                    name=name,
                    kind="source",
                    path=field_cfg.source.split(".")[1:],
                )
            )
        else:
            fields.append(PlanField(name=name, kind="value", value=field_cfg.value))

    return ExecutionPlan(
        api_version=policy.api_version,
        policy_id=policy.policy.id,
        policy_name=policy.policy.name,
        policy_version=policy.policy.version,
        policy_hash=policy_hash(policy),
        levels=levels,
        metadata_fields=fields,
        include_strategy=policy.metadata.include.strategy,
        include_organization=policy.metadata.include.organization,
    )
