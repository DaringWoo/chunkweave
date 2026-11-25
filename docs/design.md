# Design

chunkweave separates two orthogonal dimensions:

- **Chunking strategy** — how text is split: `sliding_window`, `recursive`,
  `semantic`.
- **Organization** — how chunks relate: `flat`, `hierarchical`.

Any strategy can serve under any organization, at any level of a hierarchy.

## Layers

```
caller
  └─ ChunkEngine          public facade: chunk(), register(), set_provider()
       ├─ Registry        name -> chunker factory (builtins + custom)
       ├─ Organization    FlatOrganization / HierarchicalOrganization
       │    └─ Strategy   Chunker protocol: chunk(text) -> Sequence[Chunk]
       ├─ assembly.py     four-group metadata merge + conflict validation
       └─ tree.py         ChunkResult (flat view) + ChunkNode (tree view)
```

## Contracts

- **Chunk** — `chunk_id`, `content`, `start_offset`, `end_offset`,
  `metadata: ChunkMetadata`. Offsets are Unicode code-point indexes,
  half-open `[start, end)`, and `content == text[start:end]` always holds.
- **Strategy protocol** — a class with `metadata_keys: ClassVar[frozenset[str]]`
  and `chunk(text) -> Sequence[Chunk]`. Strategies produce only split results
  and their own strategy metadata; they never set organization fields.
  Offsets are local to the text passed in; the organization layer converts
  them to global offsets.
- **Registry** — `name -> factory` (`config mapping -> Chunker`). Duplicate
  registration is rejected unless `replace=True`; unknown names raise
  `UnregisteredStrategyError` listing available names.
- **Provider protocol** — `score(left, right) -> float in [0,1]` for adjacent
  semantic units; optional `score_batch(pairs)`. Injected, never serialized.

## Hierarchical execution

Each level has its own strategy and config. Every chunk produced at level
*i* is independently chunked by level *i+1*'s strategy — parent chunks are
never merged before re-chunking. A child's global offsets equal its local
offsets plus `parent.start_offset`; children can never exceed their parent's
range. Overlapping parents may produce children covering the same text —
that is allowed. `chunk_id` values are renumbered in breadth-first order so
ids stay unique and deterministic.

## Flat is not single-level hierarchical

Flat output carries no organization fields; a hierarchical run always
writes `level`/`parent_id`/`sequence`. `FlatOrganization` therefore calls
the strategy and assembles metadata directly instead of reusing the
hierarchical path with one level.
