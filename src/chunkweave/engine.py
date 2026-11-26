"""Public API entry point: strategy registry and ChunkEngine."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from . import organization
from .config import (
    EngineConfig,
    FlatConfig,
    HierarchicalConfig,
    LevelConfig,
    RecursiveConfig,
    SemanticConfig,
    SlidingWindowConfig,
    engine_config_from_dict,
)
from .models import (
    ChunkResult,
    ConfigError,
    RegistryConflictError,
    UnregisteredStrategyError,
)
from .strategies import (
    LegacyChunker,
    LegacyRecursiveChunker,
    LegacySemanticChunker,
    LegacySlidingWindowChunker,
    ProviderAware,
    SimilarityProvider,
)

ChunkerFactory = Callable[[Mapping[str, Any]], LegacyChunker]


class Registry:
    """Maps strategy names to chunker factories.

    Only responsible for registration and lookup; hierarchy execution,
    parent-child relations and metadata assembly live elsewhere.
    """

    def __init__(self, register_builtins: bool = True) -> None:
        self._factories: dict[str, ChunkerFactory] = {}
        if register_builtins:
            self.register(
                "sliding_window",
                lambda cfg: LegacySlidingWindowChunker(SlidingWindowConfig.from_dict(cfg)),
            )
            self.register(
                "recursive",
                lambda cfg: LegacyRecursiveChunker(RecursiveConfig.from_dict(cfg)),
            )
            self.register(
                "semantic",
                lambda cfg: LegacySemanticChunker(SemanticConfig.from_dict(cfg)),
            )

    def register(
        self, name: str, factory: ChunkerFactory, *, replace: bool = False
    ) -> None:
        """Register ``factory`` under ``name``.

        Existing names are rejected unless ``replace=True`` is given
        explicitly; silent overwrites are not allowed.
        """
        if name in self._factories and not replace:
            raise RegistryConflictError(name)
        self._factories[name] = factory

    def create(self, name: str, config: Mapping[str, Any] | None = None) -> LegacyChunker:
        """Instantiate the strategy registered under ``name``."""
        try:
            factory = self._factories[name]
        except KeyError:
            raise UnregisteredStrategyError(name, self.names()) from None
        return factory(config or {})

    def names(self) -> list[str]:
        return list(self._factories)


def default_registry() -> Registry:
    """A registry pre-populated with the three builtin strategies."""
    return Registry()


class ChunkEngine:
    """Facade for chunking: execution, custom chunker registration,
    similarity-provider injection, result views and serialization.

    .. code-block:: python

        engine = ChunkEngine()
        engine.set_provider(my_provider)
        result = engine.chunk(text, {
            "organization": "hierarchical",
            "levels": [{"strategy": "recursive", "config": {"chunk_size": 500}}],
        })
        result.chunks   # flat list
        result.tree()   # nested view
    """

    def __init__(self, registry: Registry | None = None) -> None:
        self.registry = registry if registry is not None else default_registry()
        self._provider: SimilarityProvider | None = None

    def register(
        self,
        name: str,
        factory: Any,
        *,
        replace: bool = False,
    ) -> None:
        """Register a custom chunker factory ``name -> (config -> Chunker)``."""
        self.registry.register(name, factory, replace=replace)

    def set_provider(self, provider: SimilarityProvider) -> None:
        """Inject the similarity provider used by ``semantic`` chunking."""
        self._provider = provider

    def chunk(
        self,
        text: str,
        config: EngineConfig | Mapping[str, Any],
        *,
        provider: SimilarityProvider | None = None,
    ) -> ChunkResult:
        """Chunk ``text`` under a Flat or Hierarchical configuration.

        ``config`` accepts a :class:`FlatConfig`/:class:`HierarchicalConfig`
        or their serialized dict form; a ``"provider"`` key in the dict (or
        the ``provider`` kwarg) overrides the engine-level provider for this
        call only.
        """
        call_provider = provider if provider is not None else self._provider
        if isinstance(config, Mapping):
            raw = dict(config)
            dict_provider = raw.pop("provider", None)
            if dict_provider is not None:
                call_provider = dict_provider
            cfg = engine_config_from_dict(raw)
        elif isinstance(config, FlatConfig | HierarchicalConfig):
            cfg = config
        else:
            raise ConfigError(
                "config", f"expected a config dict or config object, got {config!r}"
            )

        # Flat is the single-level special case without organization fields.
        levels: list[LevelConfig]
        write_organization: bool
        if isinstance(cfg, FlatConfig):
            levels = [LevelConfig(strategy=cfg.strategy, config=cfg.config)]
            write_organization = False
        else:
            levels = list(cfg.levels)
            write_organization = True

        chunkers = [self.registry.create(lv.strategy, lv.config) for lv in levels]
        for chunker in chunkers:
            if call_provider is not None and isinstance(chunker, ProviderAware):
                chunker.set_provider(call_provider)

        chunks = organization.run(
            text,
            chunkers,
            cfg.custom,
            [dict(lv.metadata) for lv in levels],
            write_organization=write_organization,
        )
        return ChunkResult(chunks)
