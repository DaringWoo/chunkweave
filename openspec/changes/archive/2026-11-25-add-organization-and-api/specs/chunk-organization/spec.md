# Spec Delta

## Purpose

定义 Flat 与 Hierarchical 两种 Chunk 组织方式的执行语义：层级执行顺序、父子关系、全局 Offset 换算、组织元数据填充与四组元数据组装规则。

## ADDED Requirements

### Requirement: Flat 组织

Flat 组织 MUST 接受单个策略配置执行切块，所有产出 Chunk 平级、互不建立父子关系；结果 MUST NOT 携带 `parent_id`、`level`、`sequence` 等无意义层级字段。

#### Scenario: Flat 平级输出

- **WHEN** 以 Flat + 任一内置策略对文本切块
- **THEN** 产出平铺 Chunk 集合，所有 Chunk 无组织字段值、按原文顺序排列

#### Scenario: Flat 可执行三种策略

- **WHEN** 分别以 `sliding_window`、`recursive`、`semantic`（已注入 Provider）执行 Flat
- **THEN** 三种策略均可正常产出平级 Chunk 集合

### Requirement: Hierarchical 多层执行

Hierarchical MUST 支持 N 层配置（不限两层），每层独立指定策略与参数；执行时上一层的每个 Chunk MUST 分别作为下一层的输入范围，禁止将上一层所有 Chunk 合并后再切下一层。Parent-Child 为两层 Hierarchical 特例，不另设组织方式。

#### Scenario: 每个父块独立下切

- **WHEN** 配置两层（如 recursive → sliding_window）执行
- **THEN** 第一层每个 Chunk 分别被第二层策略切块，子块 `parent_id` 指向其来源父块，不存在跨父块合并切分

#### Scenario: 三层不同策略

- **WHEN** 配置三层不同策略（如 recursive → semantic → sliding_window）执行
- **THEN** 按层依次下切，第三层 Chunk 的 `parent_id` 指向第二层 Chunk、`level` 为 2

### Requirement: 子块边界约束

子层 Chunk 的文本范围 MUST NOT 越过其父 Chunk 的范围。父层存在 overlap 时，不同父块的子块覆盖相同原文范围属允许行为。

#### Scenario: 子块不越父界

- **WHEN** Hierarchical 多层执行完成
- **THEN** 任一子块的 `[start_offset, end_offset)` 均包含于其父块范围内

#### Scenario: 父层 overlap 重复覆盖

- **WHEN** 父层策略带 overlap 导致相邻父块范围重叠
- **THEN** 重叠原文范围可被多个父块的子块覆盖，引擎不视为错误

### Requirement: 全局 Offset 换算

各层 Chunk 的 `start_offset`/`end_offset` MUST 最终相对于最初输入文本；子层策略产出的局部 Offset MUST 经父块基址正确换算为全局 Offset。

#### Scenario: 局部 Offset 转全局

- **WHEN** 第二层对父块 `text[1000:2000]` 切块产出局部 `[100, 300)` 的子块
- **THEN** 该子块全局 Offset 为 `[1100, 1300)`，且 `content == text[1100:1300]`

### Requirement: 组织元数据填充

组织层 MUST 填充 `parent_id`（根为 `None`）、`level`（从 0 起）、`sequence`（同一父块下从 0 起顺序编号）；策略 MUST NOT 填充这些字段。层级结果 MUST 支持按 `parent_id` 查询子块。

#### Scenario: 父子关系字段正确

- **WHEN** 三层 Hierarchical 执行完成
- **THEN** 根块 `parent_id=None`、`level=0`；每层子块 `level` 递增、`sequence` 在同一父块内从 0 连续编号，可按 `parent_id` 取得全部子块

### Requirement: 层级边界与终止行为

空输入产出空结果；`levels` 为空属非法配置；单层 Hierarchical 等价于一层执行；某层对某父块无产出时该分支自然终止；不可继续细分的 Chunk 不产生子块；最后一层产出即叶节点。任何情况下 MUST NOT 死循环。

#### Scenario: 某层无结果分支终止

- **WHEN** 某父块在下一层策略下产出空集合
- **THEN** 该父块成为叶分支，其余父块继续正常下切，整体正常结束

#### Scenario: 空 levels 拒绝

- **WHEN** Hierarchical 配置的 `levels` 为空列表
- **THEN** 配置校验阶段抛出清晰异常

### Requirement: 元数据组装

Metadata Assembly MUST 统一组装 Common、Organization、Strategy、Custom 四组元数据；Custom 元数据 MUST 按明确规则向子 Chunk 继承（调用方传入的 custom 传播至全部后代，逐层深拷贝）；元数据组装逻辑 MUST NOT 散落在各切块算法内部。

#### Scenario: Custom 继承到后代

- **WHEN** 调用方传入 custom 元数据并执行三层 Hierarchical
- **THEN** 所有层级 Chunk 均携带该 custom 副本，修改其一不影响其他

#### Scenario: 层级附加元数据

- **WHEN** 某层配置附加了自定义元数据
- **THEN** 仅该层产出的 Chunk 及其后代按继承规则携带，与保留字段冲突时仍被拒绝
