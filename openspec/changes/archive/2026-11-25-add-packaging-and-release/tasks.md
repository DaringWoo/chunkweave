# Tasks

## 1. 包元信息与依赖边界

- [x] 1.1 补全 `pyproject.toml`：名称、版本 0.1.0、`requires-python >= 3.11`、license 引用、分类器、项目 URL；作者取 git `user.name`，无法确认则留空——验证 `pip install -e .` 与元信息渲染正确
- [x] 1.2 声明可选依赖边界（Semantic 适配器走 extras，核心零重依赖），验证干净 venv `pip install .` 后核心功能可用且未装大型库
- [x] 1.3 核对 LICENSE 全文确认为 MIT 并检查 wheel 会打包该文件，验证 sdist/wheel 内含 LICENSE

## 2. 文档树与 ADR

- [x] 2.1 完善 `README.md`（英文为主+中文概述段）：定位、边界、安装、快速上手、API 一览，验证其中示例代码可实际运行
- [x] 2.2 编写 `docs/design.md`、`docs/configuration.md`、`docs/metadata.md` 与 `docs/decisions/` ADR（Python>=3.11、hatchling、分隔符归属、chunk_id 编号、Provider 协议、custom 继承），验证描述的参数与行为同实现一致
- [x] 2.3 编写 `docs/algorithms/{sliding-window,recursive,semantic}.md` 与 `docs/organization/{flat,hierarchical}.md`，验证文档中每个代码片段可运行

## 3. 示例

- [x] 3.1 实现并实际运行 `examples/` 前三个：Flat+Sliding Window、Flat+Recursive（中文+正则分隔符）、Flat+Semantic（确定性 Fake Provider，无网络）
- [x] 3.2 实现并实际运行后三个：Hierarchical Recursive→Sliding Window、Recursive→Semantic→Sliding Window、自定义 Chunker 注册
- [x] 3.3 将 6 个示例纳入 CI 执行步骤，验证任一示例失败会使 CI 变红

## 4. Benchmark

- [x] 4.1 编写 `benchmarks/bench.py`（stdlib timeit、固定种子、输出环境+参数+结果 JSON），实际运行并保存真实数字
- [x] 4.2 将 Benchmark 环境、参数与结果写入报告引用，验证报告中数字与脚本输出一致

## 5. CI

- [x] 5.1 编写 `.github/workflows/ci.yml`：push/PR 触发、Python 3.11–3.13 matrix、ruff→mypy→pytest→build(+twine check)→examples 步骤，验证工作流语法正确且各步骤真实执行无静默跳过

## 6. 构建与发布准备

- [x] 6.1 `python -m build` 产出 wheel+sdist，`twine check` 通过，验证产物内容（源码、LICENSE、README、METADATA）
- [x] 6.2 临时 venv `pip install dist/*.whl` + `import chunkweave` 冒烟 + 一次示例运行，验证安装可用
- [x] 6.3 生成 `IMPLEMENTATION_REPORT.md`：目录结构、模块与架构、算法参数、执行机制、元数据示例、真实测试数量与结果、ruff/mypy/构建/Benchmark 输出、已知限制、安装与二次开发说明、后续版本建议——所有数字来自实际执行记录

## 7. 最终质量门禁

- [x] 7.1 全量 `pytest` + `ruff check` + `mypy src` + 构建 + 示例全跑，全部通过；对照三份 change 的验收清单逐项核对并在报告中标注未完成项

## Workflow follow-up

- 三个 change 全部实施完成后，按顺序执行 openspec archive 归档。
