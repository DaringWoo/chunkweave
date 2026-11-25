# Implementation Report — chunkweave 0.1.0

All numbers below come from actual runs on 2026-11-25 (Python 3.13.16,
Windows-10-10.0.19045-SP0).

## 1. Directory layout

```
chunkweave/
├── pyproject.toml              # hatchling, requires-python >=3.11, MIT
├── LICENSE / README.md
├── src/chunkweave/             # 17 modules
│   ├── __init__.py             # public exports
│   ├── chunk.py                # Chunk + ChunkMetadata, JSON round-trip
│   ├── config.py               # strategy/org config models + serialization
│   ├── metadata.py             # reserved fields + custom attach
│   ├── assembly.py             # cross-level custom merge, conflict validation
│   ├── errors.py               # ChunkweaveError + 5 typed errors
│   ├── registry.py             # name -> chunker factory
│   ├── engine.py               # ChunkEngine facade
│   ├── tree.py                 # ChunkResult + ChunkNode tree view
│   ├── strategies/
│   │   ├── base.py             # Chunker / SimilarityProvider protocols
│   │   ├── sliding_window.py
│   │   ├── recursive.py        # leaf split + greedy merge + overlap
│   │   └── semantic.py         # provider-injected boundaries
│   └── organization/
│       ├── flat.py
│       └── hierarchical.py     # N-level descent + global offsets
├── tests/                      # 9 test files
├── examples/                   # 6 runnable examples
├── benchmarks/bench.py         # stdlib timeit, seed-pinned, JSON out
├── docs/                       # design, configuration, metadata,
│   ├── algorithms/             #   sliding-window, recursive, semantic
│   ├── organization/           #   flat, hierarchical
│   └── decisions/              #   6 ADRs
├── .github/workflows/ci.yml
└── openspec/                   # change management (3 implemented changes)
```

## 2. Modules

- `ChunkEngine`: `chunk(text, config)`, `register(name, factory, replace=)`,
  `set_provider(provider)`. Config = dict / `FlatConfig` / `HierarchicalConfig`.
- `ChunkResult`: `chunks` (flat, `start_offset`-sorted), `tree()` (rebuilt
  from `parent_id` each call), `to_json()`/`from_json()` round-trip.
- `Chunk`: `chunk_id` (deterministic `chunk-NNNN`, BFS-renumbered in
  hierarchies), `content`, `start_offset`, `end_offset`, `metadata` with
  `organization`/`strategy`/`custom` groups.

## 3. Architecture

Two decoupled dimensions: chunking strategy (`sliding_window`,
`recursive`, `semantic`) × organization (`flat`, `hierarchical`).
`Registry` maps names to factories; organization executors obtain chunkers
through it — never direct imports. Metadata assembly is centralized in
`assembly.py`/`metadata.py`, not scattered through the algorithms. Flat is
its own executor (not single-level hierarchical) so flat output stays free
of organization fields.

## 4. Algorithms and parameters

| strategy | params | metadata keys |
| --- | --- | --- |
| `sliding_window` | `chunk_size`, `overlap` (0 ≤ o < size; 0 = fixed) | `window_index`, `overlap_size` |
| `recursive` | `chunk_size`, `separators` (str/regex, priority list, `""`/exhaustion = char fallback), `overlap` ≥ 0 (clamped `prev_len-1`, no gap crossing), `keep_separator` ∈ previous/next/none, `max_depth` | `separator_used`, `separator_level` (first leaf wins on merge) |
| `semantic` | `threshold` ∈ [0,1] (`score < threshold` = boundary), `chunk_size`, `unit_separators` | `boundary_score` (null on first chunk and fallback boundaries) |

## 5. Execution

- **Flat**: single strategy call + custom attach; no org fields.
- **Hierarchical**: every level-i chunk is independently chunked by level
  i+1 (no merging parents first); child global offset = local +
  `parent.start_offset`; children ⊆ parent range; empty branches terminate;
  `parent_id`/`level`/`sequence` written; ids renumbered BFS.

## 6. Metadata example

```json
{
  "chunk_id": "chunk-0003",
  "content": "…",
  "start_offset": 16, "end_offset": 30,
  "metadata": {
    "organization": {"parent_id": "chunk-0001", "level": 1, "sequence": 0},
    "strategy": {"window_index": 0, "overlap_size": 0},
    "custom": {"doc_id": "d1"}
  }
}
```

## 7. Tests

- Command: `pytest -q` → **149 passed** (0 failed), ~0.5 s.
- Coverage of the spec scenarios: unified Chunk type, deterministic ids,
  Unicode (Chinese/emoji/combining) offsets, 4-group boundaries, reserved
  conflicts, JSON round-trips, per-strategy edges (empty text, oversized
  atomic fragments, empty-match regex, max_depth, overlap clamps, gaps),
  provider errors, threshold equality, fallback splitting, hierarchy
  parent/level/sequence, global offsets, branch termination, custom
  inheritance, custom chunker at any level, tree/serialization.

## 8. Lint & types

- `ruff check .` → **All checks passed** (E, F, I, UP, B, SIM, RUF).
- `mypy src` (strict) → **no issues, 17 source files**.

## 9. Build

- `python -m build` → `dist/chunkweave-0.1.0-py3-none-any.whl` +
  `chunkweave-0.1.0.tar.gz`; `twine check dist/*` → **PASSED** (both).
- Wheel: 17 modules + `METADATA` + `licenses/LICENSE`; sdist: 34 files +
  `LICENSE` + `PKG-INFO`.
- Fresh venv smoke test: `pip install <wheel>` → `import chunkweave` OK,
  `pip show` (version 0.1.0, author daringwoo, license MIT), example ran,
  environment had only chunkweave + pip — zero runtime dependencies.

## 10. Examples

`python examples/*.py` — all 6 run offline:

1. `flat_sliding_window.py` — 6 chunks from a pangram text
2. `flat_recursive.py` — literal separators + regex chapter split
   (`keep_separator="next"` splits exactly at 第一章/第二章)
3. `flat_semantic.py` — FakeProvider splits fruit vs. calculus topics
4. `hierarchical_recursive_sliding.py` — 2 levels, tree view printed
5. `hierarchical_recursive_semantic_sliding.py` — 3 levels, boundary scores
6. `custom_chunker.py` — registered `WordChunker` at level 0 + sliding at 1

## 11. Benchmark

`python benchmarks/bench.py` — seed 20261125, input 10,515 code points,
40 paragraphs; repeat=5, number=20 (best-of) + 5 single repeats (median).

| workload | chunks | best | median |
| --- | --- | --- | --- |
| flat + sliding_window (500/50) | 24 | 0.053 ms | 0.057 ms |
| flat + recursive (500) | 32 | 0.121 ms | 0.126 ms |
| flat + semantic (thr 0.6, hash-free provider) | 79 | 1.021 ms | 1.022 ms |
| hierarchical recursive(800) → sliding(200) | 72 | 0.364 ms | 0.356 ms |

Raw numbers: `benchmarks/results.json`.

## 12. Known limitations / not done

- Pairwise semantic scoring is insensitive to gradual topic drift (block-
  level accumulation is a future option, documented in ADR 0004).
- Provider protocol is synchronous; remote providers block (partially
  mitigated by `score_batch`).
- `chunk_id` is positional, not content-addressable.
- `parent.content` substring copies amplify memory on deep hierarchies.
- `semantic` extra is declared but intentionally empty (adapter packages
  live outside core).

## 13. Install & develop

```bash
pip install -e .[dev]   # or install dist/*.whl
pytest -q && ruff check . && mypy src
python -m build && twine check dist/*
python benchmarks/bench.py
```

Custom chunker: implement `metadata_keys` + `chunk(text)`, then
`engine.register("name", lambda cfg: MyChunker(cfg))`. Provider: implement
`score(left, right)` (+ optional `score_batch`), `engine.set_provider(p)`.

## 14. Follow-ups

- Async provider protocol; block-level semantic context; benchmark on
  multi-MB inputs; optional `score_batch` chunking of pair lists; stricter
  provider output validation ([0,1] clamping or warning).

## Acceptance checklist (vs. requirement doc §12)

- [x] Flat usable; Hierarchical N levels; parent-child is 2-level case
- [x] sliding_window incl. overlap=0 ≡ fixed size
- [x] recursive: multi-level separators, regex, length limits, keep rules,
  overlap, fallbacks, no infinite loops
- [x] semantic: injected provider, no model dependency, length fallback
- [x] per-level strategy config; 4-group metadata; global offsets
- [x] custom chunker registration; stable serialization
- [x] light core deps (zero); unit+integration tests pass; ruff + mypy pass
- [x] examples runnable; docs match API; wheel+sdist built; CI configured
- [x] no fabricated test or benchmark results
