"""Public API entry point: ChunkEngine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import EngineConfig, FlatConfig, HierarchicalConfig, engine_config_from_dict
from .errors import ConfigError
from .organization.flat import FlatOrganization
from .organization.hierarchical import HierarchicalOrganization
from .registry import Registry, default_registry
from .strategies.base import SimilarityProvider
from .tree import ChunkResult


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
        call_provider = provider or self._provider
        if isinstance(config, Mapping):
            raw = dict(config)
            call_provider = raw.pop("provider", None) or call_provider
            cfg = engine_config_from_dict(raw)
        elif isinstance(config, FlatConfig | HierarchicalConfig):
            cfg = config
        else:
            raise ConfigError(
                "config", f"expected a config dict or config object, got {config!r}"
            )

        organization: FlatOrganization | HierarchicalOrganization
        if isinstance(cfg, FlatConfig):
            organization = FlatOrganization(self.registry, call_provider)
        else:
            organization = HierarchicalOrganization(self.registry, call_provider)
        chunks = organization.run(text, cfg)  # type: ignore[arg-type]
        return ChunkResult(chunks)
