# Spec Delta

## Purpose

定义 Chunk 统一结果模型、Offset 与长度单位语义、四组元数据结构、配置模型与序列化契约，是所有切块策略与组织方式共用的数据基础。

## ADDED Requirements

### Requirement: 统一 Chunk 结果模型

所有切块策略与组织方式 MUST 产出同一种 Chunk 类型，包含 `chunk_id`、`content`、`start_offset`、`end_offset`。`chunk_id` 在单次切块调用的产出集合内唯一，且对同一输入与配置确定性生成（重复执行结果一致）。任何策略 MUST NOT 返回互不兼容的结果类型。

#### Scenario: 策略产出统一类型

- **WHEN** 使用任意内置策略对同一文本切块
- **THEN** 返回的每个结果都是同一 Chunk 类型，含 `chunk_id`、`content`、`start_offset`、`end_offset`

#### Scenario: chunk_id 唯一且稳定

- **WHEN** 对同一输入与配置重复切块两次
- **THEN** 两次结果中 `chunk_id` 集合一致，且单次结果内无重复 `chunk_id`

### Requirement: Offset 与长度单位语义

`start_offset`/`end_offset` MUST 使用 Python 字符串索引语义（Unicode 码点索引），采用左闭右开区间 `[start_offset, end_offset)`，相对于本次切块调用传入的文本。所有以长度计的参数（如 `chunk_size`、`overlap`）MUST 以 Unicode 码点计。层级场景下，策略产出的局部 Offset 由组织层换算为相对最初输入文本的全局 Offset。

#### Scenario: content 与 Offset 一致

- **WHEN** 对含中文、Emoji 与组合字符的文本切块
- **THEN** 每个 Chunk 满足 `content == text[start_offset:end_offset]`，Offset 不越界

#### Scenario: 空文本 Offset

- **WHEN** 输入为空字符串
- **THEN** 不产生任何 Offset 越界的 Chunk

### Requirement: 元数据四组结构

Chunk 元数据 MUST 由四组构成：Common（`chunk_id`、`content`、`start_offset`、`end_offset` 等）、Organization（`parent_id`、`level`、`sequence`）、Strategy（由策略动态提供）、Custom（调用方传入）。MUST 只生成有真实意义的字段，Flat 组织下 MUST NOT 携带无意义的层级字段。

#### Scenario: 元数据分组边界清晰

- **WHEN** 检查任一 Chunk 的元数据
- **THEN** 每个字段可归入且仅归入四组之一，无策略之间互相冲突的同名字段

#### Scenario: 组织字段由组织层赋值

- **WHEN** 策略单独产出切块结果（未经过组织层）
- **THEN** 结果不包含 `parent_id`、`level`、`sequence` 等组织字段值

### Requirement: Custom 元数据规则与组装

调用方传入的 Custom 元数据 MUST 原样保留且不解释业务含义；与保留字段冲突时 MUST 拒绝或显式报错而非静默覆盖；不同 Chunk 之间 MUST NOT 意外共享可变字典对象。保留字段 MUST 定义为 Common 字段名、组织字段名（`parent_id`、`level`、`sequence`）与产生该结果集的策略声明的 Strategy Metadata 键名的并集。引擎 MUST 提供统一的元数据组装机制：校验冲突后将 Custom 元数据逐 Chunk 深拷贝写入 `custom` 组。Custom 元数据值 MUST 为 JSON 可序列化类型。

#### Scenario: 保留字段冲突拒绝

- **WHEN** Custom 元数据包含与 Common/Organization/Strategy 保留字段同名的键
- **THEN** 引擎抛出清晰异常而非静默覆盖

#### Scenario: 不共享可变对象

- **WHEN** 多个 Chunk 继承同一份 Custom 元数据
- **THEN** 任一 Chunk 的元数据被修改不会影响其他 Chunk

#### Scenario: Custom 元数据注入

- **WHEN** 将 Custom 元数据附加到一份切块结果
- **THEN** 每个 Chunk 的 `custom` 组包含该元数据的独立副本，修改任一 Chunk 的副本不影响其他 Chunk

### Requirement: Sliding Window 配置模型

`sliding_window` 配置 MUST 包含 `chunk_size`（必填，正整数）与 `overlap`（可选，默认 0，`0 <= overlap < chunk_size`）；长度均以 Unicode 码点计。

#### Scenario: 缺省 overlap 即固定长度

- **WHEN** 仅提供 `chunk_size` 构造 sliding_window 配置
- **THEN** 配置合法，`overlap` 缺省为 0

### Requirement: Recursive 配置模型

`recursive` 配置 MUST 包含 `chunk_size`（必填，正整数，为最大块长）；`separators`（可选，缺省为段落/句读分隔符序列，元素为字面量字符串或正则，空列表等价仅兜底）；`overlap`（可选，默认 0，`>= 0`）；`keep_separator`（可选，默认 `previous`，取值 `previous`/`next`/`none`）；`max_depth`（可选正整数，超出时剩余片段按字符兜底）。长度均以 Unicode 码点计。

#### Scenario: 缺省分隔符与归属

- **WHEN** 仅提供 `chunk_size` 构造 recursive 配置
- **THEN** 配置合法，缺省 `separators`、`overlap=0`、`keep_separator="previous"` 生效

### Requirement: Semantic 配置模型

`semantic` 配置 MUST 包含 `threshold`（必填，`[0,1]` 浮点数）与 `chunk_size`（必填，正整数，为最大块长）；`unit_separators`（可选，缺省为句读类分隔符）。Provider 经构造注入，不属于配置、不参与序列化。长度均以 Unicode 码点计。

#### Scenario: 缺省语义单元分隔符

- **WHEN** 提供 `threshold` 与 `chunk_size` 构造 semantic 配置
- **THEN** 配置合法，缺省 `unit_separators` 生效

### Requirement: 组织配置模型

Flat 配置 MUST 为单策略配置（策略名 + 参数）；Hierarchical 配置 MUST 为 `levels` 列表，每项含策略名、该层配置与可选 `name`，`levels` MUST 非空。

#### Scenario: 多层配置合法

- **WHEN** 构造含两层以上策略配置的 Hierarchical 配置
- **THEN** 配置合法，各层策略名与参数独立保存

### Requirement: 配置校验快速失败

策略配置与组织配置 MUST 在构造/校验阶段即检查合法性，非法配置 MUST 立即抛出清晰异常，而非执行到中途才失败。

#### Scenario: 非法参数立即报错

- **WHEN** 构造 `chunk_size <= 0` 或 `overlap >= chunk_size` 等非法配置
- **THEN** 在校验阶段抛出带参数信息的异常，切块未开始

#### Scenario: 组织配置非法报错

- **WHEN** Hierarchical 配置的 `levels` 为空列表
- **THEN** 在配置校验阶段抛出带参数信息的异常

#### Scenario: 策略专属参数越界

- **WHEN** `recursive.overlap < 0`、`semantic.threshold` 不在 `[0,1]` 或 `keep_separator` 取值非法
- **THEN** 在构造期抛出 `ConfigError`，切块未开始

### Requirement: 序列化稳定性

Chunk 结果与配置 MUST 支持 JSON 序列化，序列化结果 MUST 保留四组元数据边界；序列化-反序列化往返保持语义等价；相同输入的序列化输出稳定。正则分隔符 MUST 以 JSON 可判别形式序列化，使字面量与正则分隔符不产生歧义。

#### Scenario: JSON 往返等价

- **WHEN** 将切块结果序列化为 JSON 再反序列化
- **THEN** 得到的 Chunk 集合在 `content`、Offset 与元数据上与原结果等价

#### Scenario: 含正则分隔符的配置往返

- **WHEN** 含正则分隔符的 recursive 配置序列化为 JSON 再反序列化
- **THEN** 还原配置与原配置语义等价，分隔符类型（字面量/正则）不丢失
