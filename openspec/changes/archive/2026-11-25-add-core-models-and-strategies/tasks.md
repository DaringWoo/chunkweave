# Tasks

## 1. 包骨架与工具链

- [x] 1.1 创建 `src/chunkweave/` 包结构与 `tests/` 目录，编写 `pyproject.toml`（hatchling 后端、`requires-python = ">=3.11"`、包元信息、许可证引用既有 LICENSE），验证 `pip install -e .` 成功
- [x] 1.2 配置 pytest、ruff、mypy（规则与例外写入 pyproject），验证 `pytest`、`ruff check`、`mypy src` 在空套件下均可运行
- [x] 1.3 定义 `errors.py` 异常层级（`ChunkweaveError` 及 `ConfigError`、`UnregisteredStrategyError`、`RegistryConflictError`、`MetadataConflictError`、`ProviderMissingError`），验证各异常可抛出且信息含上下文

## 2. 数据模型与配置

- [x] 2.1 实现 `Chunk` dataclass（`chunk_id`、`content`、`start_offset`、`end_offset`）与 `ChunkMetadata`（`organization`/`strategy`/`custom` 三组 dict），验证 `content == text[start:end]` 语义与 `chunk_id` 在单次切块调用产出集合内唯一且确定性生成的单测通过（含中文、Emoji、组合字符）
- [x] 2.2 实现四组元数据规则：策略 `metadata_keys: ClassVar[frozenset[str]]` 声明机制（列入策略 Protocol）、保留字段集合计算（Common 字段名 + 组织字段名 + 产生该结果集的策略声明键）、`attach_custom_metadata` 组装辅助（冲突抛 `MetadataConflictError`、逐 Chunk 独立深拷贝、返回新列表不修改入参、Custom 值限定 JSON 可序列化类型），验证对应单测通过
- [x] 2.3 实现策略配置模型：`sliding_window`（`chunk_size`/`overlap`）、`recursive`（`chunk_size`/`separators` 元素为 `str` 字面量或 `re.Pattern`/`overlap`/`keep_separator` 三态/`max_depth`）、`semantic`（`threshold`/`chunk_size`/`unit_separators`），以及 Flat/Hierarchical 配置模型（`levels` 非空）；所有长度参数按 Unicode 码点计，`chunk_size<=0`、sliding `overlap>=chunk_size`、recursive `overlap<0`、`threshold` 越界 `[0,1]`、`keep_separator` 非法值、`levels` 为空等非法配置在构造期抛 `ConfigError`，验证校验单测通过
- [x] 2.4 实现 Chunk 与配置的 `to_dict`/`from_dict`/JSON 序列化：正则分隔符序列化为 `{"value","regex"}` 标签对象、字面量分隔符反序列化兼容纯字符串、四组元数据边界保留、Provider 不参与序列化，验证往返等价与输出稳定性的单测通过（含中文、Emoji、正则分隔符内容）

## 3. 策略协议与 Registry

- [x] 3.1 定义策略 `Protocol`（`metadata_keys: ClassVar[frozenset[str]]` 声明 Strategy Metadata 键集合、构造注入配置、`chunk(text) -> Sequence[Chunk]`）与 `Registry`（name→factory、`create(name, config)`），验证协议检查与类型标注通过 mypy
- [x] 3.2 实现注册/获取/冲突（默认拒绝抛异常、`replace=True` 显式替换后按名获取返回新实现）/未注册报错行为，验证 Registry 单测覆盖全部规则且不含组织职责
- [x] 3.3 验证自定义 Chunker 注册单测：第三方实现符合协议（含 `metadata_keys` 声明）即可注册、按名获取、产出统一 Chunk

## 4. Sliding Window 策略

- [x] 4.1 实现 `SlidingWindowChunker`：`overlap=0` 固定长度、正常重叠、最大合法重叠（`overlap = chunk_size - 1`）、窗口始终前进、末块截断、空文本空结果，验证上述单测全部通过
- [x] 4.2 产出 `window_index`（从 0 起）、`overlap_size`（首个窗口为 0、其余等于 `overlap` 配置值）strategy 元数据且不设置组织字段，验证中文/Emoji 文本的 Offset 与 `content == text[start:end]` 单测通过

## 5. Recursive 策略

- [x] 5.1 实现 `RecursiveChunker` 切分阶段：`separators` 元素支持 `str` 字面量（`re.escape`）与 `re.Pattern` 正则、按优先级逐级下推、`len(text) <= chunk_size` 不切分、超长片段用下一分隔符、`""`/分隔符耗尽按码点兜底、空片段丢弃、可匹配空串的分隔符忽略空匹配、空 `separators` 列表仅兜底、`max_depth` 超限按字符兜底，验证多级/正则/无匹配/超长原子片段/空匹配正则单测通过且无死循环
- [x] 5.2 实现叶子片段贪心合并：按原文顺序累加、合并后不超 `chunk_size`、合并块 `separator_used`/`separator_level` 取首个叶子片段的分隔符，验证小片段合并与合并不超限单测通过
- [x] 5.3 实现 `keep_separator` 归属规则：`previous`（默认）/`next`/`none`（丢弃分隔符、块间允许未覆盖间隙），正则分隔符保留其匹配文本，验证归属可还原原文、间隙语义与 `content == text[start:end]` 单测通过
- [x] 5.4 实现相邻块 overlap：携带量钳制为 `min(overlap, len_i - 1)`、`start_offset` 严格递增、`keep_separator="none"` 间隙边界携带量为 0，验证 overlap 与小块钳制单测通过
- [x] 5.5 产出 `separator_used`、`separator_level`（合并块取首叶规则）strategy 元数据，验证空文本、最终段无分隔符、Unicode Offset 单测通过

## 6. Semantic 策略

- [x] 6.1 定义 Provider 协议（`score(left, right) -> float` 对相邻语义单元返回 `[0,1]` 相似度、可选 `score_batch`）与 `SemanticChunker`：未注入抛 `ProviderMissingError`、Provider 异常透传、Provider 不参与序列化，验证错误路径单测通过
- [x] 6.2 实现语义切分：`unit_separators` 产出语义单元叶子片段（不受 `chunk_size` 约束、不做块合并、分隔符归属前单元、覆盖全文无间隙）、相邻单元两两评分 `score < threshold` 成边界、语义块超 `chunk_size` 时以 `unit_separators` 经 Recursive 兜底二次切分、`boundary_score` 规则（语义边界记分数、兜底边界与结果首块为 `null`）、单元不足不评分，使用确定性 Fake Provider 验证主题变化、threshold 边界（含 `score == threshold` 不切）、单元不足、超长兜底、空文本单测全部通过

## 7. 集成与质量门禁

- [x] 7.1 全量运行 `pytest`（覆盖 chunk-model、chunking-strategies、strategy-registry 三份规格的全部 Scenario），统计实际用例数，全部通过
- [x] 7.2 `ruff check` 与 `mypy src` 通过，修复真实发现的问题（禁止删测试、弱化断言或静默跳过）
