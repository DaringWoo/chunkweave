# chunk-organization Specification

## Purpose
定义 `pipeline.levels` 组织方式的执行语义：单层与多层执行顺序、父子关系、全局 Offset 换算、组织字段填充与业务 Metadata 生成规则。

## Requirements

### Requirement: 多层 Pipeline 执行

`pipeline.levels` MUST 支持 1..N 层（不限两层），按声明顺序执行，每层独立指定策略与 `params`；执行时第 i 层的每个 Chunk MUST 分别作为第 i+1 层的输入范围，禁止将上一层所有 Chunk 合并后再切下一层。两层即父子组织，不另设组织方式。

#### Scenario: 每个父块独立下切

- **WHEN** `pipeline.levels` 为两层（如 recursive → sliding_window）执行
- **THEN** 第一层每个 Chunk 分别被第二层策略切块，子块 `parent_id` 指向其来源父块，不存在跨父块合并切分

#### Scenario: 三层不同策略

- **WHEN** `pipeline.levels` 为三层不同策略（如 recursive → semantic → sliding_window）执行
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

Organization MUST 为所有 Chunk（含单层）填充 `parent_id`（根为 `None`）、`level`（从 0 起）、`sequence`；`sequence` MUST 在同一父 Chunk 下从 0 连续编号，根 Chunk 之间也从 0 起连续编号；策略 MUST NOT 填充这些字段。调用方仅凭扁平 `chunks` 中的 `parent_id` MUST 能重建全部父子关系。

#### Scenario: 父子关系字段正确

- **WHEN** 三层 Pipeline 执行完成
- **THEN** 根块 `parent_id=None`、`level=0`；每层子块 `level` 递增、`sequence` 在同一父块内从 0 连续编号，仅凭扁平 `chunks` 的 `parent_id` 即可重建全部父子关系

### Requirement: 层级边界与终止行为

空输入产出空结果；`pipeline.levels` 为空属 Policy 校验错误；某层对某父块无产出时该分支自然终止；不可继续细分的 Chunk 不产生子块；最后一层产出即叶节点；默认 MUST NOT 产生空 Chunk（content 为空字符串的 Chunk）。任何情况下 MUST NOT 死循环。

#### Scenario: 某层无结果分支终止

- **WHEN** 某父块在下一层策略下产出空集合
- **THEN** 该父块成为叶分支，其余父块继续正常下切，整体正常结束

#### Scenario: 空 levels 拒绝

- **WHEN** Policy 的 `pipeline.levels` 为空列表
- **THEN** 在 Policy 校验阶段报出清晰校验错误

### Requirement: 单层 Pipeline 即平铺

`pipeline.levels` 仅含一层时，该层 MUST 产出平铺 Chunk 集合：所有 Chunk `parent_id=None`、`level=0`，`sequence` 按原文顺序从 0 连续编号；MUST NOT 再要求调用方另行选择组织方式。

#### Scenario: 单层平铺输出

- **WHEN** Policy 的 `pipeline.levels` 仅含一层并执行
- **THEN** 产出平铺 Chunk 集合，所有 Chunk `parent_id=None`、`level=0`，`sequence` 从 0 按原文顺序编号

#### Scenario: 三种内置策略均可单层执行

- **WHEN** 分别以 `sliding_window`、`recursive`、`semantic`（已注入 Provider）构造单层 Policy 执行
- **THEN** 三种策略均可正常产出平级 Chunk 集合

### Requirement: 业务 Metadata 生成

Metadata Builder MUST 对每个 Chunk 按 Policy `metadata.fields` 生成 `metadata`：声明 `value` 的字段写入固定值，声明 `source` 的字段写入 Context 路径解析到的值；所有层级的 Chunk MUST 得到相同字段集；每个 Chunk MUST 持有独立副本，修改一个 Chunk 的 `metadata` 不影响其他 Chunk。

#### Scenario: 固定值与动态值生成

- **WHEN** Policy 同时声明 `value` 字段与 `source` 字段且 Context 提供对应值
- **THEN** 每个 Chunk 的 `metadata` 包含全部声明字段及对应值

#### Scenario: 独立副本

- **WHEN** 修改某一 Chunk 的 `metadata`
- **THEN** 其他 Chunk 的 `metadata` 不受影响

### Requirement: Context 只提供值

Context MUST 只为 Policy `metadata.fields` 中 `source` 引用的路径提供值，不负责声明字段；Context 中未被 Policy 引用的键 MUST NOT 出现在任何 Chunk 的 `metadata` 中。

#### Scenario: 未引用键不写入

- **WHEN** Context 包含未被 Policy `source` 引用的键
- **THEN** 该键不出现在任何 Chunk 的 `metadata` 中

### Requirement: Context 路径缺失

`source` 引用的路径在 Context 中不存在或 `context` 为 `None` 时，`execute()` MUST 失败并报出清晰错误，错误信息 MUST 含字段名与路径；MUST NOT 返回部分结果，MUST NOT 写入 `None`。

#### Scenario: 缺失路径报错

- **WHEN** Policy 声明 `source: context.document_id` 而 Context 中不存在该路径
- **THEN** `execute()` 报错，错误信息含字段名与路径，且不返回部分结果

### Requirement: Context 值可序列化

`source` 解析到的 Context 值 MUST 为 JSON 可序列化；不可序列化时 `execute()` MUST 报出清晰错误且不返回部分结果。

#### Scenario: 不可序列化值报错

- **WHEN** `source` 引用的 Context 值不可 JSON 序列化
- **THEN** `execute()` 报错，不返回部分结果

### Requirement: Metadata 输出选项

`metadata.include` MUST 控制将保留键复制进每个 Chunk 的 `metadata`：`include.organization` 为 `true` 时 `metadata` 含 `parent_id`、`level`、`sequence`（值等于对应 Chunk 属性）与 `level_name`（所在层的 `name`），为 `false` 时不含这 4 个键；`include.strategy` 为 `true` 时 `metadata` 含 `strategy` 与 `strategy_metadata`（与对应 Chunk 属性相等的独立副本），为 `false` 时不含这 2 个键。两者缺省 `true`；Chunk 属性 MUST 始终完整保留，复制进 `metadata` 的值各 Chunk 持有独立副本。

#### Scenario: 缺省全部启用

- **WHEN** Policy 未声明 `include` 而执行
- **THEN** 每个 Chunk 的 `metadata` 含 `parent_id`、`level`、`sequence`、`level_name`、`strategy`、`strategy_metadata` 六个键，且各值与对应 Chunk 属性相等

#### Scenario: 关闭组织信息输出

- **WHEN** `include.organization` 为 `false` 执行
- **THEN** `metadata` 不含 `parent_id`、`level`、`sequence`、`level_name` 四个键

#### Scenario: 关闭策略信息输出

- **WHEN** `include.strategy` 为 `false` 执行
- **THEN** `metadata` 不含 `strategy`、`strategy_metadata` 两个键，且 Chunk 属性 `strategy_metadata` 仍保留策略信息

#### Scenario: Chunk 属性不受影响

- **WHEN** 以任意 `include` 组合执行
- **THEN** `chunk_id`、`parent_id`、`level`、`sequence`、`strategy`、`strategy_metadata` 等 Chunk 属性完整保留
