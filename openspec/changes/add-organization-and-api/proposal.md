# Proposal

## Why

核心模型与三种策略就绪后（`add-core-models-and-strategies`），需要第二层能力：把策略产出的 Chunk 按 Flat 或 Hierarchical 方式组织起来，建立父子关系、换算全局 Offset、组装四组元数据，并以统一公共 API 暴露。这是需求文档"两维度解耦可组合"模型的另一半，也是引擎可被调用的入口。

## What Changes

- 实现 **Flat** 组织：单策略配置，所有 Chunk 平级输出，不携带 `parent_id`/`level` 等无意义层级字段。
- 实现 **Hierarchical** 组织：N 层不限两层；每层独立配置策略与参数；每个父 Chunk 独立作为下一层输入范围；子块不得越过父块文本范围；父层 overlap 导致的子块重复覆盖属允许行为；Parent-Child 为两层特例而非第三种组织方式。
- 组织层职责：经 Registry 获取策略、层级执行、局部 Offset 换算为相对最初输入的全局 Offset、填充 `parent_id`/`level`/`sequence` 组织元数据；不依赖具体 Semantic Provider。
- 实现 **Metadata Assembly**：统一组装 Common、Organization、Strategy、Custom 四组；Custom 元数据按明确规则向子 Chunk 继承；元数据逻辑不散落到各算法中。
- 实现**公共 API**：Flat + 指定策略、Hierarchical + 多层配置、注册自定义 Chunker、注入 Semantic Provider、获取平铺 Chunk 集合、获取/构建 Tree View、配置与结果序列化入口。
- 边界行为：空输入、空层级、单层配置、某层无结果、不可继续细分、层级深度与末层行为均有定义。
- 不包含：文档/示例/Benchmark/CI/打包发布（属 `add-packaging-and-release`）；新增切块算法或组织方式（文档禁止）。

## Capabilities

### New Capabilities

- `chunk-organization`: Flat 与 Hierarchical 两种组织方式的执行语义、父子关系建立、全局 Offset 换算、组织元数据填充与四组元数据组装（含 Custom 继承规则）。
- `chunking-api`: 面向调用方的公共入口：两种组织方式的执行入口、自定义 Chunker 注册、Provider 注入、平铺结果与 Tree View 获取、序列化入口。

### Modified Capabilities

（无——`chunk-model`/`chunking-strategies`/`strategy-registry` 的行为契约不变，本 change 在其上新增能力。）

## Impact

- 新增组织层与公共 API 模块；复用既有 Registry、策略协议与 `Chunk` 模型。
- 依赖：前置 change `add-core-models-and-strategies` 的代码落地（实施顺序即提案顺序）。
- 对外影响：形成可用库形态；仍不发布 PyPI、不建远端 Release。
- 依据文档：`docs/autonomous_chunking_engine_agent_prompt.md` 第 2.1、3、4、5 节。
