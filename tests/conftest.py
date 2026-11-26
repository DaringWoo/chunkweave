"""Shared helpers: Policy construction and deterministic providers."""

from __future__ import annotations

from typing import Any

import yaml

from chunkweave import Policy


def make_policy(
    levels: list[dict[str, Any]],
    *,
    fields: dict[str, Any] | None = None,
    include: dict[str, Any] | None = None,
    policy_id: str = "test-policy",
    name: str = "test",
    version: str = "1.0.0",
) -> Policy:
    """Build a Policy object from plain data (same shape as YAML)."""
    data: dict[str, Any] = {
        "api_version": "chunkweave/v1",
        "policy": {"id": policy_id, "name": name, "version": version},
        "pipeline": {"levels": levels},
    }
    metadata: dict[str, Any] = {}
    if fields is not None:
        metadata["fields"] = fields
    if include is not None:
        metadata["include"] = include
    if metadata:
        data["metadata"] = metadata
    return Policy.model_validate(data)


def policy_from_yaml(
    levels: list[dict[str, Any]],
    *,
    fields: dict[str, Any] | None = None,
    include: dict[str, Any] | None = None,
    policy_id: str = "test-policy",
    name: str = "test",
    version: str = "1.0.0",
) -> Policy:
    """Build a Policy through ``from_yaml`` (exercises the YAML path)."""
    data: dict[str, Any] = {
        "api_version": "chunkweave/v1",
        "policy": {"id": policy_id, "name": name, "version": version},
        "pipeline": {"levels": levels},
    }
    metadata: dict[str, Any] = {}
    if fields is not None:
        metadata["fields"] = fields
    if include is not None:
        metadata["include"] = include
    if metadata:
        data["metadata"] = metadata
    return Policy.from_yaml(yaml.safe_dump(data, allow_unicode=True))


class FakeProvider:
    """Deterministic provider: similar when units start with the same char."""

    def __init__(self, scores: dict[tuple[str, str], float] | None = None, default=0.9):
        self.scores = dict(scores or {})
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def score(self, left: str, right: str) -> float:
        self.calls.append((left, right))
        return self.scores.get((left, right), self.default)
