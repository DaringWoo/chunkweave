# Spec Delta

## Purpose

定义包的分发与发布准备契约：可安装性、构建产物、可选依赖边界、文档与示例可用性、Benchmark 可重复性与 CI 流水线。

## ADDED Requirements

### Requirement: 可安装性

包 MUST 支持 `pip install` 本地安装与 `pip install -e .` 开发安装；`requires-python >= 3.11`；核心安装 MUST 只含轻量依赖，不引入大型模型库或完整 RAG 框架。

#### Scenario: 干净环境本地安装

- **WHEN** 在不含开发依赖的干净环境中执行 `pip install .`
- **THEN** 安装成功，`import chunkweave` 可用，未连带安装大型模型库

### Requirement: 构建产物

项目 MUST 能成功构建 wheel 与 sdist；产物 MUST 包含包源码、LICENSE、README 与正确元信息（名称、版本、许可证、作者信息真实不伪造）；wheel 安装后功能与源码一致。

#### Scenario: 构建并检查产物

- **WHEN** 执行标准构建命令产出 wheel 与 sdist
- **THEN** 两者构建成功，包内容与元信息完整，wheel 可安装且 `import` 正常

### Requirement: 可选依赖边界

Semantic Provider 相关扩展 MUST 以可选依赖（extras）或零依赖方式提供；不安装可选项时核心功能全部可用。

#### Scenario: 无可选依赖的核心功能

- **WHEN** 仅安装核心包且不装任何 extras
- **THEN** Flat/Hierarchical 与非 Semantic 策略全部可用；Semantic 在未注入 Provider 时给出清晰异常

### Requirement: 文档可用性

项目 MUST 交付：`README.md`、`docs/design.md`、`docs/configuration.md`、三种算法文档、两种组织方式文档、`docs/metadata.md` 与 `docs/decisions/` ADR；文档描述的 API、参数与行为 MUST 与实际实现一致。

#### Scenario: 文档与实现一致

- **WHEN** 按文档中的 API 名称与参数示例调用
- **THEN** 调用成功且行为与文档描述一致

### Requirement: 示例可运行

`examples/` MUST 包含 6 个示例：Flat+Sliding Window、Flat+Recursive（中文分隔符与正则）、Flat+Semantic（Fake Provider）、Hierarchical Recursive→Sliding Window、Recursive→Semantic→Sliding Window、自定义 Chunker 注册；每个示例 MUST 对真实 API 实际运行成功，Semantic 示例 MUST NOT 下载真实模型。

#### Scenario: 六个示例逐一执行

- **WHEN** 依次运行 `examples/` 下 6 个示例
- **THEN** 全部正常结束并输出合理结果，Semantic 示例使用 Fake Provider 无网络依赖

### Requirement: 可重复 Benchmark

项目 MUST 提供可重复 Benchmark：记录运行环境、输入规模与参数配置，性能数字 MUST 来自真实执行；不要求并行或分布式执行。

#### Scenario: Benchmark 可复现

- **WHEN** 按文档说明运行 Benchmark
- **THEN** 得到带环境与参数标注的真实性能结果，无编造数据

### Requirement: CI 流水线

项目 MUST 配置 CI，至少覆盖：Lint（ruff）、类型检查（mypy）、测试（pytest）、构建（wheel/sdist）；流水线失败 MUST 如实反映，不允许静默跳过。

#### Scenario: CI 四项检查

- **WHEN** 触发 CI 流水线
- **THEN** Lint、类型检查、测试、构建四步均实际执行并报告真实结果

### Requirement: 发布边界

发布准备 MUST NOT 包含实际上传 PyPI、创建远端 Release 或破坏性 Git 操作；所有交付物停留在本地可验证状态。

#### Scenario: 无远端发布副作用

- **WHEN** 完成全部发布准备工作
- **THEN** 远端无新 Tag/Release，PyPI 无上传记录，工作区保留全部本地产物
