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

`Chunk` 用 `@dataclass`：核心字段 `chunk_id`、`content`、`start_offset`、`end_offset` 即 Common 元数据；其余三组放入 `metadata: ChunkMetadata`（dataclass，含 `organization: dict`、`strategy: dict`、`custom: dict` 三个独立 dict）。选三分组 dict 而非合并为单 dict：保留四组边界、便于冲突检测与序列化。Custom 元数据经 `metadata.attach_custom_metadata(chunks, custom)` 组装：先校验保留字段冲突，再逐 Chunk `copy.deepcopy` 写入 `metadata.custom`，返回新 Chunk 列表、不修改入参；Custom 值限定 JSON 可序列化类型。保留字段集合 = Common 字段名 ∪ 组织字段名（`parent_id`/`level`/`sequence`）∪ 产生该结果集的策略声明的 `metadata_keys`，Custom 键命中即抛 `MetadataConflictError`。每个策略 MUST 以 `metadata_keys: ClassVar[frozenset[str]]` 声明其 Strategy Metadata 键名（列入策略 Protocol）；自定义 Chunker 同样必须声明，未声明的键不受冲突保护。

备选：`metadata` 合成单一扁平 dict —— 否决，无法区分三组来源；Pydantic 模型 —— 否决，dataclass 足够且零依赖。

### chunk_id 与 Offset

`chunk_id` 采用确定性顺序编号（单次 `chunk()` 调用产出内按输出序生成，如 `chunk-0000`）：同一输入+配置必然得到相同 id 集，满足"唯一且稳定"。备选：内容哈希 —— 否决，重叠窗口下不同父范围可能产出同 content+offset 的块（层级模式），哈希会撞 id。Offset 一律相对调用方传入文本；为层级预留：策略只产出相对输入片段的局部 Offset，组织层负责加基址换算（本 change 内基址为 0）。所有长度参数（`chunk_size`、`overlap` 等）以 Unicode 码点计，与 Offset 单位一致。

### 策略协议与 Registry

策略协议用 `typing.Protocol`（结构化类型，免继承）：类属性 `metadata_keys: ClassVar[frozenset[str]]` 声明 Strategy Metadata 键集合，实例方法 `chunk(text: str) -> Sequence[Chunk]`，配置在构造时注入（如 `SlidingWindowChunker(config)`），便于各策略参数独立。Registry 保存 `name -> factory`（`Callable[[Mapping[str, Any]], Chunker]`），`create(name, config)` 实例化；自定义 Chunker 以同样形式注册。重复注册默认抛 `RegistryConflictError`，`register(..., replace=True)` 显式替换。未知名称抛 `UnregisteredStrategyError` 并附可用名列表。

备选：ABC 继承 —— 否决，Protocol 对自定义实现更友好；registry 存实例而非工厂 —— 否决，配置随实例固化则无法复用于不同参数。

### Recursive 算法

分隔符类型：`separators` 元素为 `str`（字面量，内部 `re.escape`）或 `re.Pattern`（正则）；缺省为 `["\n\n", "\n", "。", "！", "？", "；", "，", ""]`，空列表等价仅兜底。

切分（迭代+显式下推而非递归函数）：`len(text) <= chunk_size` 的片段直接成为叶子；否则按当前分隔符切分，`<= chunk_size` 的片段成为叶子、超长片段用下一分隔符重切；分隔符耗尽或遇 `""` 时按码点切分；无任何分隔符匹配的超长原子片段按 `chunk_size` 强制切分；空片段丢弃；可匹配空串的分隔符（含正则）忽略空匹配；`max_depth`（可选正整数）超出后剩余片段按字符兜底。终止性由"每级产出严格更细或到达字符兜底"保证。

合并：全部叶子片段按原文顺序贪心合并——从左到右累加，相邻片段合并后 `<= chunk_size` 时并入当前块，否则开新块。

分隔符归属 `keep_separator`：`previous`（默认，分隔符保留并入前块）、`next`（并入后块）、`none`（丢弃，相邻块间允许未覆盖间隙，拼接还原仅对保留模式成立）。归属在切分时决定叶子片段边界，合并只拼接相邻叶子。

Overlap：合并后相邻结果块间按 `overlap` 码点从前一块尾部携带上下文，`start' = max(start_i + 1, n - min(overlap, len_i - 1))`（`n` 为该块名义起点、`len_i` 为前块长度），保证 `start_offset` 严格递增；`keep_separator="none"` 的间隙边界携带量为 0（间隙不得被携带跨越）。`separator_used`/`separator_level` 写入 strategy 元数据，合并块取首个叶子片段的分隔符信息。

### Semantic 算法与 Provider 协议

语义单元：文本先按 `unit_separators`（缺省 `["\n\n", "\n", "。", "！", "？"]`）经与 Recursive 相同的分隔符机制切分为语义单元——产出叶子片段、不受 `chunk_size` 约束、不做块合并、分隔符保留并归属前单元（单元序列覆盖全文无间隙）、空单元丢弃。

Provider 协议：`score(left: str, right: str) -> float` 对相邻两个语义单元（left 为前单元、right 为后单元）返回 `[0,1]` 相似度分数（越大越相似），同步、纯函数语义；可选 `score_batch(pairs) -> list[float]` 供批处理优化；未注入抛 `ProviderMissingError`；Provider 异常原样传播；Provider 实例不属于配置、不参与序列化。

边界与块构建：对相邻单元两两评分，`score < threshold` 处成边界（`threshold ∈ [0,1]` 必填，越大切分越激进）；语义块在边界处结束；块超过 `chunk_size`（最大块长）时以 `unit_separators` 经 Recursive 机制二次切分兜底（含字符兜底），保证无 Chunk 超限；单元本身超限同样走兜底。退化输入：不足两个语义单元时不评分，整体为单块（空文本为空结果）。

`boundary_score`：Chunk 起始边界为语义边界时记录对应分数；长度兜底产生的边界与结果首块为 `null`。

备选：要求 Provider 直接给 embedding、引擎内算余弦 —— 否决，把向量数学留在引擎里会引入 numpy 类依赖，且与"只定义轻量协议"冲突；语义单元用独立句子算法 —— 否决，文档禁止另设句子算法；块级累积上下文评分 —— 留作 Open Questions（pairwise 相邻单元是最简契约）。

### 配置字段与序列化

各策略配置字段即序列化契约：`sliding_window`（`chunk_size`、`overlap` 默认 0）、`recursive`（`chunk_size`、`separators`、`overlap` 默认 0、`keep_separator` 默认 `previous`、`max_depth` 可选）、`semantic`（`threshold` 必填、`chunk_size`、`unit_separators`）；组织配置 Flat 为单策略、Hierarchical 为非空 `levels` 列表。正则分隔符序列化为 `{"value": "<pattern>", "regex": true}` 标签对象，字面量分隔符序列化为 `{"value": "<text>", "regex": false}`；`from_dict` 同时接受纯字符串（视为字面量）与标签对象，保证 JSON 往返无损且输出稳定。

### 错误类型

`ChunkweaveError` 基类；`ConfigError`（含字段名与原因）、`UnregisteredStrategyError`、`RegistryConflictError`、`MetadataConflictError`、`ProviderMissingError`。不吞异常；Provider 异常原样向上传播。

## Risks / Trade-offs

- Recursive 逐级切分+贪心合并+overlap 的边界组合（保留/归属×间隙×overlap 钳制×兜底）复杂 → 以确定性迭代算法+针对每规则的参数化测试覆盖，禁止引入第二套代码路径；贪心合并可能跨越细粒度分隔符边界（块尽量填满 `chunk_size`），属长度约束优先的预期行为；`keep_separator="none"` 的覆盖间隙为显式取舍，文档标注。
- 确定性 `chunk_id` 在层级重复覆盖下可能显得语义弱 → 可接受：组织层后续可将层级路径编入 id 规则，本 change 先固定顺序编号契约。
- Semantic 相邻单元两两评分对渐进式主题漂移不敏感（相邻对始终相似则不切分）→ 接受为 v1 最简契约；Provider 可在 `score` 内部自实现上下文，累积比较留作后续。
- Provider 协议为同步接口，远程 Provider 会阻塞 → 接受，文档要求"批量相似度"由可选 `score_batch` 缓解；异步版本留作后续。
- 深度复制 Custom 元数据有性能成本 → 仅在组装/继承时复制一次，正确性优先。

## Open Questions

- `chunk_id` 是否需要在层级模式下编码层级路径（留给 `add-organization-and-api` 决定，不影响本 change 契约）。
- Semantic 是否需要块级/窗口级累积上下文评分（pairwise 相邻单元评分对渐变主题不敏感）——本 change 固定 pairwise 契约，留待后续评估。
