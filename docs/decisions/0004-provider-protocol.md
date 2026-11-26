# ADR 0004: SimilarityProvider protocol

**Status:** partially superseded by 0011 · **Date:** 2026-11-25

> `score`/`score_batch` 协议仍然有效；注入方式（`set_provider`）已由
> ADR 0011 的按次 `provider=` 注入与 `requires_provider` 声明替代。

## Context

Semantic chunking needs similarity between adjacent units without binding a
vendor or forcing model downloads. The requirement: a light injected
protocol, no large-model dependency in core.

## Decision

A `typing.Protocol`:

```python
def score(self, left: str, right: str) -> float  # [0,1], higher = more similar
def score_batch(self, pairs) -> list[float]      # optional
```

The engine calls `score_batch` when present, else pairwise `score`. The
provider is injected via `set_provider()` or per-call `provider=`; it is
never serialized and never raises silently — missing provider raises
`ProviderMissingError`, provider exceptions propagate.

Rejected: provider returns embeddings and the engine computes cosine — pulls
vector math (numpy-class deps) into core and contradicts "light protocol".

## Consequences

- Core stays dependency-free; a provider is ~3 lines for tests.
- Synchronous contract; remote providers block the caller — accepted for v1,
  `score_batch` mitigates round trips.
- Pairwise comparison cannot see gradual topic drift; accumulating context
  is a documented future option.
