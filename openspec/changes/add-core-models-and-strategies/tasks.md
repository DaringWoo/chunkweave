# Tasks

## 1. 包骨架与工具链

- [ ] 1.1 创建 `src/chunkweave/` 包结构与 `tests/` 目录，编写 `pyproject.toml`（hatchling 后端、`requires-python = ">=3.11"`、包元信息、许可证引用既有 LICENSE），验证 `pip install -e .` 成功
- [ ] 1.2 配置 pytest、ruff、mypy（规则与例外写入 pyproject），验证 `pytest`、`ruff check`、`mypy src` 在空套件下均可运行
- [ ] 1.3 定义 `errors.py` 异常层级（`ChunkweaveError` 及 `ConfigError`、`UnregisteredStrategyError`、`RegistryConflictError`、`MetadataConflictError`、`ProviderMissingError`），验证各异常可抛出且信息含上下文

## 2. 数据模型与配置

- [ ] 2.1 实现 `Chunk` dataclass（`chunk_id`、`content`、`start_offset`、`end_offset`）与 `ChunkMetadata`（`organization`/`strategy`/`custom` 三组 dict），验证 `content == text[start:end]` 语义与确定性 `chunk_id` 顺序编号的单测通过
- [ ] 2.2 实现四组元数据规则：保留字段集合计算、Custom 冲突抛 `MetadataConflictError`、Custom 深拷贝不共享可变对象，验证对应单测通过
- [ ] 2.3 实现三种策略配置与 Flat/Hierarchical 配置模型，`chunk_size<=0`、`overlap>=chunk_size` 等非法配置在构造期抛 `ConfigError`，验证校验单测通过
- [ ] 2.4 实现 Chunk 与配置的 `to_dict`/`from_dict`/JSON 序列化，验证往返等价与输出稳定性的单测通过（含中文、Emoji 内容）

## 3. 策略协议与 Registry

- [ ] 3.1 定义策略 `Protocol`（构造注入配置、`chunk(text) -> Sequence[Chunk]`）与 `Registry`（name→factory、`create(name, config)`），验证协议检查与类型标注通过 mypy
- [ ] 3.2 实现注册/获取/冲突（默认拒绝、`replace=True` 显式替换）/未注册报错行为，验证 Registry 单测覆盖四条规则且不含组织职责
- [ ] 3.3 验证自定义 Chunker 注册单测：第三方实现符合协议即可注册、按名获取、产出统一 Chunk

## 4. Sliding Window 策略

- [ ] 4.1 实现 `SlidingWindowChunker`：`overlap=0` 固定长度、正常重叠、窗口始终前进、末块截断、空文本空结果，验证上述单测全部通过
- [ ] 4.2 产出 `window_index`、`overlap_size` strategy 元数据且不设置组织字段，验证中文/Emoji 文本的 Offset 与 `content == text[start:end]` 单测通过

## 5. Recursive 策略

- [ ] 5.1 实现 `RecursiveChunker` 迭代式逐级切分：字符串与正则分隔符、优先级、超长片段下推、空分隔符字符兜底、`max_depth` 保险，验证多级/正则/无匹配/超长原子片段单测通过且无死循环
- [ ] 5.2 实现分隔符归属规则（默认 `previous`，可配 `none`/`next`）与相邻块 overlap，验证归属可还原原文与 overlap Offset 单测通过
- [ ] 5.3 产出 `separator_used`、`separator_level` strategy 元数据，验证空文本、最终段无分隔符、Unicode Offset 单测通过

## 6. Semantic 策略

- [ ] 6.1 定义 Provider 协议（`score`/`score_batch`）与 `SemanticChunker`：未注入抛 `ProviderMissingError`、Provider 异常透传，验证错误路径单测通过
- [ ] 6.2 实现语义切分：`unit_separators` 复用 Recursive 切原子单元、`score < threshold` 成边界、超 `max_chunk_size` 二次切分兜底、`boundary_score` 元数据，用确定性 Fake Provider 验证主题变化、threshold 边界、单元不足、超长兜底单测全部通过

## 7. 集成与质量门禁

- [ ] 7.1 全量运行 `pytest`（覆盖 chunk-model、chunking-strategies、strategy-registry 三份规格的全部 Scenario），统计实际用例数，全部通过
- [ ] 7.2 `ruff check` 与 `mypy src` 通过，修复真实发现的问题（禁止删测试、弱化断言或静默跳过）
