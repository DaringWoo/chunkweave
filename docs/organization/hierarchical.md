# Hierarchical organization

N levels, each with its own strategy and config. Parent-Child is the
two-level special case, not a third organization type.

```python
result = engine.chunk(text, {
    "organization": "hierarchical",
    "levels": [
        {"name": "chapter",  "strategy": "recursive",
         "config": {"chunk_size": 5000},
         "metadata": {"kind": "chapter"}},
        {"name": "event",    "strategy": "semantic",
         "config": {"threshold": 0.8, "chunk_size": 1000}},
        {"name": "detail",   "strategy": "sliding_window",
         "config": {"chunk_size": 300, "overlap": 50}},
    ],
    "custom": {"doc_id": "d1"},
})
```

## Execution

1. Level 0 chunks the whole text.
2. Each level-*i* chunk is independently chunked by level *i+1*'s strategy —
   parent chunks are never merged before re-chunking.
3. Child global offsets = local offsets + `parent.start_offset`; children
   never exceed their parent's range.
4. A parent producing no children ends that branch; a chunk that cannot be
   split further simply has no children. The last level's chunks are leaves.
5. Overlapping parents may produce children covering the same text range —
   allowed.

`chunk_id` values are renumbered breadth-first; organization fields are
`parent_id` (`None` at roots), `level` (0-based) and `sequence` (0-based
within each parent). `levels=[]` is rejected at config time; empty input
yields an empty result; single-level configs are legal.

## Level metadata and inheritance

Each level's `metadata` lands on its own chunks and is inherited by
descendants; nearer levels override farther ones, and all level metadata
overrides the engine-level `custom`. Reserved-field collisions are rejected
before execution.

## Views

- `result.chunks` — flat list across all levels, sorted by `start_offset`.
- `result.tree()` — nested `ChunkNode` view rebuilt from `parent_id` each
  call; children are reachable per node, and the flat list stays the single
  source of truth.

See `examples/hierarchical_recursive_sliding.py` and
`examples/hierarchical_recursive_semantic_sliding.py`.
