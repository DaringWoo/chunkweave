# Spec Delta

## MODIFIED Requirements

### Requirement: 可安装性

包 MUST 支持 `pip install` 本地安装与 `pip install -e .` 开发安装；`requires-python >= 3.11`；核心安装 MUST 只含轻量依赖，允许一个数据校验库（Pydantic V2）与一个 YAML 解析库这类轻量依赖，MUST NOT 引入大型模型库或完整 RAG 框架。

#### Scenario: 干净环境本地安装

- **WHEN** 在不含开发依赖的干净环境中执行 `pip install .`
- **THEN** 安装成功，`import chunkweave` 可用，未连带安装大型模型库

### Requirement: 可选依赖边界

Semantic Provider 相关扩展 MUST 以可选依赖（extras）或零依赖方式提供；不安装可选项时核心功能全部可用。

#### Scenario: 无可选依赖的核心功能

- **WHEN** 仅安装核心包且不装任何 extras
- **THEN** 单层与多层 Policy 及非 Semantic 策略全部可用；Semantic 在未注入 Provider 时给出清晰异常

### Requirement: 文档可用性

项目 MUST 交付：`README.md`、`docs/design.md`、`docs/configuration.md`（Policy YAML DSL 参考，覆盖 `api_version`、`policy`、`pipeline.levels`、`params`、`metadata.fields`/`include`）、三种算法文档、多层组织文档（`pipeline.levels`）、`docs/metadata.md`（`value`/`source` 与 Context 的职责划分）与 `docs/decisions/` ADR；文档描述的 API、参数与行为 MUST 与实际实现一致。

#### Scenario: 文档与实现一致

- **WHEN** 按文档中的 API 名称与参数示例调用
- **THEN** 调用成功且行为与文档描述一致

### Requirement: 示例可运行

`examples/policies/` MUST 提供可加载的 YAML Policy 文件；`examples/` MUST 包含 6 个示例：单层 `sliding_window`、单层 `recursive`（中文分隔符与正则）、单层 `semantic`（Fake Provider）、两层 recursive→sliding_window、三层 recursive→semantic→sliding_window、自定义 Chunker 注册；每个示例 MUST 经 `Policy.from_file` 与 `execute()` 对真实 API 实际运行成功，Semantic 示例 MUST NOT 下载真实模型。

#### Scenario: 六个示例逐一执行

- **WHEN** 依次运行 `examples/` 下 6 个示例
- **THEN** 全部正常结束并输出合理结果，Semantic 示例使用 Fake Provider 无网络依赖
