"""Flat organization: a single strategy, sibling-level output."""

from __future__ import annotations

from ..chunk import Chunk
from ..config import FlatConfig
from ..metadata import attach_custom_metadata, validate_custom_metadata
from ..registry import Registry
from ..strategies.base import Chunker, ProviderAware, SimilarityProvider


class FlatOrganization:
    """Runs one strategy over the input and returns sibling chunks.

    Produces no organization fields: the ``organization`` group stays empty.
    """

    def __init__(
        self, registry: Registry, provider: SimilarityProvider | None = None
    ) -> None:
        self.registry = registry
        self.provider = provider

    def _inject(self, chunker: Chunker) -> None:
        if self.provider is not None and isinstance(chunker, ProviderAware):
            chunker.set_provider(self.provider)

    def run(self, text: str, config: FlatConfig) -> list[Chunk]:
        if not text:
            return []
        chunker = self.registry.create(config.strategy, config.config)
        self._inject(chunker)
        # Config-time rejection: validate custom keys before executing.
        validate_custom_metadata(config.custom, chunker.metadata_keys)
        chunks = list(chunker.chunk(text))
        return attach_custom_metadata(chunks, config.custom, chunker.metadata_keys)
