# Proposal

## Why

`docs/autonomous_chunking_engine_agent_prompt.md` 定义了一个独立 Python 文本切块引擎的产品模型：切块策略（Chunking Strategy）与组织方式（Organization）两个维度解耦、可组合。本 change 是该引擎三个规划变更中的第一个，负责打下核心地基——数据模型、配置校验、策略接口与三种切块算法，使后续组织层（Flat/Hierarchical）有稳定、可测试的构建块可用。

## What Changes

- 建立包的骨架与公共数据模型：`Chunk` 统一结果模型（`chunk_id`、`content`、`start_offset`、`end_offset`），Offset 采用 Unicode 码点索引、左闭右开区间 `[start, end)`，并相对稳定于"最初输入文本"的语义预留。
- 建立四组元数据模型：`Metadata = Common + Organization + Strategy + Custom`；本 change 实现 Common、Strategy、Custom 三组以及 Organization 组的字段约定（`parent_id`、`level`、`sequence` 的表示与取值规则），组织字段的赋值由后续组织层完成。
- 实现 Flat/Hierarchical 配置模型与三种策略配置（`sliding_window`、`recursive`、`semantic`），非法配置快速失败。
- 定义策略协议（Base Protocol/ABC）：策略只产出切分结果与 Strategy Metadata，不设置 `parent_id`、`level` 等组织字段。
- 实现 Strategy Registry：注册内置三种策略、支持用户注册自定义 Chunker、未注册策略与名称冲突给出清晰行为。
- 实现三种切块算法：
  - Sliding Window：`chunk_size` + `overlap`，`overlap = 0` 即固定长度切块（不另设 FixedSize），校验 `0 <= overlap < chunk_size`，保证窗口始终前进。
  - Recursive：按分隔符优先级逐级切分，支持普通字符串与正则分隔符、长度约束、必要 overlap、分隔符保留/归属规则、无匹配与超长原子片段兜底，禁止死循环；句子/段落/标题切分一律通过分隔符规则实现，不另设 Sentence/Paragraph/Structural 算法。
  - Semantic：通过注入的相似度/Embedding 协议判断边界；定义轻量 Provider 协议，`threshold`、最大长度约束与超长二次切分兜底；不绑定厂商、不强制下载模型、核心安装不依赖大型模型库；临时向量不作检索向量。
- 配置与结果序列化（JSON）稳定。
- 职责边界：本 change 不含 Flat/Hierarchical 组织执行、公共入口 API、文档/打包/CI（属于后续 change）。

## Capabilities

### New Capabilities

- `chunk-model`: Chunk 统一结果模型、Offset 语义、四组元数据模型（含 Custom 元数据的继承与保留字段冲突规则）、配置模型与序列化。
- `chunking-strategies`: 三种切块算法（Sliding Window、Recursive、Semantic）的行为约定、参数校验、边界与兜底行为、Strategy Metadata 产出。
- `strategy-registry`: 策略协议契约、内置策略注册、自定义 Chunker 注册、未注册与命名冲突行为。

### Modified Capabilities

（无——绿地项目，无存量的 `openspec/specs/` 能力规格。）

## Impact

- 新增 Python 包源码（建议顶层包名 `chunkweave`）、`pyproject.toml`（`requires-python >= 3.11`）、pytest 测试套件。
- 核心依赖保持轻量；Semantic Provider 通过注入协议解耦，不引入模型库依赖。
- 为后续 `add-organization-and-api`、`add-packaging-and-release` 两个 change 提供基础。
- 对外影响：尚无发布物；不上传 PyPI、不创建远端 Release。
- 依据文档：`docs/autonomous_chunking_engine_agent_prompt.md`（产品模型约束，不得扩大职责）。
