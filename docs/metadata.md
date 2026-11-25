# Metadata model

Every `Chunk` carries four disjoint metadata groups:

```
Metadata = Common + Organization + Strategy + Custom
```

## Common

Fields on `Chunk` itself: `chunk_id`, `content`, `start_offset`,
`end_offset`. `chunk_id` is a deterministic sequence id (`chunk-0000`, …)
unique within one result set; hierarchical runs renumber breadth-first.

## Organization

Written only by organization executors, into `chunk.metadata.organization`:

- `parent_id` — parent chunk id, `None` at level 0
- `level` — 0-based level index
- `sequence` — 0-based index within the parent's children

Flat output leaves `organization` empty — no meaningless hierarchy fields.

## Strategy

Into `chunk.metadata.strategy`; every strategy declares its keys via
`metadata_keys`:

| strategy | keys |
| --- | --- |
| `sliding_window` | `window_index` (0-based), `overlap_size` (0 on the first window, `overlap` after) |
| `recursive` | `separator_used` (literal, regex source, `""` for char fallback, `null` if unsplit), `separator_level` (index into `separators`; merged chunks keep their first leaf's values) |
| `semantic` | `boundary_score` (score that opened this chunk's start boundary; `null` on the first chunk and on fallback boundaries) |

## Custom

Caller-supplied, into `chunk.metadata.custom`. Rules:

- Preserved as-is; the engine never interprets it.
- Engine-level `custom` propagates to every descendant.
- Level `metadata` lands on that level's chunks and is inherited by
  descendants; on key conflicts the nearer level wins, and level metadata
  overrides the engine-level custom.
- Each chunk holds an independent deep copy — mutating one chunk's custom
  metadata never affects another.
- Values must be JSON-serializable; reserved-key collisions raise
  `MetadataConflictError` at config time.

**Reserved fields** = common field names ∪ `{"parent_id","level","sequence"}`
∪ the producing strategy's `metadata_keys`.

## Example

```json
{
  "chunk_id": "chunk-0007",
  "content": "…",
  "start_offset": 112,
  "end_offset": 160,
  "metadata": {
    "organization": {"parent_id": "chunk-0001", "level": 1, "sequence": 2},
    "strategy": {"window_index": 2, "overlap_size": 8},
    "custom": {"doc_id": "d1", "kind": "chapter"}
  }
}
```
