# Implementation Report — chunkweave 0.1.0（Policy 驱动架构）

All numbers below come from actual runs on 2026-11-26; the HTTP
service section and its test counts from 2026-11-27 (Python 3.13.16,
Windows-10-10.0.19045-SP0, Intel64 Family 6 Model 158 Stepping 10).

## 1. Directory layout

```
chunkweave/
├── pyproject.toml              # hatchling, requires-python >=3.11, MIT
├── LICENSE / README.md
├── src/chunkweave/             # 9 modules, flat layout
│   ├── __init__.py             # public exports + __version__
│   ├── models.py               # exceptions, ChunkSpan, Chunk, ChunkResult
│   ├── strategies.py           # protocols, params models, 3 chunkers
│   ├── policy.py               # Policy model + YAML/dict loading
│   ├── compiler.py             # ExecutionPlan IR + policy_hash
│   ├── metadata.py             # Metadata Builder (resolve + build)
│   ├── organization.py         # Runtime: per-parent descent, ordering
│   ├── engine.py               # Registry/StrategySpec + ChunkEngine
│   └── server.py               # optional HTTP service (create_app, POST /api/v1/chunks)
├── tests/                      # 13 test files, 304 tests
├── examples/                   # 11 runnable examples + policies/*.yaml
├── benchmarks/                 # bench.py + fingerprint.py + results.json
├── docs/                       # design, configuration, metadata, migration,
│   ├── algorithms/             #   sliding-window, recursive, semantic
│   ├── organization/           #   pipeline-levels.md
│   ├── http-service.md         #   HTTP API reference (optional extra)
│   └── decisions/              #   12 ADRs (0004–0006 superseded/partial)
├── .github/workflows/ci.yml
└── openspec/                   # change management
```

## 2. Public API

- `Policy.from_file(path)` / `Policy.from_yaml(text)` /
  `Policy.from_dict(data)` — safe loading, strict unknown-field
  rejection, `PolicyLoadError`/`PolicyValidationError`.
- `ChunkEngine()` — `validate(policy)`, `compile(policy) -> ExecutionPlan`,
  `execute(text, policy, context=None, provider=None) -> ChunkResult`,
  `register(name, factory, *, params_model, requires_provider=False,
  replace=False)`.
- `Chunk` — system fields (`chunk_id`, `content`, `parent_id`, `level`,
  `sequence`, `start_offset`, `end_offset`) + `strategy` +
  `strategy_metadata` + `metadata`.
- `ChunkResult` — `chunks` + traceability (`policy_id`, `policy_version`,
  `policy_hash`, `execution_id`, `engine_version`, `execution_time_ms`)
  + computed `total` in serialization.
- `ExecutionPlan` — serializable Execution IR; `model_dump_json()`
  round-trips, contains no runtime objects.
- Exceptions — `ChunkweaveError`, `PolicyLoadError`,
  `PolicyValidationError`, `UnregisteredStrategyError`,
  `RegistryConflictError`, `ProviderMissingError`,
  `ContextResolutionError`.

## 3. Architecture

`YAML Policy → Compiler → Execution IR → Runtime → ChunkResult`.
Strategies produce `ChunkSpan` (local offsets + `strategy_metadata`);
Runtime (organization.py) descends per parent chunk, converts local
offsets to global, assigns BFS `chunk-NNNN` ids, drops empty spans, and
sorts by `(start_offset, level)`. Metadata Builder resolves `source`
fields from Context before any chunking and attaches per-chunk deep
copies plus include-gated reserved-key copies. Policy Hash =
`sha256:` + canonicalized `policy.model_dump(mode="json")`.

## 4. Verification

| Check | Result |
| --- | --- |
| `pytest -q` | **304 passed** in ~1.1 s |
| `ruff check .` | **All checks passed** |
| `mypy src` | **Success: no issues found in 9 source files** |
| `examples/*.py` | **11/11 run OK** |
| `benchmarks/fingerprint.py` | digest `d2604841…b3422`, counts 9/12/21/24 |
| `python -m build --no-isolation` | wheel + sdist built |
| `twine check` | PASSED (see §6) |
| `openspec validate --all --strict` | 9 passed, 0 failed |

## 5. Benchmark

`python benchmarks/bench.py` — seed 20261125, input 10,515 code points,
40 paragraphs; repeat=5, number=20 (best-of) + median. Old = the
pre-refactor engine at the same seed/input/params, new = current
`execute`.

| workload | chunks (old = new) | old best | new best | ratio |
| --- | --- | --- | --- | --- |
| single_level sliding_window (500/50) | 24 | 0.054 ms | 0.368 ms | ~6.8× |
| single_level recursive (500) | 32 | 0.123 ms | 0.522 ms | ~4.2× |
| single_level semantic (thr 0.6) | 79 | 1.048 ms | 1.907 ms | ~1.8× |
| two_level recursive(800) → sliding(200) | 72 | 0.421 ms | 1.137 ms | ~2.7× |

Raw numbers: `benchmarks/results.json`. Chunk counts are identical
across all workloads; old values from the committed
`git show HEAD~:benchmarks/results.json`.

## 6. Build & install

- `python -m build --no-isolation --outdir %TEMP%\cw-build` →
  `chunkweave-0.1.0.tar.gz` + `chunkweave-0.1.0-py3-none-any.whl`.
- `twine check %TEMP%\cw-build\*` → PASSED for both artifacts.
- Clean-venv smoke: `pip install <wheel>` pulls only `pydantic` and
  `PyYAML` (plus pydantic's own `annotated-types`/`pydantic-core`/
  `typing-inspection` deps); `import chunkweave` prints `0.1.0`;
  a single-level `execute` runs correctly.

## 7. Known limitations

- **Slower than the old implementation (~2–7× per call)** — every
  `execute` compiles the Policy, validates params via Pydantic, and
  deep-copies per-chunk `metadata`; see §5 for measured numbers.
- **Q8 (semantic model identity) not implemented** — the Provider
  protocol has no channel for model id/version/params; deferred to a
  future change.
- **HTTP Service** — implemented as the optional `chunkweave[server]`
  extra (`src/chunkweave/server.py` → `create_app`,
  `POST /api/v1/chunks`); 25 tests in `tests/test_server.py` cover
  SDK-equivalence, request validation, error mapping (422/413/500)
  and internal-error redaction. `policy_ref`, authentication, policy
  management and streaming remain out of scope.
- **Isolated build depends on the local pip mirror** — the configured
  index lacks `hatchling`; `python -m build` only works with
  `--no-isolation` (or a full pypi.org index).
- `chunk_id` is positional, not content-addressable; deep hierarchies
  copy `parent.content` per child.
- Provider protocol is synchronous; remote providers block the caller.

## 8. Develop

```bash
pip install -e .[dev]   # or install dist/*.whl
pytest -q && ruff check . && mypy src
python -m build --no-isolation && twine check dist/*
python benchmarks/bench.py
```
