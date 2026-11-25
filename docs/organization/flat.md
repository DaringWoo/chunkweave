# Flat organization

One strategy, sibling-level output. No `parent_id`/`level`/`sequence`
fields are produced — the `organization` metadata group stays empty.

```python
result = engine.chunk(text, {
    "organization": "flat",
    "strategy": "recursive",
    "config": {"chunk_size": 500},
    "custom": {"doc_id": "d1"},
})
```

- Works with any strategy (`sliding_window`, `recursive`, `semantic` with an
  injected provider, or a registered custom chunker).
- `custom` metadata is attached to every chunk as an independent deep copy.
- `result.chunks` is ordered by `start_offset`; `result.tree()` returns each
  chunk as a root node.

Flat is deliberately not implemented as single-level hierarchical: the
hierarchical executor always writes organization fields, while flat output
must stay clean.
