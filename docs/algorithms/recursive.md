# Recursive

Splits text by descending separator priority, then greedily merges the
resulting leaf fragments back up to `chunk_size`. Sentence/paragraph/heading
splits are expressed as separator rules; there are no dedicated sentence or
paragraph algorithms.

```yaml
pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params:
        chunk_size: 500
        separators: ["\n\n", "\n", "。", "！", "？", "；", "，", ""]
        overlap: 0
        keep_separator: previous
        max_depth: null
```

## Splitting

A fragment longer than `chunk_size` is split by the separator at its current
priority level; pieces still too long descend to the next separator level —
never the same level twice. Leaves are fragments at most `chunk_size` long.

- Separators are `str` literals or `{value: "<pattern>", regex: true}`
  regex declarations, applied highest priority first.
- `""` in the list means code-point fallback; exhausting the list does the
  same. `separators=[]` means fallback only.
- A separator with no match pushes the fragment to the next level unchanged.
- Matches of length 0 (e.g. `x*`) are ignored — no empty pieces, no stalls.
- `max_depth` caps how deep the separator list is applied; deeper fragments
  are char-split.
- An oversized fragment with no usable separator is force-split at
  `chunk_size` code points — termination is guaranteed.

## keep_separator

| value | effect |
| --- | --- |
| `"previous"` (default) | separator text attaches to the piece before it; concatenating chunks restores the source span |
| `"next"` | separator attaches to the following piece (heading-style) |
| `"none"` | separator is dropped; adjacent chunks show uncovered gaps |

Applies equally to literals and regexes (the regex keeps its matched text).

## Merging and overlap

Leaves merge left-to-right while the combined length stays `<= chunk_size`;
a merge never spans a `"none"`-gap. With `overlap > 0`, each chunk carries
`min(overlap, prev_len - 1)` code points of the previous chunk's tail, so
`start_offset` stays strictly increasing; carry is 0 across a gap.

## strategy_metadata

- `separator_used` — the separator that produced the chunk (literal string,
  regex source, `""` for char fallback, `null` when the input never split).
- `separator_level` — its index in `separators` (levels past the list denote
  char fallback).

Merged chunks record their first leaf's separator info.

See `examples/single_level_recursive.py`.
