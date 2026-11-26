# Spec Delta

## Purpose

定义 Policy 到 Execution IR 的编译契约：`compile(policy)` 产出的 `ExecutionPlan` 内容、缺省值补全与 Context 路径解析、编译与执行的边界、稳定 `policy_hash`，以及 Runtime 只消费 IR 的依赖约束。

## ADDED Requirements

### Requirement: 编译产出 Execution IR

`compile(policy)` MUST 返回 `ExecutionPlan`（Execution IR 的公共类型），包含：Policy 身份（`api_version`、`id`、`name`、`version`）、`policy_hash`、按声明顺序排列的层（索引、`name`、`strategy`、经校验并补全缺省值的 `params`）、Metadata 字段解析计划（字段名到固定值或已解析 Context 路径的映射）与 include 选项。

#### Scenario: 编译产物内容

- **WHEN** 对合法 Policy 调用 `compile()`
- **THEN** 返回的 `ExecutionPlan` 含 Policy 身份、`policy_hash`、按声明顺序的层、Metadata 字段解析计划与 include 选项

### Requirement: 编译先校验

`compile()` MUST 先完成 Policy 校验；非法 Policy MUST 编译失败并报出校验错误，MUST NOT 产出 Execution IR。

#### Scenario: 非法 Policy 不产出 IR

- **WHEN** 对含未注册策略或非法 `params` 的 Policy 调用 `compile()`
- **THEN** 报出校验错误，不产出 Execution IR

### Requirement: 编译不执行切块

`compile()` MUST NOT 执行任何切块：不要求提供 text、Context 或 Provider，不调用任何 Chunker。

#### Scenario: 编译无运行时依赖

- **WHEN** 对声明 `source: context.x` 字段的 Policy 调用 `compile()` 且不传 Context
- **THEN** 编译正常完成并产出 Execution IR，不因缺少 Context 报错

### Requirement: IR 补全而非复制

Execution IR MUST 是经校验、解析与缺省值补全的执行计划，MUST NOT 是 Policy 原始声明的逐字复制：省略的可选参数以缺省值呈现，`source` 路径以已解析的路径段形式呈现。

#### Scenario: 缺省参数补全

- **WHEN** 编译省略 `overlap` 的 `sliding_window` 层
- **THEN** Execution IR 中该层的 `params` 显示 `overlap` 为 0

#### Scenario: Context 路径已解析

- **WHEN** 编译声明 `source: context.a.b` 的字段
- **THEN** Execution IR 中该字段的路径以等价于路径段序列 `["a", "b"]` 的已解析形式呈现

### Requirement: IR 可序列化且不含运行时对象

Execution IR MUST 支持 `model_dump()`/`model_dump_json()` 序列化并可重建；MUST NOT 含 Provider 实例或可调用对象；正则分隔符 MUST 保持可与字面量判别的形式。

#### Scenario: IR 序列化往返

- **WHEN** 将 `ExecutionPlan` `model_dump_json()` 后再重建
- **THEN** 重建结果语义等价，正则分隔符仍可与字面量判别，全程无 Provider 实例或可调用对象参与

### Requirement: Policy Hash 稳定

`policy_hash` MUST 为 `sha256:<64 位十六进制>` 格式；仅键顺序、空白、注释或引号风格不同的 YAML MUST 得到相同 Hash；任一声明值变化 MUST 得到不同 Hash；Hash MUST 与 Context、text、Provider 无关。

#### Scenario: 等价 YAML 同 Hash

- **WHEN** 两份仅键顺序、空白与注释不同的 YAML 表达同一 Policy
- **THEN** 两者的 `policy_hash` 相同

#### Scenario: 声明变化不同 Hash

- **WHEN** 任一声明值（如某层 `params` 取值）变化
- **THEN** `policy_hash` 不同

### Requirement: Runtime 只消费 IR

`execute()` 的结果 MUST 等价于先 `compile()` 再按该 Execution IR 执行；Runtime MUST NOT 直接读取 YAML 文本或 Policy 原始字典。

#### Scenario: 执行结果与 IR 一致

- **WHEN** 对同一 Policy 分别调用 `compile()` 与 `execute()`
- **THEN** `execute()` 结果的 `policy_hash` 等于 `compile()` 产出的 Hash

#### Scenario: 相同输入结果确定

- **WHEN** 对同一 Policy 与相同 text、Context 执行两次 `execute()`
- **THEN** 两次产出的 `chunks` 完全相同
