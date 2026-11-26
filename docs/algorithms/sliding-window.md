# Sliding Window

Fixed-size windows that advance by `chunk_size - overlap` code points.
`overlap = 0` is fixed-size chunking — there is no separate FixedSize
algorithm.

```yaml
pipeline:
  levels:
    - name: window
      strategy: sliding_window
      params: {chunk_size: 100, overlap: 20}
```

## Parameters

- `chunk_size` — window length in Unicode code points (> 0, required).
- `overlap` — code points shared with the previous window
  (`0 <= overlap < chunk_size`, default 0).

## Behavior

- Windows start at `0, step, 2*step, …` while `start < len(text)`; the last
  window may be shorter than `chunk_size`, and a text shorter than
  `chunk_size` yields a single chunk.
- Every window advances — no infinite loops, even at `overlap = chunk_size - 1`
  (step 1).
- Empty text yields an empty result.
- `strategy_metadata` keys: `window_index` (0-based) and `overlap_size`
  (0 on the first window, equal to `overlap` on the rest).

## Example

`chunk_size=4, overlap=2` over `"abcdefgh"`:

```
chunk-0000 [0,4) "abcd"  window_index=0 overlap_size=0
chunk-0001 [2,6) "cdef"  window_index=1 overlap_size=2
chunk-0002 [4,8) "efgh"  window_index=2 overlap_size=2
chunk-0003 [6,8) "gh"    window_index=3 overlap_size=2
```

See `examples/single_level_sliding_window.py`.
