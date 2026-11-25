# chunking-api Specification

## Purpose
定义引擎面向调用方的公共入口行为：两种组织方式的执行入口、自定义 Chunker 注册、Semantic Provider 注入、结果视图与序列化入口。

## Requirements

### Requirement: 统一公共入口

引擎 MUST 提供统一公共 API 入口，调用方经该入口完成全部能力：Flat/Hierarchical 执行、注册自定义 Chunker、注入 Semantic Provider、获取结果与序列化。API 命名 MUST 一致且与 README 文档一致。

#### Scenario: 单一入口完成组合调用

- **WHEN** 调用方通过公共入口依次配置并执行 Flat 与 Hierarchical
- **THEN** 无需实例化内部模块即可完成，返回统一 Chunk 结果

### Requirement: 执行入口

公共 API MUST 支持：Flat + 指定策略配置的一次性执行；Hierarchical + 多层策略配置的一次性执行。未注册策略名或未注入 Provider 的 Semantic 执行 MUST 透出清晰异常。

#### Scenario: Flat 一键执行

- **WHEN** 调用方以 `organization=flat` 与 `strategy=sliding_window` 及参数执行
- **THEN** 返回平铺 Chunk 集合，过程无需感知 Registry 细节

#### Scenario: 层级配置执行

- **WHEN** 调用方以多层 `levels` 配置执行 Hierarchical
- **THEN** 按层产出带组织关系的完整 Chunk 集合；`levels` 中引用未注册策略时抛出清晰异常

### Requirement: 扩展入口

公共 API MUST 暴露：注册符合策略协议的自定义 Chunker（注册后即可在 Flat/Hierarchical 任意层按名引用）；注入 Semantic Provider（注入后 `semantic` 策略可用）。

#### Scenario: 自定义策略接入层级

- **WHEN** 调用方注册自定义 Chunker 并在某层 `levels` 中引用其名
- **THEN** 该层按自定义策略切块，行为与内置策略一致

### Requirement: 结果视图

公共 API MUST 支持获取平铺 Chunk 集合（按原文顺序），以及从层级结果获取/构建 Tree View（父子嵌套结构，可从根遍历到叶）。

#### Scenario: 平铺集合

- **WHEN** 调用方请求任一组织方式的结果
- **THEN** 返回按 `start_offset` 顺序排列的完整 Chunk 集合（含各层级）

#### Scenario: Tree View

- **WHEN** 调用方对 Hierarchical 结果请求 Tree View
- **THEN** 获得以根节点为起点的嵌套结构，可逐级访问子节点且与 `parent_id` 关系一致

### Requirement: 序列化入口

公共 API MUST 支持配置与结果的序列化/反序列化，输出 JSON 兼容结构且往返等价；对相同输入序列化输出稳定。

#### Scenario: 结果序列化往返

- **WHEN** 将 Hierarchical 结果序列化为 JSON 再恢复
- **THEN** 恢复的 Chunk 集合在内容、Offset、组织关系与元数据上等价，Tree View 可重建
