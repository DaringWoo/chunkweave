"""Public API entry point: strategy registry and ChunkEngine."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from . import organization
from .compiler import ExecutionPlan, compile_policy
from .metadata import resolve_fields
from .models import (
    ChunkResult,
    ProviderMissingError,
    RegistryConflictError,
    UnregisteredStrategyError,
)
from .policy import Policy
from .strategies import (
    Chunker,
    RecursiveChunker,
    RecursiveParams,
    SemanticChunker,
    SemanticParams,
    SimilarityProvider,
    SlidingWindowChunker,
    SlidingWindowParams,
)

ChunkerFactory = Callable[[Any, "SimilarityProvider | None"], Chunker]
"""``(validated params instance, provider) -> Chunker``."""


@dataclass(frozen=True)
class StrategySpec:
    """Registration record: factory, params schema and provider need."""

    name: str
    factory: ChunkerFactory
    params_model: type[BaseModel]
    requires_provider: bool = False


class Registry:
    """Maps strategy names to :class:`StrategySpec` records.

    Only responsible for registration and lookup; params validation happens
    in the compiler, hierarchy execution in the runtime.
    """

    def __init__(self, register_builtins: bool = True) -> None:
        self._specs: dict[str, StrategySpec] = {}
        if register_builtins:
            self.register(
                "sliding_window",
                lambda params, _: SlidingWindowChunker(params),
                params_model=SlidingWindowParams,
            )
            self.register(
                "recursive",
                lambda params, _: RecursiveChunker(params),
                params_model=RecursiveParams,
            )
            self.register(
                "semantic",
                lambda params, provider: SemanticChunker(params, provider),
                params_model=SemanticParams,
                requires_provider=True,
            )

    def register(
        self,
        name: str,
        factory: ChunkerFactory,
        *,
        params_model: type[BaseModel],
        requires_provider: bool = False,
        replace: bool = False,
    ) -> None:
        """Register ``factory`` under ``name``.

        Existing names are rejected unless ``replace=True`` is given
        explicitly; silent overwrites are not allowed.
        """
        if name in self._specs and not replace:
            raise RegistryConflictError(name)
        self._specs[name] = StrategySpec(
            name=name,
            factory=factory,
            params_model=params_model,
            requires_provider=requires_provider,
        )

    def get(self, name: str) -> StrategySpec:
        """Return the spec registered under ``name``."""
        try:
            return self._specs[name]
        except KeyError:
            raise UnregisteredStrategyError(name, self.names()) from None

    def names(self) -> list[str]:
        return list(self._specs)


class ChunkEngine:
    """Facade: ``validate``/``compile``/``execute`` plus chunker registration.

    .. code-block:: python

        engine = ChunkEngine()
        policy = Policy.from_file("novel.yaml")
        result = engine.execute(text, policy, context={...}, provider=...)
    """

    def __init__(self, registry: Registry | None = None) -> None:
        self.registry = registry if registry is not None else Registry()

    def register(
        self,
        name: str,
        factory: ChunkerFactory,
        *,
        params_model: type[BaseModel],
        requires_provider: bool = False,
        replace: bool = False,
    ) -> None:
        """Register a custom chunker: ``name -> (params, provider) -> Chunker``."""
        self.registry.register(
            name,
            factory,
            params_model=params_model,
            requires_provider=requires_provider,
            replace=replace,
        )

    @staticmethod
    def _require_policy(policy: object) -> Policy:
        if not isinstance(policy, Policy):
            raise TypeError(
                "policy must be a Policy object; load one with "
                "Policy.from_file() or Policy.from_yaml(), "
                f"got {type(policy).__name__}"
            )
        return policy

    def validate(self, policy: Policy) -> None:
        """Semantically validate ``policy`` without chunking anything."""
        self.compile(policy)

    def compile(self, policy: Policy) -> ExecutionPlan:
        """Compile ``policy`` into its Execution IR."""
        return compile_policy(self._require_policy(policy), self.registry)

    def execute(
        self,
        text: str,
        policy: Policy,
        context: Mapping[str, Any] | None = None,
        provider: SimilarityProvider | None = None,
    ) -> ChunkResult:
        """Chunk ``text`` under ``policy`` and return a :class:`ChunkResult`.

        Validation, compilation, provider checks and context resolution all
        finish before any chunking starts.
        """
        start = time.perf_counter()
        self._require_policy(policy)
        if not isinstance(text, str):
            raise TypeError(f"text must be a str, got {type(text).__name__}")
        plan = compile_policy(policy, self.registry)

        for level in plan.levels:
            if level.requires_provider and provider is None:
                raise ProviderMissingError(level.strategy)

        field_values = resolve_fields(plan, context)

        chunkers: list[Chunker] = []
        for level in plan.levels:
            spec = self.registry.get(level.strategy)
            params = spec.params_model.model_validate(level.params)
            chunkers.append(spec.factory(params, provider))

        chunks = organization.run(text, plan, chunkers, field_values)

        from . import __version__

        return ChunkResult(
            chunks=chunks,
            policy_id=plan.policy_id,
            policy_version=plan.policy_version,
            policy_hash=plan.policy_hash,
            execution_id=str(uuid.uuid4()),
            engine_version=__version__,
            execution_time_ms=(time.perf_counter() - start) * 1000.0,
        )
