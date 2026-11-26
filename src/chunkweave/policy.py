"""Policy model: YAML DSL loading and structural validation.

A Policy declares the chunking pipeline (``pipeline.levels``), strategy
``params`` and business metadata rules (``metadata.fields`` / ``include``).
This module covers the structural layer of the ``policy-engine`` spec:
loading, required fields, types, unknown-key rejection and field-name
rules. Semantic validation against the strategy registry (unregistered
strategy names, per-strategy ``params`` schema checks) and compilation to
the Execution IR live in the compiler layer.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)

from .models import RESERVED_METADATA_KEYS, PolicyLoadError, PolicyValidationError

API_VERSION = "chunkweave/v1"
"""The only ``api_version`` this engine accepts."""

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SOURCE_RE = re.compile(r"^context(\.[^.]+)+$")


class PolicyInfo(BaseModel):
    """Policy identity: ``id``, ``name``, ``version``."""

    model_config = ConfigDict(extra="forbid")

    id: StrictStr = Field(min_length=1)
    name: StrictStr = Field(min_length=1)
    version: StrictStr = Field(min_length=1)

    @field_validator("version")
    @classmethod
    def _version_format(cls, value: str) -> str:
        if not _VERSION_RE.match(value):
            raise ValueError(
                f"version must be MAJOR.MINOR.PATCH, got {value!r}"
            )
        return value


class LevelConfig(BaseModel):
    """One pipeline level: a strategy reference plus its ``params``."""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr = Field(min_length=1)
    strategy: StrictStr = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """``pipeline`` section: a non-empty ordered list of levels."""

    model_config = ConfigDict(extra="forbid")

    levels: list[LevelConfig] = Field(min_length=1)


class MetadataFieldConfig(BaseModel):
    """One business metadata field: fixed ``value`` or ``source`` path.

    Exactly one of ``value`` / ``source`` must be declared; ``value: null``
    counts as a declared fixed value. The serializer emits only the
    declared key so a ``model_dump()`` round-trip never turns into
    "both declared".
    """

    model_config = ConfigDict(extra="forbid")

    value: Any = None
    source: StrictStr | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> MetadataFieldConfig:
        has_value = "value" in self.model_fields_set
        has_source = "source" in self.model_fields_set
        if has_value == has_source:
            raise ValueError("must declare exactly one of 'value' or 'source'")
        if has_source:
            if self.source is None:
                raise ValueError("'source' must not be null")
            if not _SOURCE_RE.match(self.source):
                raise ValueError(
                    f"'source' must be a context path like 'context.doc.author', "
                    f"got {self.source!r}"
                )
        else:
            try:
                json.dumps(self.value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"'value' must be JSON-serializable: {e}") from e
        return self

    @property
    def is_fixed(self) -> bool:
        """True when this field holds a declared fixed ``value``."""
        return "value" in self.model_fields_set

    @property
    def is_context(self) -> bool:
        """True when this field resolves from a ``source`` context path."""
        return "source" in self.model_fields_set

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        if "source" in self.model_fields_set:
            return {"source": self.source}
        return {"value": self.value}


class MetadataIncludeConfig(BaseModel):
    """``metadata.include``: copy reserved keys into ``metadata`` or not."""

    model_config = ConfigDict(extra="forbid")

    strategy: StrictBool = True
    organization: StrictBool = True


class MetadataConfig(BaseModel):
    """``metadata`` section: declared business fields plus include options."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, MetadataFieldConfig] = Field(default_factory=dict)
    include: MetadataIncludeConfig = Field(default_factory=MetadataIncludeConfig)

    @field_validator("fields")
    @classmethod
    def _field_names_allowed(
        cls, fields: dict[str, MetadataFieldConfig]
    ) -> dict[str, MetadataFieldConfig]:
        for name in fields:
            if not name:
                raise ValueError("metadata field name must be a non-empty string")
            if name in RESERVED_METADATA_KEYS:
                raise ValueError(
                    f"metadata field name {name!r} uses a reserved key"
                )
        return fields


def format_loc(loc: tuple[Any, ...]) -> str:
    """Format a pydantic error ``loc`` as ``a.b[0].c`` field path."""
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts:
                parts.append(".")
            parts.append(str(item))
    return "".join(parts)


class Policy(BaseModel):
    """A loaded Policy: identity, pipeline levels and metadata rules."""

    model_config = ConfigDict(extra="forbid")

    api_version: StrictStr
    policy: PolicyInfo
    pipeline: PipelineConfig
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)

    @field_validator("api_version")
    @classmethod
    def _api_version_supported(cls, value: str) -> str:
        if value != API_VERSION:
            raise ValueError(
                f"unsupported api_version {value!r}; supported: {API_VERSION!r}"
            )
        return value

    @property
    def id(self) -> str:
        """Shortcut for ``policy.policy.id``."""
        return self.policy.id

    @property
    def name(self) -> str:
        """Shortcut for ``policy.policy.name``."""
        return self.policy.name

    @property
    def version(self) -> str:
        """Shortcut for ``policy.policy.version``."""
        return self.policy.version

    @classmethod
    def from_yaml(cls, yaml_text: str) -> Policy:
        """Parse a Policy from a YAML string using safe loading.

        Unsafe tags (e.g. ``!!python/object``), YAML syntax errors and a
        non-mapping root raise :class:`PolicyLoadError`; structural and
        semantic violations raise :class:`PolicyValidationError`.
        """
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = (
                f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
            )
            raise PolicyLoadError(f"cannot parse policy YAML{where}: {e}") from e
        if not isinstance(data, dict):
            raise PolicyLoadError(
                f"policy root must be a mapping, got {type(data).__name__}"
            )
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            first = e.errors()[0]
            raise PolicyValidationError(
                format_loc(first["loc"]), first["msg"]
            ) from e

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> Policy:
        """Read a UTF-8 YAML file and parse it as a Policy."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            raise PolicyLoadError(f"cannot read policy file {path}: {e}") from e
        return cls.from_yaml(text)
