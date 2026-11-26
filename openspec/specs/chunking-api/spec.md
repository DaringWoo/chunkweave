# chunking-api Specification

## Purpose
定义引擎面向调用方的公共入口行为：`Policy` 加载与 `ChunkEngine.validate/compile/execute`、自定义 Chunker 注册、Semantic Provider 按次注入、执行追溯信息与序列化入口。

## Requirements

### Requirement: 统一公共入口

引擎 MUST 提供统一公共 API 入口，调用方经 `Policy`（`Policy.from_file(path)`、`Policy.from_yaml(yaml_text)`）与 `ChunkEngine`（`validate(policy)`、`compile(policy)`、`execute(text, policy, context=None, provider=None)`）完成全部能力：加载与校验 Policy、编译 Execution IR、执行切块、注册自定义 Chunker、按次注入 Semantic Provider、获取结果与序列化，无需实例化内部模块。API 命名 MUST 一致且与 README 文档一致。

#### Scenario: 单一入口完成组合调用

- **WHEN** 调用方通过公共入口加载 Policy 并执行切块
- **THEN** 无需实例化内部模块即可完成，返回统一 ChunkResult 结果

### Requirement: 执行入口

`execute()` MUST 只接受已加载的 Policy 对象；传入文件路径、YAML 字符串或原始字典 MUST 报错。`execute()` MUST 在内部自动完成校验与编译，普通用户无需先调用 `validate()`/`compile()`。未注册策略、非法 `params`、需要 Provider 的层（如 `semantic`）缺少 Provider（在任何切块开始前报错）、`source` 引用的 Context 路径缺失，MUST 报出清晰错误且不返回部分结果。

#### Scenario: Flat 一键执行

- **WHEN** 调用方以 `pipeline.levels` 仅一层的 Policy 执行 `execute()`
- **THEN** 返回平铺 Chunk 集合，过程无需感知内部模块细节

#### Scenario: 层级配置执行

- **WHEN** 调用方以多层 `pipeline.levels` 的 Policy 执行 `execute()`
- **THEN** 按层产出带组织关系的完整 Chunk 集合；`pipeline.levels` 中引用未注册策略时抛出清晰异常

#### Scenario: 非 Policy 参数被拒

- **WHEN** 调用方向 `execute()` 的 `policy` 参数传入文件路径、YAML 字符串或原始字典
- **THEN** 报出清晰错误，不执行切块

#### Scenario: semantic 缺 Provider

- **WHEN** 执行含需要 Provider 的层（如 `semantic`）的 Policy 而未提供 `provider` 参数
- **THEN** 在任何切块开始前报出指明缺少 Provider 的清晰错误

### Requirement: 扩展入口

公共 API MUST 暴露 `register(name, factory, params_model=..., requires_provider=..., replace=...)` 注册入口：调用方提供符合策略协议的 Chunker 工厂、参数 Schema 与是否需要 Provider 的声明，注册后即可在任意层 `strategy` 按名引用、`params` 按其 Schema 校验；声明需要 Provider 的策略被引用而 `execute()` 未提供 `provider` 时 MUST 在任何切块开始前报错。Semantic Provider 经 `execute(provider=...)` 按次注入；MUST NOT 提供引擎级 `set_provider`。

#### Scenario: 自定义策略接入层级

- **WHEN** 调用方注册自定义 Chunker 并在某层 `strategy` 中引用其名
- **THEN** 该层按自定义策略切块，行为与内置策略一致

### Requirement: 序列化入口

公共 API MUST 支持 ChunkResult 的序列化/反序列化：ChunkResult 经 `model_dump()`/`model_dump_json()` 输出 JSON 兼容结构，可重建且往返等价；对相同输入序列化输出稳定。

#### Scenario: 结果序列化往返

- **WHEN** 将多层执行结果序列化为 JSON 再恢复
- **THEN** 恢复的 Chunk 集合在内容、Offset、`parent_id` 关系与 `metadata` 上等价

### Requirement: validate 校验 Policy

`validate(policy)` MUST 对 Policy 执行结构与语义校验；Policy 合法时正常返回，MUST NOT 执行切块，MUST NOT 要求提供 text、Context 或 Provider；Policy 非法时 MUST 抛出校验错误。

#### Scenario: 合法 Policy 校验通过

- **WHEN** 对合法 Policy 调用 `validate()`
- **THEN** 正常返回，未执行任何切块，无需 Context 或 Provider

#### Scenario: 非法 Policy 校验报错

- **WHEN** 对含未注册策略或非法 `params` 的 Policy 调用 `validate()`
- **THEN** 抛出含定位信息的校验错误

### Requirement: 执行追溯信息

ChunkResult 的 `policy_id`、`policy_version` MUST 等于 Policy 声明值；`policy_hash` MUST 等于 `compile(policy)` 产出的 Hash；`engine_version` MUST 等于包版本 `chunkweave.__version__`；每次 `execute()` 的 `execution_id` MUST 唯一；`execution_time_ms` MUST 大于等于 0。

#### Scenario: 追溯字段与 Policy 一致

- **WHEN** 执行一份已知 `id`/`version` 的 Policy
- **THEN** 结果 `policy_id`、`policy_version` 等于声明值，`policy_hash` 等于 `compile()` 结果，`engine_version` 等于包版本，`execution_time_ms` 不小于 0

#### Scenario: execution_id 每次唯一

- **WHEN** 对同一输入连续执行两次 `execute()`
- **THEN** 两次结果的 `execution_id` 不同
