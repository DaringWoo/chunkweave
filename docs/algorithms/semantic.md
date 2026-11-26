# Semantic

Splits text where the similarity between adjacent semantic units drops
below `threshold`. Similarity comes from an injected provider — the core
package has no model dependency.

```yaml
pipeline:
  levels:
    - name: topic
      strategy: semantic
      params:
        threshold: 0.7
        chunk_size: 500
        unit_separators: ["\n\n", "\n", "。", "！", "？"]
```

```python
result = engine.execute(text, policy, provider=MyProvider())
```

## Provider protocol

```python
class MyProvider:
    def score(self, left: str, right: str) -> float:
        """Similarity of two adjacent units in [0, 1]; higher = more similar."""
        ...
    # optional batch optimization:
    def score_batch(self, pairs: list[tuple[str, str]]) -> list[float]: ...
```

- Providers are synchronous and side-effect free; engine calls
  `score_batch` when available, else `score` per pair.
- Missing provider raises `ProviderMissingError`; provider exceptions
  propagate unchanged.
- The provider never appears in serialized configs or results. Temporary
  vectors a provider computes internally are not retrieval vectors — the
  engine stores none.

## Units and boundaries

Text is split into semantic units at every `unit_separators` level
(separator text attached to the previous unit, full coverage, no merging,
no `chunk_size` constraint). Adjacent units are scored pairwise; a score
`< threshold` opens a boundary (`score == threshold` does not). Higher
`threshold` splits more aggressively. Fewer than two units means no scoring
and a single block.

## Length fallback

A semantic block longer than `chunk_size` is re-split through the recursive
mechanism over `unit_separators` (with code-point fallback), so no emitted
chunk ever exceeds `chunk_size`.

## strategy_metadata

`boundary_score` — the score that opened the boundary at this chunk's start;
`null` for the first chunk of the result and for boundaries produced by the
length fallback.

See `examples/single_level_semantic.py`.
