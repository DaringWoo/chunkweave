# Design

## Context

引擎功能已在前两个 change 规划完毕；本 change 只做交付层：包元信息、文档、示例、Benchmark、CI 与构建产物。远端为 GitHub（`origin` → github.com/DaringWoo/chunkweave），CI 自然选 GitHub Actions。需求文档硬约束：不伪造作者身份、不编造性能数字、不实际上传 PyPI 或建远端 Release。

## Goals / Non-Goals

**Goals:**

- `pyproject.toml` 元信息完备，`python -m build` 产出合规 wheel/sdist。
- 文档树与 6 个示例与实际 API 一致且示例真实可跑。
- GitHub Actions CI 四步（ruff、mypy、pytest、build）与可重复 Benchmark。
- `IMPLEMENTATION_REPORT.md` 记录全部为真实执行数字。

**Non-Goals:**

- 上传 PyPI、远端 Release、版本号正式化之外的发布流程（如签名、可信发布 OIDC）。
- 引擎行为改动——发现缺陷修 bug 属于实现工作，不在此设计范围新增能力。

## Decisions

### 包元信息

`name = "chunkweave"`，`version = "0.1.0"`，`license` 引用既有 `LICENSE`（MIT，开工时核对全文确认）。`authors` 取 git `user.name`；无法确认则省略字段并在 ADR 记录，不留假名。Semantic 相关不设强制依赖；如提供便捷 Provider 适配器，放入 `extras`（如 `[project.optional-dependencies]`），核心保持零第三方运行时依赖（开发依赖放 `[dependency-groups]`/`optional` 测试组）。

### 文档语言与结构

README 英文为主、附中文概述段（PyPI 面向开源受众，且现有 README 已是英文）；`docs/` 正文英文，ADR 记此决定。ADR 至少覆盖：Python>=3.11、hatchling、分隔符归属默认值、`chunk_id` 顺序编号、Provider 协议形态、custom 近者优先继承。假设记录：若维护者偏好中文文档，后续版本可补中文版——本版不强求。

### 示例

`examples/` 每例一个独立脚本，顶部注释写明运行方式（`python examples/01_flat_sliding_window.py`）。Fake Provider 用确定性实现（如对两输入 token 集合算 Jaccard 相似度），保证无网络、可复现。示例输出打印切块数与首块摘要，人工可核验。

### Benchmark

`benchmarks/bench.py`：stdlib `timeit`/`perf_counter`，固定随机种子合成语料（可拼接真实样本文本），输出 JSON + 表格；环境信息（Python 版本、平台、CPU）与参数一并写入输出，结果抄入 `IMPLEMENTATION_REPORT.md`，不引用脚本外的数字。不用 `pytest-benchmark`：减少依赖，脚本足够可重复。

### CI

`.github/workflows/ci.yml`：push/PR 触发，matrix `python: [3.11, 3.12, 3.13]` on `ubuntu-latest`（Windows/macOS 由文档要求"跨平台"程度决定，首版 Linux 单平台足够——记录为已知限制），步骤：安装 → `ruff check` → `mypy src` → `pytest` → `python -m build` + `twine check`（twine 仅 CI 环境用）。全部步骤真实执行，不 `continue-on-error`。

### 本地安装验证

构建后做 `pip install dist/*.whl` 到临时 venv + `import` 冒烟 + `tar -tf`/`unzip -l` 检查产物内容（源码、LICENSE、README、METADATA）。安装说明写入 README。

## Risks / Trade-offs

- 文档与 API 漂移 → 示例脚本直接进 CI 运行（示例即可运行的文档一致性检查）。
- 作者字段难确认 → 宁可留空+ADR 记录，不编造。
- 单平台 CI 覆盖面有限 → 已知限制写入报告，matrix 留扩展位。
- Benchmark 数字随机波动 → 固定种子+多次取中位数，报告中标注为参考值而非承诺。

## Open Questions

- 无（README 中英取舍已按上述假设定案，可后续调整）。
