# policy-engine Specification

## Purpose

定义 ChunkWeave 的 YAML Policy DSL：Policy 顶层结构、文件与字符串加载方式、结构与语义校验规则（含未知字段拒绝与版本格式），以及 Metadata 字段声明（`value`/`source`、include 选项）的契约。

## Requirements

### Requirement: Policy 顶层结构

Policy MUST 为 YAML 映射，顶层含 `api_version`、`policy` 与 `pipeline`；`policy` 内的 `id`、`name`、`version` MUST 为必填非空字符串；`metadata` 可选，缺省时等价于无字段声明且 `include` 全部为 `true`。

#### Scenario: 最小合法 Policy

- **WHEN** Policy 含 `api_version`、完整 `policy` 身份信息与一层 `pipeline.levels`，无 `metadata`
- **THEN** Policy 合法，`metadata` 等价于无字段、`include` 全部为 `true`

#### Scenario: 缺少必填身份信息报错

- **WHEN** `policy.id`、`policy.name` 或 `policy.version` 缺失或为空字符串
- **THEN** 加载时报出含字段路径的校验错误

### Requirement: API 版本识别

`api_version` MUST 为 `chunkweave/v1`；其他取值 MUST 报错，错误信息 MUST 指出当前支持的 API 版本。

#### Scenario: 不支持的 api_version 报错

- **WHEN** `api_version` 取值不是 `chunkweave/v1`
- **THEN** 报出校验错误，错误信息指出支持的版本为 `chunkweave/v1`

### Requirement: 从文件与字符串加载

`Policy.from_file(path)` MUST 以 UTF-8 读取并解析 YAML 文件；`Policy.from_yaml(yaml_text)` MUST 从字符串解析。MUST 使用安全解析：带 Python 对象构造标签（如 `!!python/object`）的 YAML MUST 被拒绝，MUST NOT 执行任意对象构造。文件不存在、YAML 语法错误、根节点不是映射时 MUST 报出清晰错误。

#### Scenario: 文件加载成功

- **WHEN** 对存在的合法 YAML 文件调用 `Policy.from_file(path)`
- **THEN** 返回 Policy 对象

#### Scenario: 加载失败报错

- **WHEN** 文件不存在、YAML 语法错误或根节点不是映射
- **THEN** 报出指明失败原因的清晰错误

#### Scenario: 不安全标签被拒

- **WHEN** YAML 含 `!!python/object` 等对象构造标签
- **THEN** 加载被拒绝并报错，不执行任意对象构造

### Requirement: Policy 对象访问

加载后的 Policy MUST 支持直接属性访问：`policy.id`、`policy.name`、`policy.version`、`policy.pipeline.levels`、`policy.metadata.fields`；同时 MUST 可通过 `policy.policy.id` 等嵌套路径访问身份信息。

#### Scenario: 属性直达

- **WHEN** 读取已加载 Policy 的 `id`、`version`、`pipeline.levels`、`metadata.fields`
- **THEN** 均可通过属性直接访问，无需字典下标

### Requirement: Pipeline Levels 声明

`pipeline.levels` MUST 为非空列表；每层 MUST 含 `name`（必填字符串）与 `strategy`（必填字符串），`params` 可选且为映射、缺省为空映射。层数即组织层数：1 层平铺、2 层父子、N 层多级。

#### Scenario: 非空 levels 合法

- **WHEN** `pipeline.levels` 含一层或多层且各层声明 `name` 与 `strategy`
- **THEN** 结构合法；未提供 `params` 的层等价于空映射

#### Scenario: 空 levels 报错

- **WHEN** `pipeline.levels` 为空列表或缺失
- **THEN** 报出含字段路径的校验错误

### Requirement: 结构校验

结构校验 MUST 在加载阶段检查 YAML 结构、字段类型与必填项；类型错误或缺必填项 MUST 在加载时报错，错误信息 MUST 含字段路径（如 `pipeline.levels[1].strategy`）。

#### Scenario: 类型错误带字段路径

- **WHEN** `pipeline.levels[1]` 缺少 `strategy` 或其类型不是字符串
- **THEN** 加载时报出含 `pipeline.levels[1].strategy` 字段路径的校验错误

### Requirement: 未知字段拒绝

Policy 顶层、`policy`、`pipeline`、每个 level、`metadata`、`metadata.include` 与每个字段配置中的未知键 MUST 报出含字段路径的校验错误；`value` 的内容不受此约束；`params` 中的未知参数由该层策略的参数 Schema 拒绝。

#### Scenario: 顶层未知键报错

- **WHEN** Policy 顶层、`policy`、level 或 `metadata` 中出现未定义的键
- **THEN** 报出含该键字段路径的校验错误

#### Scenario: pipeline 与 include 未知键报错

- **WHEN** `pipeline` 或 `metadata.include` 中出现未定义的键
- **THEN** 报出含该键字段路径的校验错误

#### Scenario: params 未知参数报错

- **WHEN** 某层 `params` 含该策略未定义的参数名
- **THEN** 语义校验按策略 Schema 拒绝并报错

### Requirement: 语义校验

语义校验 MUST 检查：各层 `strategy` 已在 Strategy Registry 注册、各层 `params` 通过对应策略的参数 Schema。语义校验 MUST 在 `validate()`、`compile()` 或 `execute()` 时执行，错误信息 MUST 含层位置（索引或名称）、策略名与参数名。

#### Scenario: 未注册策略报错

- **WHEN** 某层 `strategy` 引用未在 Registry 注册的策略名
- **THEN** 语义校验报错，错误信息含层位置与策略名

#### Scenario: params 语义校验报错

- **WHEN** 某层 `params` 不满足该策略的参数 Schema
- **THEN** 语义校验报错，错误信息含层位置、策略名与参数名

### Requirement: Policy 版本格式

`policy.version` MUST 为 `MAJOR.MINOR.PATCH` 三段非负整数格式；不符合该格式 MUST 报校验错误。

#### Scenario: 非法版本格式报错

- **WHEN** `policy.version` 不是三段非负整数（如 `1.0` 或 `v1.0.0`）
- **THEN** 报出校验错误

### Requirement: Metadata 字段来源互斥

`metadata.fields` 中每个字段 MUST 且只能配置 `value` 或 `source` 之一；两者都配置或都未配置 MUST 报错。`value: null` MUST 视为合法的固定值，与未配置 `value` 区分。

#### Scenario: 双来源报错

- **WHEN** 某字段同时配置 `value` 与 `source`
- **THEN** 报出含字段名的校验错误

#### Scenario: 无来源报错

- **WHEN** 某字段既未配置 `value` 也未配置 `source`
- **THEN** 报出含字段名的校验错误

#### Scenario: null 固定值合法

- **WHEN** 某字段显式声明 `value: null`
- **THEN** 该字段合法，执行为固定值 `null`

### Requirement: Metadata 固定值可序列化

字段的 `value` MUST 为 JSON 可序列化值；不可序列化时 MUST 报校验错误。

#### Scenario: 不可序列化固定值报错

- **WHEN** 某字段的 `value` 为不可 JSON 序列化的值
- **THEN** 报出含字段名的校验错误

### Requirement: Metadata 字段名不得使用保留键

`metadata.fields` 的字段名 MUST 为非空字符串，且 MUST NOT 使用保留键：`chunk_id`、`content`、`parent_id`、`level`、`sequence`、`start_offset`、`end_offset`、`strategy`、`strategy_metadata`、`metadata`、`level_name`。使用保留键作字段名时，加载阶段 MUST 报出含字段名的校验错误，与 `include` 取值无关。

#### Scenario: 保留键名被拒

- **WHEN** `metadata.fields` 中任一字段名使用保留键（如 `strategy` 或 `level_name`）
- **THEN** 加载阶段报出含该字段名的校验错误

#### Scenario: include 全关仍被拒

- **WHEN** `include.strategy` 与 `include.organization` 均为 `false` 且字段名使用保留键
- **THEN** 仍报出含字段名的校验错误

### Requirement: Context 路径语法

字段的 `source` MUST 为 `context.` 前缀加一个或多个以 `.` 分隔的非空键，按嵌套映射逐级解析；语法非法时 MUST 在校验阶段报错，不要求提供 Context。

#### Scenario: 路径语法非法报错

- **WHEN** `source` 不是 `context.` 前缀、含空键或键序列不合法
- **THEN** 校验阶段报出含字段名与路径的校验错误

#### Scenario: 嵌套路径合法

- **WHEN** `source` 为 `context.a.b` 形式
- **THEN** 语法合法，按嵌套映射逐级解析

### Requirement: Metadata 输出选项声明

`metadata.include.strategy` 与 `metadata.include.organization` MUST 为布尔值，缺省为 `true`；非布尔取值 MUST 报校验错误。两个选项的可观察效果见 `chunk-organization`「Metadata 输出选项」。

#### Scenario: include 缺省为真

- **WHEN** `metadata` 未声明 `include`
- **THEN** `include.strategy` 与 `include.organization` 等价于 `true`

### Requirement: Context 不声明字段

Context MUST 只提供 `source` 引用路径的运行时值，不能声明或改变 `metadata` 键集合；`metadata` 的键集合 MUST 由 Policy `metadata.fields` 与 `metadata.include` 选项共同决定（生成行为见 `chunk-organization`「业务 Metadata 生成」「Context 只提供值」「Metadata 输出选项」）。

#### Scenario: 字段集由 Policy 决定

- **WHEN** Policy 声明两个字段而 Context 提供其他键
- **THEN** 产出 `metadata` 的键集合恰为 Policy 声明的字段加 `include` 选项启用的保留键，不含 Context 中的其他键

### Requirement: 从映射加载

`Policy` MUST 提供从映射加载的入口：接受与 YAML 解析结果结构相同的映射形式的 Policy，执行与字符串加载相同的结构校验；映射不是合法结构时抛出带字段路径的校验错误，`data` 不是映射时抛出加载错误。

#### Scenario: 合法映射加载成功

- **WHEN** 以映射形式提供完整合法的 Policy 结构
- **THEN** 加载成功，行为与从 YAML 字符串加载等价

#### Scenario: 映射内未知字段报错

- **WHEN** 映射含未声明字段
- **THEN** 抛出含字段路径的校验错误

#### Scenario: 非映射被拒绝

- **WHEN** `data` 为列表、字符串或其他非映射类型
- **THEN** 抛出加载错误而非校验错误
