## ADDED Requirements

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
