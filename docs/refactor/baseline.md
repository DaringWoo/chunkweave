# Phase 0 基线

规范层审计见 `openspec/changes/refactor-to-policy-driven-engine/audit.md`（引用，不重复）。
本文只记录代码层基线：执行命令、结果、失败分类，以及旧模块 → 目标模块映射。

## 环境

- Python 3.13.16（Windows）
- pydantic 2.14.1、PyYAML 6.0.3 已安装
- pip 默认索引（tuna 镜像）不可用：`hatchling`、`types-PyYAML` 无法解析，已用 `-i https://pypi.org/simple` 安装成功
- `python -m build` 的隔离环境因上述镜像问题失败；`--no-isolation`（hatchling 已装）可成功构建

## 基线命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m pytest -q` | 150 passed in 0.72s |
| `python -m ruff check .` | **2 errors**（见下） |
| `python -m mypy src` | Success: no issues found in 7 source files |
| `python -m build --no-isolation --outdir %TEMP%\cw-build` | 成功：`chunkweave-0.1.0.tar.gz` + `chunkweave-0.1.0-py3-none-any.whl` |
| `examples/_demo_usage.py` | exit 0 |
| `examples/custom_chunker.py` | exit 0 |
| `examples/flat_recursive.py` | exit 0 |
| `examples/flat_semantic.py` | exit 0 |
| `examples/flat_sliding_window.py` | exit 0 |
| `examples/hierarchical_recursive_semantic_sliding.py` | exit 0 |
| `examples/hierarchical_recursive_sliding.py` | exit 0 |

## 基线失败项

1. `ruff check .`：2 个 E501，均在 `examples/_demo_usage.py`（第 19 行 141 字符、第 60 行 101 字符）。该文件为用户提交的示例，属既有问题，本次重构不修。
2. `python -m build`（隔离环境）：pip 默认镜像无法安装构建依赖，属环境问题；`--no-isolation` 可用。

## 旧模块 → 目标模块映射（扁平布局，延续 448d132）

| 旧模块 | 目标模块 | 说明 |
| --- | --- | --- |
| `models.py`（异常、`Chunk`/`ChunkMetadata`/`ChunkResult`） | `models.py` | 新增 `ChunkSpan`、`PolicyLoadError`/`PolicyValidationError`/`ContextResolutionError`；`Chunk`/`ChunkResult` 字段第 2 批定型 |
| `strategies.py`（`SlidingWindow*`/`Recursive*`/`Semantic*`、`SimilarityProvider`） | `strategies.py` | 新增参数模型（`SlidingWindowParams` 等）、`SeparatorSpec`、`Chunker` 协议与同名新 Chunker；旧类改名 `Legacy*`，第 2 批删除 |
| `config.py`（`FlatConfig`/`HierarchicalConfig`/策略 dataclass） | `policy.py`（新增） | 第 1 批新建 Policy 模型；`config.py` 保留至第 2 批删除，分隔符常量移到 `strategies.py` 后由 config 导入 |
| —（编译缺失） | `compiler.py` | 第 2 批：Policy → `ExecutionPlan` |
| `metadata.py`（四组组装+Custom） | `metadata.py` | 第 2 批改为 Metadata Builder（`value`/`source` + include 复制） |
| `organization.py`（Flat/Hierarchical 下切） | `organization.py` | 第 2 批改为按 ExecutionPlan 下切的 Runtime，输出带全局 Offset 的 Chunk |
| `engine.py`（`Registry` + `ChunkEngine.chunk(config)` + `set_provider`） | `engine.py` | 第 2 批：Registry 改 Chunker 协议 + `params_model`/`requires_provider`；`ChunkEngine.execute(text, policy, context=None, provider=None)` + `register(...)` |

## 现状要点（代码层面）

- 旧公共面：`ChunkEngine.chunk(text, config)`、`FlatConfig`/`HierarchicalConfig`、引擎级 `set_provider`、Custom 元数据参数、`to_tree()`。
- 策略输出旧 `Chunk`（最终块），`metadata_keys` 声明策略元数据键。
- 四组元数据模型：Common（`Chunk` 属性）、`organization`、`strategy`、`custom`。
- 序列化：旧 `to_json`/手动 dict。
