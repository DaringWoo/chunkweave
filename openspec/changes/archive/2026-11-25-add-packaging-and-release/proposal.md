# Proposal

## Why

前两个 change 交付了引擎全部功能代码，但要成为"可安装、可扩展、可发布到 PyPI"的库，还缺最后一层：完整文档、可运行示例、可重复 Benchmark、CI 流水线与规范的打包产物。本 change 完成发布准备（只准备，不实际上传或发布）。

## What Changes

- 补全 `pyproject.toml` 包元信息（版本、许可证、作者占位规范、分类器等，不伪造作者身份），核心依赖保持轻量，Semantic 相关扩展以可选方式声明。
- 交付文档树：`README.md`、`docs/design.md`、`docs/configuration.md`、`docs/algorithms/{sliding-window,recursive,semantic}.md`、`docs/organization/{flat,hierarchical}.md`、`docs/metadata.md`、`docs/decisions/`（ADR），文档内容必须与实际 API 一致。
- 交付 `examples/`：Flat+Sliding Window、Flat+Recursive（中文分隔符与正则）、Flat+Semantic（Fake Provider）、Hierarchical Recursive→Sliding Window、Recursive→Semantic→Sliding Window、自定义 Chunker 注册，共 6 个，必须与实际 API 一致并可运行。
- 提供可重复 Benchmark：声明环境、输入规模与参数，结果来自真实执行，不编造数据。
- 配置 CI：Lint、类型检查、测试、构建。
- 构建并检查 wheel 与 sdist 产物及本地安装说明。
- 生成 `IMPLEMENTATION_REPORT.md`：真实记录目录结构、测试结果数字、Lint/类型检查/构建/Benchmark 结果与已知限制。
- 明确不做：上传 PyPI、创建远端 Release、破坏性 Git 操作。

## Capabilities

### New Capabilities

- `package-distribution`: 包的可安装性、构建产物正确性、可选依赖边界、文档与示例可用性、CI 与发布准备状态。

### Modified Capabilities

（无——不改引擎行为契约，仅增加交付与验证要求。）

## Impact

- 新增 `docs/` 文档树、`examples/`、Benchmark 脚本、CI 配置、`IMPLEMENTATION_REPORT.md`；完善 `pyproject.toml`。
- 依赖：前置 `add-core-models-and-strategies` 与 `add-organization-and-api` 的实现已落地。
- 对外影响：仓库达到"本地可安装、可验证、可发布候选"状态；不触碰远端发布。
- 依据文档：`docs/autonomous_chunking_engine_agent_prompt.md` 第 6、8、9、10、13 节。
