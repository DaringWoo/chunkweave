# Policy 配置参考

Policy 是 chunkweave 唯一的配置形式：一个 YAML 文档，声明流水线层级、
各层策略参数与元数据规则。加载入口为 `Policy.from_file(path)`（UTF-8）
或 `Policy.from_yaml(yaml_text)`；解析后的对象经 `ChunkEngine.execute`
使用。加载统一走 `yaml.safe_load`，`!!python/object` 等不安全标签会被
拒绝并报 `PolicyLoadError`。

## 顶层结构

```yaml
api_version: chunkweave/v1          # 必填，且必须等于该值
policy:                             # 必填，身份信息
  id: my-policy
  name: 我的策略
  version: 1.0.0                    # MAJOR.MINOR.PATCH 三段数字
pipeline:                           # 必填
  levels:                           # 必填，非空列表
    - name: paragraph
      strategy: recursive
      params: {chunk_size: 500}
metadata:                           # 可选
  fields: {}
  include: {strategy: true, organization: true}
```

- `policy.id`/`name`/`version` 均为非空字符串；`version` 必须匹配
  `MAJOR.MINOR.PATCH`（`1.0`、`v1.0.0` 都被拒绝）。
- `api_version` 不等于 `chunkweave/v1` 时报错并指明支持的版本。
- Policy 对象的 `policy.id`/`name`/`version` 可直接属性访问，嵌套的
  `policy.policy.id` 等路径同样可用。

## pipeline.levels

每个层级声明：

| 键 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 非空字符串；层名以 `level_name` 键经 `include.organization` 复制进 `metadata` |
| `strategy` | 是 | 非空字符串；内置 `sliding_window`/`recursive`/`semantic` 或已注册的自定义策略 |
| `params` | 否 | 映射，缺省 `{}`；只允许该策略参数 Schema 中定义的键 |

`levels` 至少一层；一层即平铺输出，多层按层级逐级下切（见
`docs/organization/pipeline-levels.md`）。

## 策略参数

### sliding_window

| 参数 | 必填 | 缺省 | 约束 |
| --- | --- | --- | --- |
| `chunk_size` | 是 | — | 严格整数 > 0，Unicode 码点计长 |
| `overlap` | 否 | `0` | 严格整数，`0 <= overlap < chunk_size`；`0` = 定长切块 |

### recursive

| 参数 | 必填 | 缺省 | 约束 |
| --- | --- | --- | --- |
| `chunk_size` | 是 | — | 严格整数 > 0 |
| `separators` | 否 | `["\n\n","\n","。","！","？","；","，",""]` | 分隔符声明列表，优先级从高到低 |
| `overlap` | 否 | `0` | 严格整数 >= 0 |
| `keep_separator` | 否 | `"previous"` | `"previous"`/`"next"`/`"none"` |
| `max_depth` | 否 | `null` | 严格整数 > 0；更深的片段回退逐字符切分 |

### semantic

| 参数 | 必填 | 缺省 | 约束 |
| --- | --- | --- | --- |
| `threshold` | 是 | — | `[0,1]` 内 int/float（拒绝 bool），存为 float |
| `chunk_size` | 是 | — | 严格整数 > 0 |
| `unit_separators` | 否 | `["\n\n","\n","。","！","？"]` | 同 `separators` 的声明形式 |

`semantic` 层要求 `execute(provider=...)` 提供 Provider，否则在任何切块
开始前报 `ProviderMissingError`。

### 分隔符声明形式

`separators`/`unit_separators` 的元素为：

- 字面量字符串：`"\n\n"`、`"。"`；
- 映射：`{value: "<pattern>", regex: true}` 声明正则分隔符（`regex`
  缺省 `false`）；`regex: true` 的 pattern 必须能编译，否则校验失败。

`""` 或耗尽列表表示逐字符兜底；`separators: []` 表示只用兜底。

### 类型规则

参数模型使用严格类型：整数字段拒绝 bool 与字符串；`threshold` 拒绝
bool 与字符串。未定义键一律拒绝（不会静默忽略）。

## metadata.fields

声明式业务元数据。每个字段必须恰好声明一个来源：

```yaml
metadata:
  fields:
    doc_id: {value: "d-42"}                # 固定值
    nullable: {value: null}                # null 也是合法固定值
    tenant: {source: context.request.tenant}  # 执行时从 Context 取值
```

- `value`：任意可无损表示为 JSON 的值；`value: null` 合法且视为已声明。
  数值必须有限（拒绝 `.nan`/`.inf`），对象键必须是字符串。
- `source`：`context.` 前缀的路径，段名非空即可（`context.a.b.c`）；
  执行时对每次 `execute(context=...)` 提供的映射逐级取值，取到的值
  也必须满足同一 JSON 规则。
- 字段名必须非空，且不得使用保留键。
- `fields` 对所有层级生效：每个 Chunk 的 `metadata` 含同一字段集，
  各持有独立副本。

## metadata.include

```yaml
metadata:
  include: {strategy: true, organization: true}   # 缺省均为 true
```

复制语义：把以下保留键的副本复制进每个 Chunk 的 `metadata`（不隐藏
Chunk 属性本身，属性始终完整）：

- `organization` 为真时：`parent_id`、`level`、`sequence`、`level_name`
- `strategy` 为真时：`strategy`、`strategy_metadata`

## 保留键

`metadata.fields` 的字段名不得使用以下保留键（与 include 开关无关）：

`chunk_id`、`content`、`parent_id`、`level`、`sequence`、`start_offset`、
`end_offset`、`strategy`、`strategy_metadata`、`metadata`、`level_name`

## 未知字段严格拒绝

以下位置出现未声明的键都会在加载/校验时报错，错误信息含字段路径
（如 `pipeline.levels[1].strategy`）：Policy 顶层、`policy`、`pipeline`、
每个 level、`metadata`、`metadata.include`、每个字段配置（只允许
`value`/`source`）。两个豁免：`value` 的内容不受未知字段约束；
`params` 内的未知键由对应策略的参数 Schema 拒绝。

## YAML 隐式类型提醒

YAML 会在解析时猜测类型，三类常见坑：

- `2024-01-01` 会被解析成日期对象——它不是 JSON 可序列化值，
  作为 `value` 会报校验错误；
- `yes`/`no`/`on`/`off` 会被解析成布尔值——想表达字符串必须加引号；
- `1.0` 会被解析成浮点数——`version: 1.0` 因此不合法，应写
  `version: "1.0"`（或直接 `1.0.0`）。

## 错误类型

| 错误 | 时机 |
| --- | --- |
| `PolicyLoadError` | 文件读取失败、YAML 语法错误（含行列号）、根节点非映射、不安全标签 |
| `PolicyValidationError` | 结构校验、未知字段、版本格式、params 语义校验等；带 `.path`/`.reason` |
| `UnregisteredStrategyError` | `pipeline.levels[].strategy` 未注册（`PolicyValidationError` 子类） |
| `ContextResolutionError` | `source` 路径缺失、Context 未提供、值不可序列化 |
| `ProviderMissingError` | `requires_provider` 的层缺 Provider，切块前报错 |
