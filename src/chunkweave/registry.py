"""Strategy registry: name -> factory lookup and custom chunker registration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .config import RecursiveConfig, SemanticConfig, SlidingWindowConfig
from .errors import RegistryConflictError, UnregisteredStrategyError
from .strategies.base import Chunker
from .strategies.recursive import RecursiveChunker
from .strategies.semantic import SemanticChunker
from .strategies.sliding_window import SlidingWindowChunker

ChunkerFactory = Callable[[Mapping[str, Any]], Chunker]


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
                lambda cfg: SlidingWindowChunker(SlidingWindowConfig.from_dict(cfg)),
            )
            self.register(
                "recursive",
                lambda cfg: RecursiveChunker(RecursiveConfig.from_dict(cfg)),
            )
            self.register(
                "semantic",
                lambda cfg: SemanticChunker(SemanticConfig.from_dict(cfg)),
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

    def create(self, name: str, config: Mapping[str, Any] | None = None) -> Chunker:
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
