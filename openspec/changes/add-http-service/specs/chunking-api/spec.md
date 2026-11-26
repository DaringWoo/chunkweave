## MODIFIED Requirements

### Requirement: 统一公共入口

引擎 MUST 提供统一公共 API 入口，调用方经 `Policy`（`Policy.from_file(path)`、`Policy.from_yaml(yaml_text)`、`Policy.from_dict(data)`）与 `ChunkEngine`（`validate(policy)`、`compile(policy)`、`execute(text, policy, context=None, provider=None)`）完成全部能力：加载与校验 Policy、编译 Execution IR、执行切块、注册自定义 Chunker、按次注入 Semantic Provider、获取结果与序列化，无需实例化内部模块。API 命名 MUST 一致且与 README 文档一致。

#### Scenario: 单一入口完成组合调用

- **WHEN** 调用方通过公共入口加载 Policy 并执行切块
- **THEN** 无需实例化内部模块即可完成，返回统一 ChunkResult 结果
