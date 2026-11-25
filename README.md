# chunkweave

A composable Python engine for text chunking and organization. Chunking
strategy (how text is split) and organization (how chunks relate) are two
independent, decoupled dimensions you can combine freely.

- **3 strategies**: `sliding_window`, `recursive`, `semantic` (provider-injected)
- **2 organizations**: `flat`, `hierarchical` (N levels, parent-child is the
  2-level special case)
- **Unified `Chunk` model** with 4 metadata groups and global offsets
- **Zero core dependencies**; semantic similarity is injected via a protocol

> 中文概述：chunkweave 是一个可组合的文本切块与组织引擎。切块策略与组织方式
> 两个维度解耦、自由组合：三种策略（滑动窗口、递归分隔符、语义注入）×
> 两种组织（平铺、N 层层级）。统一的 Chunk 模型、四组元数据、全局 Offset，
> 核心零依赖，语义相似度由调用方注入。示例见 `examples/`，文档见 `docs/`。

## Install

```bash
pip install -e .            # from a checkout
pip install dist/chunkweave-0.1.0-py3-none-any.whl   # built wheel
```

Requires Python >= 3.11. The core install has no third-party dependencies;
semantic provider adapters are opt-in (`pip install chunkweave[semantic]`).

## Quick start

```python
from chunkweave import ChunkEngine

engine = ChunkEngine()

# Flat + sliding window
result = engine.chunk("abcdefg...", {
    "organization": "flat",
    "strategy": "sliding_window",
    "config": {"chunk_size": 100, "overlap": 20},
})
for c in result.chunks:
    print(c.chunk_id, c.start_offset, c.end_offset, repr(c.content))
```

```python
# Hierarchical: paragraphs -> fixed windows
result = engine.chunk(text, {
    "organization": "hierarchical",
    "levels": [
        {"name": "paragraph", "strategy": "recursive",
         "config": {"chunk_size": 800}},
        {"name": "window", "strategy": "sliding_window",
         "config": {"chunk_size": 200, "overlap": 20}},
    ],
    "custom": {"doc_id": "d1"},       # custom metadata, inherited downward
})
tree = result.tree()                # nested view
flat = result.chunks                # flat view, sorted by start_offset
```

```python
# Semantic with an injected provider
class MyProvider:
    def score(self, left: str, right: str) -> float: ...  # [0, 1]
    # optional: def score_batch(self, pairs): ...

engine.set_provider(MyProvider())
result = engine.chunk(text, {
    "organization": "flat",
    "strategy": "semantic",
    "config": {"threshold": 0.7, "chunk_size": 500},
})
```

```python
# Custom chunker, usable at any level
engine.register("words", lambda cfg: WordChunker(cfg))
```

## API at a glance

| Member | Purpose |
| --- | --- |
| `ChunkEngine()` | facade; optional custom `Registry` injection |
| `engine.chunk(text, config) -> ChunkResult` | run flat or hierarchical chunking |
| `engine.register(name, factory, replace=False)` | register a custom chunker |
| `engine.set_provider(provider)` | inject the similarity provider |
| `result.chunks` | flat `list[Chunk]`, sorted by `start_offset` |
| `result.tree() -> list[ChunkNode]` | nested view rebuilt from `parent_id` |
| `result.to_json()` / `ChunkResult.from_json(s)` | stable serialization round-trip |
| `Chunk` | `chunk_id`, `content`, `start_offset`, `end_offset`, `metadata` |
| `Chunk.metadata` | `.organization`, `.strategy`, `.custom` (common fields live on `Chunk`) |

Config may be a dict (as above), `FlatConfig`, or `HierarchicalConfig`;
`engine_config_from_dict()` converts the dict form. A `"provider"` key in the
dict or the `provider=` kwarg overrides the engine-level provider per call.

## Layout

```
src/chunkweave/
  chunk.py        Chunk + ChunkMetadata (4 metadata groups)
  config.py       strategy & organization config models, JSON serialization
  metadata.py     reserved fields + custom attach (deep copies, conflicts)
  assembly.py     cross-level custom merge + config-time conflict validation
  registry.py     name -> chunker factory
  strategies/     sliding_window, recursive, semantic + protocols
  organization/   flat, hierarchical executors
  tree.py         ChunkResult + ChunkNode tree view
  engine.py       ChunkEngine public API
  errors.py       exception hierarchy
tests/            149-test pytest suite
examples/         6 runnable examples
benchmarks/       reproducible timeit benchmark + results.json
docs/             design, configuration, per-algorithm and per-organization
                  docs, metadata model, ADRs
```

## Develop

```bash
pip install -e .[dev]
pytest -q          # tests
ruff check .       # lint
mypy src           # types
python -m build    # wheel + sdist
```

See `docs/` for design details and `IMPLEMENTATION_REPORT.md` for the build
report. License: MIT.
