# Design

## Context

前置 change `add-core-models-and-strategies` 已确定：`Chunk` dataclass + `ChunkMetadata`（organization/strategy/custom 三组）、策略协议 `chunk(text) -> Sequence[Chunk]`（Offset 相对入参文本、不含组织字段）、Registry（`name -> factory`）。本 change 在其上实现组织执行、元数据组装与公共入口。层级 Offset 换算依赖前置契约：策略产出的局部 Offset 加父块 `start_offset` 即得全局值。

## Goals / Non-Goals

**Goals:**

- Flat/Hierarchical 执行器、层级关系建立、全局 Offset 换算、四组元数据统一组装。
- 统一公共入口 `ChunkEngine`：执行、注册、注入、平铺结果、Tree View、序列化。

**Non-Goals:**

- 不改变策略协议、Chunk 模型或 Registry 契约（属上一 change 的规格）。
- 文档、示例、Benchmark、CI、打包（属 `add-packaging-and-release`）。

## Decisions

### 模块与执行器形态

新增 `organization/flat.py`、`organization/hierarchical.py`、`assembly.py`、`engine.py`、`tree.py`。组织执行器为独立类：`FlatOrganization`/`HierarchicalOrganization`，入参（text、EngineConfig、Registry、provider 注入面）→ `list[Chunk]`（已填组织字段）。备选：把层级逻辑写进 `ChunkEngine` —— 否决，违反"组织层独立、不依赖具体 Provider"边界。

### Hierarchical 执行与 Offset 换算

逐层下推的迭代实现：第 0 层对原文切块；第 i+1 层对每个第 i 层块分别执行：`strategy.chunk(parent.content)`，子块全局 Offset = `parent.start_offset + local`。终止性由层级数有限保证；某父块产出空集 → 该分支自然为叶。因策略契约保证 `content == input[start:end]`，递归换算后必有 `child.content == original[global_start:global_end]`，以此写性质断言测试。

备选：传原文+范围给策略而非 `parent.content` —— 否决，协议入参是文本切片，子串拷贝成本可接受且语义最简单；深拷贝父块再改 —— 否决，直接新建子块。

### 组织元数据填充

执行器在下推后统一写组织字段：`level` = 层序号（根 0）、`parent_id` = 父块 `chunk_id`（根 `None`）、`sequence` = 该子块在其父块子集中的序号（从 0）。`chunk_id` 沿用顺序编号：对整棵结果按层序遍历（BFS）统一编号，保证稳定唯一——回应上一 change 的 Open Question：id 不编码层级路径，关系信息由 `parent_id`/`level` 表达，避免两处真相。

### 元数据组装

`assembly.py` 提供单一组装函数：Common（字段）+ Organization（执行器写入）+ Strategy（策略自带）+ Custom（引擎级 custom 传播至全部后代 + 每层 `metadata` 追加，均逐层深拷贝）。层级追加语义：第 i 层配置的 `metadata` 仅作用于该层产出块，并由其所有后代继承。保留字段冲突在配置校验期即拒绝，不在组装期静默。

备选：custom 只对叶块生效 —— 否决，文档要求"向子 Chunk 继承"，全部携带更直观。

### 公共 API 形态

`ChunkEngine` 类：构造可注入 Registry（默认内置）；方法 `register(name, factory, replace=False)`、`set_provider(provider)`、`chunk(config) -> ChunkResult`。`ChunkResult`：`chunks`（平铺、按 Offset 序）、`tree() -> list[ChunkNode]`、`to_dict()/to_json()`；`ChunkNode` 为轻量包装（`chunk` + `children`）。配置：`{"organization": "flat", "strategy": ..., "config": {...}, "custom": {...}}` 或 `{"organization": "hierarchical", "levels": [{"name"?, "strategy", "config", "metadata"?}], "custom": {...}}`。

备选：模块级函数 `chunk_text(...)` —— 否决，注册表与 Provider 是有状态的，门面类更内聚；Provider 放在每次调用的 config —— 否决为唯一方式：引擎级注入为主（一次注入多处用），允许调用级覆盖。

### Flat 与 Hierarchical 的关系

Flat 不走"单层 Hierarchical"捷径：Flat 输出必须无组织字段，而层级执行器总会写 `level=0`。实现上 Flat 直接调用策略+组装（跳过组织字段写入），保持输出干净。

## Risks / Trade-offs

- `parent.content` 子串拷贝：N 层深时内存放大 → 接受（文档：正确性优先；大文本优化留到 Benchmark change 评估）。
- `sequence` 在无产出父块/空分支下的取值歧义 → 定义为"同一父块的实际子集内"编号，空父块无子块即无 sequence 产生，写测试钉死。
- Tree View 与平铺集合可能漂移 → `tree()` 每次从 `parent_id` 现算，不缓存结构，保证单一真相。
- 层级 `metadata` 追加与引擎级 custom 键冲突 → 沿用保留字段规则：撞保留键拒绝；非保留键层级值覆盖引擎级（近者优先），写入文档与测试。

## Open Questions

- 无。
