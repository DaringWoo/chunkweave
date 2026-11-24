# Spec Delta

## Purpose

定义 Chunk 统一结果模型、Offset 语义、四组元数据结构、配置模型与序列化契约，是所有切块策略与组织方式共用的数据基础。

## ADDED Requirements

### Requirement: 统一 Chunk 结果模型

所有切块策略与组织方式 MUST 产出同一种 Chunk 类型，包含 `chunk_id`、`content`、`start_offset`、`end_offset`。`chunk_id` 在一次切块结果内唯一且稳定。任何策略 MUST NOT 返回互不兼容的结果类型。

#### Scenario: 策略产出统一类型

- **WHEN** 使用任意内置策略对同一文本切块
- **THEN** 返回的每个结果都是同一 Chunk 类型，含 `chunk_id`、`content`、`start_offset`、`end_offset`

#### Scenario: chunk_id 唯一且稳定

- **WHEN** 对同一输入与配置重复切块两次
- **THEN** 两次结果中 `chunk_id` 集合一致，且单次结果内无重复 `chunk_id`

### Requirement: Offset 语义

`start_offset`/`end_offset` MUST 使用 Python 字符串索引语义（Unicode 码点索引），采用左闭右开区间 `[start_offset, end_offset)`，且相对于最初输入文本而非某个局部片段。

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

### Requirement: 组织元数据约定

组织元数据字段的取值约定 MUST 固定：`level` 从 0 开始编号；根节点 `parent_id` 为 `None`；`sequence` 为同一父节点下子节点从 0 开始的顺序编号。

#### Scenario: 字段约定一致

- **WHEN** 组织层为 Chunk 填充组织元数据
- **THEN** 根节点 `parent_id` 为 `None`、`level` 为 0，其子节点 `level` 为 1 且 `sequence` 按顺序从 0 递增

### Requirement: Custom 元数据规则

调用方传入的 Custom 元数据 MUST 原样保留且不解释业务含义；与保留字段冲突时 MUST 拒绝或显式报错而非静默覆盖；不同 Chunk 之间 MUST NOT 意外共享可变字典对象。

#### Scenario: 保留字段冲突拒绝

- **WHEN** Custom 元数据包含与 Common/Organization/Strategy 保留字段同名的键
- **THEN** 引擎抛出清晰异常而非静默覆盖

#### Scenario: 不共享可变对象

- **WHEN** 多个 Chunk 继承同一份 Custom 元数据
- **THEN** 任一 Chunk 的元数据被修改不会影响其他 Chunk

### Requirement: 配置校验快速失败

策略配置与组织配置 MUST 在构造/校验阶段即检查合法性，非法配置 MUST 立即抛出清晰异常，而非执行到中途才失败。

#### Scenario: 非法参数立即报错

- **WHEN** 构造 `chunk_size <= 0` 或 `overlap >= chunk_size` 等非法配置
- **THEN** 在校验阶段抛出带参数信息的异常，切块未开始

### Requirement: 序列化稳定性

Chunk 结果与配置 MUST 支持 JSON 序列化，且序列化-反序列化往返保持语义等价；相同输入的序列化输出稳定。

#### Scenario: JSON 往返等价

- **WHEN** 将切块结果序列化为 JSON 再反序列化
- **THEN** 得到的 Chunk 集合在 `content`、Offset 与元数据上与原结果等价
