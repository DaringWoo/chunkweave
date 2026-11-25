# Spec Delta

## Purpose

定义切块策略协议与策略注册表的行为契约：内置策略注册、自定义 Chunker 注册、按名查找、命名冲突与未注册策略的错误处理。

## ADDED Requirements

### Requirement: 策略协议

所有切块策略 MUST 实现统一协议：接收输入文本与自身配置，产出统一 Chunk 结果集合与 Strategy Metadata。每个策略 MUST 声明其产出的 Strategy Metadata 键名集合（`metadata_keys`），供 Custom 元数据保留字段冲突检测；协议 MUST 允许各策略拥有独立配置参数，不强制共享所有参数；策略 MUST 单独可测，不依赖组织层。

#### Scenario: 协议一致调用

- **WHEN** 通过协议接口调用任一内置策略
- **THEN** 返回统一 Chunk 类型集合，且无需感知组织层

#### Scenario: 策略独立可测

- **WHEN** 在不实例化任何组织方式的情况下直接调用策略
- **THEN** 策略正常产出结果，无组织层依赖

#### Scenario: 策略声明元数据键

- **WHEN** 检查内置策略的 `metadata_keys` 声明
- **THEN** 声明集合覆盖该策略实际产出的全部 Strategy Metadata 键（如 `sliding_window` 含 `window_index`、`overlap_size`）

### Requirement: 内置策略注册

Registry MUST 预注册三个内置策略，名称固定为 `sliding_window`、`recursive`、`semantic`。

#### Scenario: 按名获取内置策略

- **WHEN** 以 `sliding_window`、`recursive`、`semantic` 任一名字向 Registry 请求
- **THEN** 返回对应的可用 Chunker

### Requirement: 自定义 Chunker 注册

Registry MUST 允许调用方注册符合策略协议（含 `metadata_keys` 声明）的自定义 Chunker，注册后即可与内置策略同样按名获取使用。

#### Scenario: 注册并获取自定义策略

- **WHEN** 调用方注册一个自定义 Chunker 并按其名称请求
- **THEN** Registry 返回该 Chunker，且其切块行为与内置策略一致地接入

### Requirement: 未注册策略错误

按名称获取未注册策略时，Registry MUST 抛出清晰异常，错误信息 MUST 包含所请求的策略名。

#### Scenario: 未知名称报错

- **WHEN** 以未注册的名称请求策略
- **THEN** 抛出包含该名称的清晰异常

### Requirement: 名称冲突行为

重复注册同名策略时 MUST 有明确行为：默认拒绝并抛出清晰异常；如需替换 MUST 通过显式方式声明，不允许静默覆盖。

#### Scenario: 同名注册默认拒绝

- **WHEN** 以已存在的名称再次注册 Chunker 且未显式声明替换
- **THEN** Registry 抛出清晰异常，原注册保持不变

#### Scenario: 显式替换生效

- **WHEN** 以已存在的名称注册 Chunker 且显式声明替换
- **THEN** 新 Chunker 替换原注册，后续按名获取返回新实现

### Requirement: Registry 职责边界

Registry MUST 只负责策略的注册与查找，MUST NOT 负责层级组织、父子关系建立或元数据组装。

#### Scenario: 边界不被破坏

- **WHEN** 检查 Registry 对外暴露的能力
- **THEN** 其接口仅覆盖注册与获取，不包含任何组织执行入口
