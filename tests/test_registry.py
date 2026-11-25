"""Registry: builtins, custom chunkers, conflicts, boundary."""

from collections.abc import Sequence
from typing import ClassVar

import pytest

from chunkweave import (
    Chunk,
    RegistryConflictError,
    UnregisteredStrategyError,
    default_registry,
)
from chunkweave.strategies import (
    Chunker,
    RecursiveChunker,
    SemanticChunker,
    SlidingWindowChunker,
)


def test_builtin_strategies_registered():
    reg = default_registry()
    assert set(reg.names()) == {"sliding_window", "recursive", "semantic"}
    assert isinstance(reg.create("sliding_window", {"chunk_size": 4}), SlidingWindowChunker)
    assert isinstance(reg.create("recursive", {"chunk_size": 4}), RecursiveChunker)
    assert isinstance(reg.create("semantic", {"threshold": 0.5, "chunk_size": 4}), SemanticChunker)


def test_unregistered_name_raises_with_name():
    reg = default_registry()
    with pytest.raises(UnregisteredStrategyError) as exc:
        reg.create("does_not_exist")
    assert "does_not_exist" in str(exc.value)


def test_duplicate_register_rejected_and_preserved():
    reg = default_registry()
    original = reg._factories["sliding_window"]
    with pytest.raises(RegistryConflictError):
        reg.register("sliding_window", lambda cfg: original(cfg))
    assert reg._factories["sliding_window"] is original


def test_explicit_replace_wins():
    reg = default_registry()
    marker = object()

    def factory(cfg):
        return marker

    reg.register("recursive", factory, replace=True)
    assert reg.create("recursive") is marker


class ReverseChunker:
    """Third-party chunker conforming to the protocol."""

    metadata_keys: ClassVar[frozenset[str]] = frozenset({"rev"})

    def __init__(self, config):
        self.unit = config.get("unit", 5)

    def chunk(self, text: str) -> Sequence[Chunk]:
        from chunkweave.models import ChunkMetadata, chunk_id_for

        return [
            Chunk(
                chunk_id=chunk_id_for(i),
                content=text[s : s + self.unit][::-1],
                start_offset=s,
                end_offset=min(s + self.unit, len(text)),
                metadata=ChunkMetadata(strategy={"rev": i}),
            )
            for i, s in enumerate(range(0, len(text), self.unit))
        ]


def test_custom_chunker_registers_and_chunks():
    reg = default_registry()
    reg.register("reverse", lambda cfg: ReverseChunker(cfg))
    chunker = reg.create("reverse", {"unit": 3})
    chunks = chunker.chunk("abcdefg")
    assert [c.content for c in chunks] == ["cba", "fed", "g"]
    assert all(c.metadata.strategy.get("rev") is not None for c in chunks)


def test_custom_chunker_conforms_to_protocol():
    assert isinstance(ReverseChunker({}), Chunker)


def test_builtin_chunkers_conform_to_protocol():
    reg = default_registry()
    for name in reg.names():
        chunker = reg.create(name, {"chunk_size": 5, "threshold": 0.5})
        assert isinstance(chunker, Chunker)
        assert isinstance(chunker.metadata_keys, frozenset)


def test_registry_has_no_organization_duties():
    reg = default_registry()
    public = [a for a in dir(reg) if not a.startswith("_")]
    assert set(public) == {"register", "create", "names"}
