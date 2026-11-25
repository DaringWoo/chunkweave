"""Semantic strategy: provider protocol, boundaries, length fallback."""

import itertools

import pytest

from chunkweave import ProviderMissingError, SemanticConfig
from chunkweave.strategies import SemanticChunker


class FakeProvider:
    """Deterministic provider keyed on (left, right) unit text pairs."""

    def __init__(self, scores=None, default=1.0):
        self.scores = dict(scores or {})
        self.default = default
        self.calls = []

    def score(self, left: str, right: str) -> float:
        self.calls.append((left, right))
        return self.scores.get((left, right), self.default)


class BatchProvider(FakeProvider):
    def score_batch(self, pairs):
        self.batch_used = True
        return [self.score(left, right) for left, right in pairs]


def make(provider, threshold=0.5, chunk_size=8, **kwargs):
    return SemanticChunker(
        SemanticConfig(threshold=threshold, chunk_size=chunk_size, **kwargs),
        provider=provider,
    )


def scores_of(chunks):
    return [c.metadata.strategy["boundary_score"] for c in chunks]


# ---- 6.1 provider protocol ----


def test_missing_provider_raises():
    chunker = SemanticChunker(SemanticConfig(threshold=0.5, chunk_size=8))
    with pytest.raises(ProviderMissingError):
        chunker.chunk("a。b。")


def test_set_provider_then_chunk():
    chunker = SemanticChunker(SemanticConfig(threshold=0.5, chunk_size=8))
    chunker.set_provider(FakeProvider())
    assert chunker.chunk("a。b。")


def test_provider_exception_propagates():
    class BadProvider:
        def score(self, left, right):
            raise ValueError("embedding service down")

    with pytest.raises(ValueError, match="embedding service down"):
        make(BadProvider()).chunk("a。b。c。")


def test_score_batch_used_when_available():
    provider = BatchProvider()
    make(provider).chunk("a。b。c。")
    assert provider.batch_used
    assert provider.calls  # still records each pair


# ---- 6.2 boundaries ----


def test_topic_change_creates_boundary():
    provider = FakeProvider({("苹果。", "香蕉。"): 0.1})
    chunks = make(provider).chunk("苹果。香蕉。")
    assert len(chunks) == 2
    assert [c.content for c in chunks] == ["苹果。", "香蕉。"]
    assert scores_of(chunks) == [None, 0.1]


def test_threshold_equal_score_not_cut():
    provider = FakeProvider(default=0.5)
    chunks = make(provider, threshold=0.5).chunk("a。b。c。")
    assert len(chunks) == 1  # score == threshold -> no boundary


def test_all_similar_single_block():
    provider = FakeProvider(default=0.9)
    chunks = make(provider, chunk_size=100).chunk("a。b。c。")
    assert len(chunks) == 1
    assert scores_of(chunks) == [None]


def test_mixed_boundaries():
    text = "A。B。C。"
    provider = FakeProvider({("A。", "B。"): 0.1, ("B。", "C。"): 0.9})
    chunks = make(provider).chunk(text)
    assert [c.content for c in chunks] == ["A。", "B。C。"]
    assert scores_of(chunks) == [None, 0.1]


def test_oversized_block_fallback_splits():
    provider = FakeProvider(default=1.0)  # no semantic boundaries
    chunks = make(provider, chunk_size=8, unit_separators=["。"]).chunk(
        "a。b。c。d。e。"
    )
    assert [c.content for c in chunks] == ["a。b。c。d。", "e。"]
    assert all(c.end_offset - c.start_offset <= 8 for c in chunks)
    assert scores_of(chunks) == [None, None]


def test_fallback_keeps_semantic_score_on_first_subchunk():
    text = "x。y。" + "z" * 10
    provider = FakeProvider({("x。", "y。"): 0.1}, default=0.9)
    chunks = make(provider, chunk_size=8, unit_separators=["。"]).chunk(text)
    # blocks: [0,2) boundary 0.1, [2,14) too long -> fallback split
    assert [c.start_offset for c in chunks] == [0, 2, 4, 12]
    assert scores_of(chunks) == [None, 0.1, None, None]
    for c in chunks:
        assert c.content == text[c.start_offset : c.end_offset]
        assert c.end_offset - c.start_offset <= 8


def test_single_unit_no_scoring():
    provider = FakeProvider()
    chunks = make(provider, chunk_size=100).chunk("abcdef")
    assert len(chunks) == 1
    assert provider.calls == []
    assert scores_of(chunks) == [None]


def test_single_unit_oversized_falls_back():
    provider = FakeProvider()
    chunks = make(provider, chunk_size=4, unit_separators=["。"]).chunk("abcdefgh")
    assert [c.content for c in chunks] == ["abcd", "efgh"]
    assert provider.calls == []


def test_empty_text():
    provider = FakeProvider()
    assert make(provider).chunk("") == []
    assert provider.calls == []


def test_no_organization_fields():
    provider = FakeProvider()
    for c in make(provider).chunk("a。b。"):
        assert c.metadata.organization == {}


def test_output_order_stable_and_increasing():
    provider = FakeProvider({("B。", "C。"): 0.2})
    chunks = make(provider, chunk_size=20).chunk("A。B。C。D。" + "字" * 30)
    starts = [c.start_offset for c in chunks]
    assert all(a < b for a, b in itertools.pairwise(starts))
