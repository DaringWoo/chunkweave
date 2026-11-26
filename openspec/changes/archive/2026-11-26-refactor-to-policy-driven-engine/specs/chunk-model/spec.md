# Spec Delta

## ADDED Requirements

### Requirement: 系统字段、策略元数据与业务元数据分离

Chunk 的系统字段 MUST 直接作为 Chunk 属性；`strategy_metadata` 属性 MUST 只含策略执行产生的信息；`metadata` MUST 只含 Policy `metadata.fields` 声明的业务字段，加上 `metadata.include` 选项启用的保留键副本。`metadata` 中的值 MUST NOT 改变任何 Chunk 属性。

#### Scenario: 三类字段边界清晰

- **WHEN** 检查任一 Chunk
- **THEN** 系统字段均为 Chunk 属性，`strategy_metadata` 属性与 `metadata` 为各自独立的映射，互不混用

#### Scenario: 保留键字段名被拒

- **WHEN** Policy `metadata.fields` 声明与保留键同名的字段
- **THEN** 加载阶段报出含字段名的校验错误（见 `policy-engine`「Metadata 字段名不得使用保留键」）

### Requirement: ChunkResult 执行结果模型

`ChunkResult` MUST 包含 `chunks`（扁平 Chunk 列表，含全部层级）、`policy_id`、`policy_version`、`policy_hash`、`execution_id`、`engine_version`、`execution_time_ms` 与 `total`；`total` MUST 等于 `len(chunks)` 且出现在序列化输出中。`ChunkResult` MUST NOT 是 Chunk 的父类。

#### Scenario: 结果字段齐备

- **WHEN** 一次 `execute()` 完成
- **THEN** 返回的 ChunkResult 含 `chunks` 与全部执行追溯字段，且 `total` 等于 `len(chunks)`

#### Scenario: total 进入序列化输出

- **WHEN** 将 ChunkResult 序列化
- **THEN** 输出中 `total` 的值等于 `len(chunks)`

### Requirement: ChunkResult 顺序

`chunks` MUST 按 `start_offset` 升序排列；`start_offset` 相同的 Chunk 中，父层 Chunk MUST 先于其子层 Chunk 出现。

#### Scenario: 顺序稳定且父先于子

- **WHEN** 多层执行后检查 `chunks` 顺序
- **THEN** `start_offset` 单调不减，且同起点的父子块中父块在前

## MODIFIED Requirements

### Requirement: 统一 Chunk 结果模型

所有切块策略与 `pipeline.levels` 各层 MUST 产出同一种 Chunk 类型，包含 `chunk_id`、`content`、`parent_id`（根 Chunk 为 `null`）、`level`（从 0 起）、`sequence`、`start_offset`、`end_offset`、`strategy`（产生该块的层所用注册策略名）、`strategy_metadata`、`metadata`。`chunk_id` 在一次执行内唯一，且对相同 text+Policy+Context 确定性生成（重复执行结果一致）。单层 Pipeline 的 Chunk 同为该类型，`parent_id=None`、`level=0`，MUST NOT 另设平铺专属模型。任何策略 MUST NOT 返回互不兼容的结果类型。

#### Scenario: 策略产出统一类型

- **WHEN** 使用任意内置策略的单层 Pipeline 对同一文本切块
- **THEN** 返回的每个结果都是同一 Chunk 类型，含全部系统字段与 `strategy_metadata`、`metadata` 映射

#### Scenario: chunk_id 唯一且稳定

- **WHEN** 以相同 text+Policy+Context 重复执行两次
- **THEN** 两次结果中 `chunk_id` 集合一致，且单次结果内无重复 `chunk_id`

#### Scenario: 单层 Chunk 字段

- **WHEN** 执行 `pipeline.levels` 仅含一层的 Policy
- **THEN** 每个 Chunk 的 `parent_id` 为 `null`、`level` 为 0，其余系统字段齐备

### Requirement: Sliding Window 配置模型

`sliding_window` 层的 `params` MUST 包含 `chunk_size`（必填，正整数）与 `overlap`（可选，默认 0，`0 <= overlap < chunk_size`）；长度均以 Unicode 码点计。

#### Scenario: 缺省 overlap 即固定长度

- **WHEN** 该层 `params` 仅提供 `chunk_size`
- **THEN** 该层参数合法，`overlap` 缺省为 0

### Requirement: Recursive 配置模型

`recursive` 层的 `params` MUST 包含 `chunk_size`（必填，正整数，为最大块长）；`separators`（可选，缺省为段落/句读分隔符序列，元素为字面量字符串或正则，空列表等价仅兜底）；`overlap`（可选，默认 0，`>= 0`）；`keep_separator`（可选，默认 `previous`，取值 `previous`/`next`/`none`）；`max_depth`（可选正整数，超出时剩余片段按字符兜底）。正则分隔符 MUST 在 `params.separators` 中以可与字面量区分的映射形式 `{value: <pattern>, regex: true}` 声明，字面量分隔符可直接写字符串。长度均以 Unicode 码点计。

#### Scenario: 缺省分隔符与归属

- **WHEN** 该层 `params` 仅提供 `chunk_size`
- **THEN** 该层参数合法，缺省 `separators`、`overlap=0`、`keep_separator="previous"` 生效

### Requirement: Semantic 配置模型

`semantic` 层的 `params` MUST 包含 `threshold`（必填，`[0,1]` 浮点数）与 `chunk_size`（必填，正整数，为最大块长）；`unit_separators`（可选，缺省为句读类分隔符）。Provider 经 `execute(provider=...)` 按次注入，MUST NOT 写入 Policy、不参与序列化。长度均以 Unicode 码点计。

#### Scenario: 缺省语义单元分隔符

- **WHEN** 该层 `params` 仅提供 `threshold` 与 `chunk_size`
- **THEN** 该层参数合法，缺省 `unit_separators` 生效

### Requirement: 配置校验快速失败

各层 `params` MUST 在 Policy 校验阶段（`validate()`、`compile()` 或 `execute()` 开始切块之前）检查合法性，非法 `params` MUST 立即报出清晰校验错误，错误信息 MUST 含层位置（索引或名称）与参数名，而非执行到中途才失败。

#### Scenario: 非法参数立即报错

- **WHEN** 某层 `params` 为 `chunk_size <= 0` 或 `overlap >= chunk_size` 等非法值
- **THEN** 在校验阶段报出含层位置与参数名的校验错误，切块未开始

#### Scenario: 组织配置非法报错

- **WHEN** Policy 的 `pipeline.levels` 为空列表
- **THEN** 在 Policy 校验阶段报出清晰校验错误

#### Scenario: 策略专属参数越界

- **WHEN** 某层 `params` 中 `recursive.overlap < 0`、`semantic.threshold` 不在 `[0,1]` 或 `keep_separator` 取值非法
- **THEN** 在校验阶段报出含层位置与参数名的校验错误，切块未开始

### Requirement: 序列化稳定性

Chunk、ChunkResult 与 Policy MUST 支持 `model_dump()`（Python dict）与 `model_dump_json()`（JSON）序列化，并能从该输出重建且语义等价。相同 text+Policy+Context 的 Chunk 序列化输出 MUST 稳定；`execution_id`、`execution_time_ms` 不在稳定性保证内。正则分隔符 MUST 以 JSON 可判别形式序列化，使字面量与正则分隔符不产生歧义、往返不丢失类型。

#### Scenario: JSON 往返等价

- **WHEN** 将执行结果 `model_dump_json()` 后再从输出重建
- **THEN** 得到的 Chunk 集合在 `content`、Offset、`parent_id` 关系与 `metadata` 上与原结果等价

#### Scenario: 含正则分隔符的配置往返

- **WHEN** 含正则分隔符 `params` 的 Policy 序列化为 JSON 再重建
- **THEN** 还原的 Policy 与原 Policy 语义等价，分隔符类型（字面量/正则）不丢失

## REMOVED Requirements

### Requirement: 元数据四组结构

**Reason**: 元数据模型改为「系统字段 + `strategy_metadata` + 业务 `metadata`」三层结构，Common/Organization/Strategy/Custom 四组划分不再存在；Flat 不再是无层级字段的独立组织方式。
**Migration**: 由本 delta「系统字段、策略元数据与业务元数据分离」承接；单层 Chunk 同样携带 `parent_id=None`、`level=0`。

### Requirement: Custom 元数据规则与组装

**Reason**: 业务 Metadata 字段改由 Policy `metadata.fields` 声明、值由 Context 提供；调用方传入的 Custom 参数与保留字段冲突检测机制整体移除。
**Migration**: 字段声明迁入 `policy-engine` 的 Metadata 字段声明规则；值来源规则迁入 `chunk-organization`「业务 Metadata 生成」「Context 只提供值」「Context 路径缺失」「Context 值可序列化」。

### Requirement: 组织配置模型

**Reason**: Flat 与 Hierarchical 两套组织配置统一为 `pipeline.levels`，不再存在独立的组织配置模型。
**Migration**: 由 `policy-engine`「Pipeline Levels 声明」承接。
