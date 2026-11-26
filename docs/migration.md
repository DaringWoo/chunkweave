# 迁移指南：旧 API → Policy 驱动 API

本次重构为 **BREAKING CHANGE**，没有兼容层。旧 `engine.chunk()`、
`FlatConfig`/`HierarchicalConfig`、`set_provider()`、`result.tree()`、
四组元数据模型（`ChunkMetadata`）已全部移除。0.1.0 Alpha 尚未发布
PyPI，因此直接替换。

## API 映射表

| 旧 API | 新 API |
| --- | --- |
| `FlatConfig(strategy, config, custom)` | 单层 `pipeline.levels` + `metadata.fields` |
| `HierarchicalConfig(levels=[...])` | `pipeline.levels`（多层） |
| `engine.chunk(text, config)` | `engine.execute(text, policy, context=None, provider=None)` |
| `custom={...}` / level `metadata={...}` | `metadata.fields`（`value`/`source`）+ `context` |
| `engine.set_provider(p)` | `engine.execute(..., provider=p)` |
| `result.tree()` → `list[ChunkNode]` | 按 `parent_id` 自行重建层级 |
| `result.to_json()` / `from_json()` | `result.model_dump_json()` / `model_validate()` |
| `metadata_keys` 声明 | `register(..., params_model=...)` 参数 Schema 声明 |
| config dataclass（`RecursiveConfig` 等） | 参数模型（`RecursiveParams` 等，Policy `params` 同源） |
| `Chunk`/`ChunkMetadata` 四组元数据 | `Chunk` 属性 + `strategy_metadata` + `metadata` |
| `metadata.organization`/`strategy`/`custom` | `chunk` 属性、`chunk.strategy_metadata`、`chunk.metadata` |
| `ConfigError` | `PolicyLoadError`（加载阶段）/`PolicyValidationError`（校验阶段） |
| `MetadataConflictError` | 已删除：保留键在加载时由 Policy 校验拒绝 |
| `UnregisteredStrategyError` | 同名，现为 `PolicyValidationError` 子类 |

## 示例文件改名

| 旧 | 新 |
| --- | --- |
| `examples/flat_sliding_window.py` | `examples/single_level_sliding_window.py` |
| `examples/flat_recursive.py` | `examples/single_level_recursive.py` |
| `examples/flat_semantic.py` | `examples/single_level_semantic.py` |
| `examples/hierarchical_recursive_sliding.py` | `examples/two_level_recursive_sliding.py` |
| `examples/hierarchical_recursive_semantic_sliding.py` | `examples/three_level_recursive_semantic_sliding.py` |

## 前后对照

**旧（flat dict）：**

```python
engine = ChunkEngine()
engine.set_provider(MyProvider())
result = engine.chunk(text, {
    "organization": "hierarchical",
    "levels": [
        {"name": "paragraph", "strategy": "recursive",
         "config": {"chunk_size": 800}, "metadata": {"kind": "para"}},
        {"name": "window", "strategy": "sliding_window",
         "config": {"chunk_size": 200}},
    ],
    "custom": {"doc_id": "d1"},
})
for node in result.tree():
    print(node.chunk.chunk_id, [c.chunk_id for c in node.children])
```

**新（Policy + execute）：**

```python
from chunkweave import ChunkEngine, Policy

policy = Policy.from_yaml("""
api_version: chunkweave/v1
policy: {id: migrate-demo, name: 迁移示例, version: 1.0.0}
pipeline:
  levels:
    - name: paragraph
      strategy: recursive
      params: {chunk_size: 800}
    - name: window
      strategy: sliding_window
      params: {chunk_size: 200}
metadata:
  fields:
    kind: {value: para}
    doc_id: {value: d1}
""")

engine = ChunkEngine()
result = engine.execute(text, policy, provider=MyProvider())
children = {}
for c in result.chunks:
    children.setdefault(c.parent_id, []).append(c.chunk_id)
for c in result.chunks:
    if c.parent_id is None:
        print(c.chunk_id, children.get(c.chunk_id, []))
```

## 行为差异速查

- 单层（原 flat）现在也携带 `level`/`sequence` 组织属性（恒为 `0`/序
  号）；`include` 可控制它们是否复制进 `metadata`。
- `parent_id` 是唯一的层级表达方式；不再有 `tree()`/`ChunkNode`。
- Provider 按次注入（`execute(provider=...)`），引擎不再持有 Provider。
- 每层的 `metadata`/`custom` 不再有"就近覆盖"继承语义；业务元数据
  由 `metadata.fields` 统一声明，对所有层级生效。
- 未知字段一律严格拒绝（Policy 各层 + 策略 `params`）。
