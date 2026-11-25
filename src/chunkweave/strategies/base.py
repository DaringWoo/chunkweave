"""Strategy and similarity-provider protocols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Protocol, runtime_checkable

from ..chunk import Chunk


@runtime_checkable
class Chunker(Protocol):
    """A text chunking strategy.

    Implementations receive their configuration at construction time and
    produce :class:`Chunk` results plus their declared strategy metadata.
    They MUST NOT set organization fields (``parent_id``, ``level``,
    ``sequence``); that is the organization layer's job.
    """

    metadata_keys: ClassVar[frozenset[str]]
    """Strategy metadata keys this chunker may produce."""

    def chunk(self, text: str) -> Sequence[Chunk]:
        """Split ``text`` and return chunks in stable input order."""
        ...


class SimilarityProvider(Protocol):
    """Injected similarity computation for semantic chunking.

    ``score(left, right)`` returns a similarity in ``[0, 1]`` for two
    adjacent semantic units; higher means more similar. Implementations are
    synchronous and side-effect free. ``score_batch`` is an optional batch
    optimization; the engine falls back to per-pair ``score`` calls.
    """

    def score(self, left: str, right: str) -> float:
        """Similarity of two adjacent units in ``[0, 1]``."""
        ...


@runtime_checkable
class ProviderAware(Protocol):
    """A chunker that accepts an injected similarity provider."""

    def set_provider(self, provider: SimilarityProvider) -> None:
        """Inject the similarity provider used by ``chunk``."""
        ...
