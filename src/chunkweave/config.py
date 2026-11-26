"""Strategy and organization configuration models with JSON serialization."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from .models import ConfigError
from .strategies import (
    DEFAULT_SEPARATORS,
    DEFAULT_UNIT_SEPARATORS,
    KeepSeparator,
    Separator,
)

__all__ = [
    "DEFAULT_SEPARATORS",
    "DEFAULT_UNIT_SEPARATORS",
    "EngineConfig",
    "FlatConfig",
    "HierarchicalConfig",
    "KeepSeparator",
    "LevelConfig",
    "RecursiveConfig",
    "SemanticConfig",
    "Separator",
    "SlidingWindowConfig",
    "engine_config_from_dict",
]


def _require_positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(name, f"expected int, got {type(value).__name__}")
    if value <= 0:
        raise ConfigError(name, f"must be > 0, got {value}")
    return value


def _separator_to_dict(sep: Separator) -> dict[str, Any]:
    if isinstance(sep, re.Pattern):
        return {"value": sep.pattern, "regex": True}
    return {"value": sep, "regex": False}


def _separator_from_dict(data: Any) -> Separator:
    if isinstance(data, str | re.Pattern):
        return data
    if isinstance(data, Mapping):
        value = data.get("value")
        if not isinstance(value, str):
            raise ConfigError("separators", f"separator 'value' must be a string, got {data!r}")
        if data.get("regex"):
            return re.compile(value)
        return value
    raise ConfigError("separators", f"unsupported separator form: {data!r}")


def _separators_to_dict(separators: list[Separator]) -> list[dict[str, Any]]:
    return [_separator_to_dict(s) for s in separators]


def _separators_from_dict(data: Any, name: str = "separators") -> list[Separator]:
    if data is None:
        return []
    if not isinstance(data, list | tuple):
        raise ConfigError(name, f"expected a list of separators, got {type(data).__name__}")
    return [_separator_from_dict(s) for s in data]


def _validate_separator_items(separators: list[Separator], name: str) -> list[Separator]:
    for sep in separators:
        if not isinstance(sep, str | re.Pattern):
            raise ConfigError(
                name, f"separator must be str or re.Pattern, got {type(sep).__name__}"
            )
    return list(separators)


@dataclass(frozen=True)
class SlidingWindowConfig:
    """Config for ``sliding_window``. Lengths are in Unicode code points."""

    chunk_size: int
    overlap: int = 0

    def __post_init__(self) -> None:
        _require_positive_int("chunk_size", self.chunk_size)
        if isinstance(self.overlap, bool) or not isinstance(self.overlap, int):
            raise ConfigError("overlap", f"expected int, got {type(self.overlap).__name__}")
        if self.overlap < 0 or self.overlap >= self.chunk_size:
            raise ConfigError(
                "overlap", f"must satisfy 0 <= overlap < chunk_size, got {self.overlap}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"chunk_size": self.chunk_size, "overlap": self.overlap}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SlidingWindowConfig:
        return cls(
            chunk_size=data.get("chunk_size"),  # type: ignore[arg-type]
            overlap=data.get("overlap", 0),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> SlidingWindowConfig:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class RecursiveConfig:
    """Config for ``recursive``. ``separators`` mix literals and regexes."""

    chunk_size: int
    separators: list[Separator] = field(
        default_factory=lambda: list(DEFAULT_SEPARATORS)
    )
    overlap: int = 0
    keep_separator: KeepSeparator = "previous"
    max_depth: int | None = None

    def __post_init__(self) -> None:
        _require_positive_int("chunk_size", self.chunk_size)
        object.__setattr__(
            self, "separators", _validate_separator_items(self.separators, "separators")
        )
        if isinstance(self.overlap, bool) or not isinstance(self.overlap, int):
            raise ConfigError("overlap", f"expected int, got {type(self.overlap).__name__}")
        if self.overlap < 0:
            raise ConfigError("overlap", f"must be >= 0, got {self.overlap}")
        if self.keep_separator not in ("previous", "next", "none"):
            raise ConfigError(
                "keep_separator",
                f"must be 'previous', 'next' or 'none', got {self.keep_separator!r}",
            )
        if self.max_depth is not None:
            _require_positive_int("max_depth", self.max_depth)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_size": self.chunk_size,
            "separators": _separators_to_dict(self.separators),
            "overlap": self.overlap,
            "keep_separator": self.keep_separator,
            "max_depth": self.max_depth,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RecursiveConfig:
        separators: list[Separator] = (
            list(DEFAULT_SEPARATORS)
            if "separators" not in data
            else _separators_from_dict(data["separators"])
        )
        return cls(
            chunk_size=data.get("chunk_size"),  # type: ignore[arg-type]
            separators=separators,
            overlap=data.get("overlap", 0),
            keep_separator=data.get("keep_separator", "previous"),
            max_depth=data.get("max_depth"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> RecursiveConfig:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class SemanticConfig:
    """Config for ``semantic``. Provider is injected, never serialized."""

    threshold: float
    chunk_size: int
    unit_separators: list[Separator] = field(
        default_factory=lambda: list(DEFAULT_UNIT_SEPARATORS)
    )

    def __post_init__(self) -> None:
        _require_positive_int("chunk_size", self.chunk_size)
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, int | float):
            raise ConfigError(
                "threshold",
                f"expected float in [0, 1], got {type(self.threshold).__name__}",
            )
        if not 0.0 <= float(self.threshold) <= 1.0:
            raise ConfigError("threshold", f"must be in [0, 1], got {self.threshold}")
        object.__setattr__(self, "threshold", float(self.threshold))
        object.__setattr__(
            self,
            "unit_separators",
            _validate_separator_items(self.unit_separators, "unit_separators"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold": self.threshold,
            "chunk_size": self.chunk_size,
            "unit_separators": _separators_to_dict(self.unit_separators),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SemanticConfig:
        separators: list[Separator] = (
            list(DEFAULT_UNIT_SEPARATORS)
            if "unit_separators" not in data
            else _separators_from_dict(data["unit_separators"], "unit_separators")
        )
        return cls(
            threshold=data.get("threshold"),  # type: ignore[arg-type]
            chunk_size=data.get("chunk_size"),  # type: ignore[arg-type]
            unit_separators=separators,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> SemanticConfig:
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class LevelConfig:
    """One level of a hierarchical organization config."""

    strategy: str
    config: Mapping[str, Any] = field(default_factory=dict)
    name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, str) or not self.strategy:
            raise ConfigError("strategy", "level strategy name must be a non-empty string")
        if self.name is not None and not isinstance(self.name, str):
            raise ConfigError("name", f"level name must be a string, got {self.name!r}")
        if not isinstance(self.config, Mapping):
            raise ConfigError(
                "config", f"level config must be a mapping, got {self.config!r}"
            )
        if not isinstance(self.metadata, Mapping):
            raise ConfigError(
                "metadata", f"level metadata must be a mapping, got {self.metadata!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"strategy": self.strategy, "config": dict(self.config)}
        if self.name is not None:
            out["name"] = self.name
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LevelConfig:
        return cls(
            strategy=data.get("strategy"),  # type: ignore[arg-type]
            config=data.get("config") or {},
            name=data.get("name"),
            metadata=data.get("metadata") or {},
        )


@dataclass(frozen=True)
class FlatConfig:
    """Flat organization config: a single strategy reference."""

    strategy: str
    config: Mapping[str, Any] = field(default_factory=dict)
    custom: Mapping[str, Any] = field(default_factory=dict)
    organization: Literal["flat"] = "flat"

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, str) or not self.strategy:
            raise ConfigError("strategy", "strategy name must be a non-empty string")
        if not isinstance(self.config, Mapping):
            raise ConfigError("config", f"strategy config must be a mapping, got {self.config!r}")
        if not isinstance(self.custom, Mapping):
            raise ConfigError("custom", f"custom metadata must be a mapping, got {self.custom!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization": "flat",
            "strategy": self.strategy,
            "config": dict(self.config),
            "custom": dict(self.custom),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FlatConfig:
        return cls(
            strategy=data.get("strategy"),  # type: ignore[arg-type]
            config=data.get("config") or {},
            custom=data.get("custom") or {},
        )


@dataclass(frozen=True)
class HierarchicalConfig:
    """Hierarchical organization config: a non-empty list of levels."""

    levels: list[LevelConfig]
    custom: Mapping[str, Any] = field(default_factory=dict)
    organization: Literal["hierarchical"] = "hierarchical"

    def __post_init__(self) -> None:
        if not isinstance(self.levels, list | tuple):
            raise ConfigError(
                "levels", f"must be a list, got {type(self.levels).__name__}"
            )
        if len(self.levels) == 0:
            raise ConfigError("levels", "must contain at least one level")
        object.__setattr__(self, "levels", list(self.levels))
        for i, level in enumerate(self.levels):
            if not isinstance(level, LevelConfig):
                raise ConfigError("levels", f"level {i} is not a LevelConfig: {level!r}")
        if not isinstance(self.custom, Mapping):
            raise ConfigError("custom", f"custom metadata must be a mapping, got {self.custom!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization": "hierarchical",
            "levels": [level.to_dict() for level in self.levels],
            "custom": dict(self.custom),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HierarchicalConfig:
        raw_levels = data.get("levels")
        if raw_levels is None:
            raise ConfigError("levels", "missing required 'levels' list")
        if not isinstance(raw_levels, list | tuple):
            raise ConfigError(
                "levels", f"must be a list, got {type(raw_levels).__name__}"
            )
        return cls(
            levels=[LevelConfig.from_dict(item) for item in raw_levels],
            custom=data.get("custom") or {},
        )


EngineConfig = FlatConfig | HierarchicalConfig


def engine_config_from_dict(data: Mapping[str, Any]) -> EngineConfig:
    """Build a Flat or Hierarchical config from its serialized dict form."""
    organization = data.get("organization")
    if organization == "flat":
        return FlatConfig.from_dict(data)
    if organization == "hierarchical":
        return HierarchicalConfig.from_dict(data)
    raise ConfigError(
        "organization", f"must be 'flat' or 'hierarchical', got {organization!r}"
    )
