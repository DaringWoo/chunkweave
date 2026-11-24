# Design

## Context

绿地仓库（仅 README、LICENSE、`.gitignore` 与需求文档 `docs/autonomous_chunking_engine_agent_prompt.md`）。需求文档规定：切块策略与组织方式解耦；只有三种策略（sliding_window、recursive、semantic）与两种组织方式（本 change 不含组织执行）；Python >= 3.11（已与用户确认）；核心依赖轻量，Semantic 的相似度能力由调用方注入。本 change 交付数据模型、配置、策略协议/Registry 与三种算法，供后续 `add-organization-and-api` 复用。

## Goals / Non-Goals

**Goals:**

- 建立 `src/chunkweave/` 包骨架、统一 `Chunk` 模型与四组元数据表示、配置校验、序列化。
- 定义策略协议与 Registry，三种内置策略可单独实例化、单独测试。
- 三种算法的边界行为与文档要求一致（含中文/Emoji Offset、死循环免疫、超长兜底）。

**Non-Goals:**

- Flat/Hierarchical 组织执行、层级 Offset 换算、公共入口 API、Tree View（属 `add-organization-and-api`）。
- 文档站点、示例、Benchmark、CI、打包发布（属 `add-packaging-and-release`）。
- 文件解析、Embedding 模型托管、检索与向量数据库（需求文档明确排除）。

## Decisions

### 包结构与构建

采用 `src/` 布局：`chunkweave/{__init__.py, chunk.py, metadata.py, config.py, errors.py, registry.py, strategies/{base,sliding_window,recursive,semantic}.py}`。构建后端选 `hatchling`（新包常用、配置简洁）；备选 `setuptools` 被否决：配置更繁。测试 `pytest`，Lint `ruff`，类型检查 `mypy`（`strict` 适度放宽并在 pyproject 记录例外）。`requires-python = ">=3.11"`。

### Chunk 与元数据表示

`Chunk` 用 `@dataclass`：核心字段 `chunk_id`、`content`、`start_offset`、`end_offset` 即 Common 元数据；其余三组放入 `metadata: ChunkMetadata`（dataclass，含 `organization: dict`、`strategy: dict`、`custom: dict` 三个独立 dict）。选三分组 dict 而非合并为单 dict：保留四组边界、便于冲突检测与序列化。Custom 元数据在组装时 `copy.deepcopy` 进每个 Chunk，避免共享可变对象。保留字段集合由 Common 字段名、组织字段名与各策略声明的 strategy keys 的并集计算，Custom 键命中即抛 `MetadataConflictError`。

备选：`metadata` 合成单一扁平 dict —— 否决，无法区分三组来源；Pydantic 模型 —— 否决，dataclass 足够且零依赖。

### chunk_id 与 Offset

`chunk_id` 采用确定性顺序编号（结果内按输出序生成，如 `chunk-0000`）：同一输入+配置必然得到相同 id 集，满足"唯一且稳定"。备选：内容哈希 —— 否决，重叠窗口下不同父范围可能产出同 content+offset 的块（层级模式），哈希会撞 id。Offset 一律相对调用方传入文本；为层级预留：策略只产出相对输入片段的局部 Offset，组织层负责加基址换算（本 change 内基址为 0）。

### 策略协议与 Registry

策略协议用 `typing.Protocol`（结构化类型，免继承）：实例方法 `chunk(text: str) -> Sequence[Chunk]`，配置在构造时注入（如 `SlidingWindowChunker(config)`），便于各策略参数独立。Registry 保存 `name -> factory`（`Callable[[Mapping[str, Any]], Chunker]`），`create(name, config)` 实例化；自定义 Chunker 以同样形式注册。重复注册默认抛 `RegistryConflictError`，`register(..., replace=True)` 显式替换。未知名称抛 `UnregisteredStrategyError` 并附可用名列表。

备选：ABC 继承 —— 否决，Protocol 对自定义实现更友好；registry 存实例而非工厂 —— 否决，配置随实例固化则无法复用于不同参数。

### Recursive 算法

迭代+显式下推而非递归函数：当前分隔符切分 → 满足长度的片段直接产出，超长片段交给下一分隔符重切 → 最后一级（含空分隔符）按字符兜底。终止性由"每级产出严格更细或到达字符兜底"保证，另设 `max_depth` 保险。分隔符归属默认 `keep_separator="previous"`（保留并并入前块），可配 `"none"`/`"next"`。Overlap 在合并阶段实现：相邻结果块间按 `overlap` 字符从前一块尾部携带上下文，Offset 同步前移。`separator_used`/`separator_level` 写入 strategy 元数据。

备选：正则统一编译后按 `re.split` 语义处理 —— 采纳，字符串分隔符先 `re.escape` 统一走同一管线。

### Semantic 算法与 Provider 协议

Provider 协议：`score(left: str, right: str) -> float`（同步、纯函数语义），可选 `score_batch(pairs) -> list[float]` 供批处理优化；未注入抛 `ProviderMissingError`。语义单元切分复用 Recursive 机制：配置 `unit_separators`（默认句读类分隔符）将文本先切成原子单元；相邻单元算分，`score < threshold` 处成边界（`threshold ∈ [0,1]`，含义=相邻单元相似度下限）；合并后的块若超 `max_chunk_size` 再经 Recursive 兜底二次切分，`boundary_score` 记录触发边界的分数。

备选：要求 Provider 直接给 embedding、引擎内算余弦 —— 否决，把向量数学留在引擎里会引入 numpy 类依赖，且与"只定义轻量协议"冲突；语义单元用独立句子算法 —— 否决，文档禁止另设句子算法。

### 错误类型

`ChunkweaveError` 基类；`ConfigError`（含字段名与原因）、`UnregisteredStrategyError`、`RegistryConflictError`、`MetadataConflictError`、`ProviderMissingError`。不吞异常；Provider 异常原样向上传播。

## Risks / Trade-offs

- Recursive 逐级重切的边界组合（保留/归属×overlap×兜底）复杂 → 以确定性迭代算法+针对每规则的参数化测试覆盖，禁止引入第二套代码路径。
- 确定性 `chunk_id` 在层级重复覆盖下可能显得语义弱 → 可接受：组织层后续可将层级路径编入 id 规则，本 change 先固定顺序编号契约。
- Provider 协议为同步接口，远程 Provider 会阻塞 → 接受，文档要求"批量相似度"由可选 `score_batch` 缓解；异步版本留作后续。
- 深度复制 Custom 元数据有性能成本 → 仅在组装/继承时复制一次，正确性优先。

## Open Questions

- `chunk_id` 是否需要在层级模式下编码层级路径（留给 `add-organization-and-api` 决定，不影响本 change 契约）。
