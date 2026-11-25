# Proposal

## Why

`docs/autonomous_chunking_engine_agent_prompt.md` 定义了一个独立 Python 文本切块引擎的产品模型：切块策略（Chunking Strategy）与组织方式（Organization）两个维度解耦、可组合。本 change 是该引擎三个规划变更中的第一个，负责打下核心地基——数据模型、配置校验、策略接口与三种切块算法，使后续组织层（Flat/Hierarchical）有稳定、可测试的构建块可用。

## What Changes

- 建立包的骨架与公共数据模型：`Chunk` 统一结果模型（`chunk_id`、`content`、`start_offset`、`end_offset`），Offset 采用 Unicode 码点索引、左闭右开区间 `[start, end)`，所有长度参数同以码点计；Offset 相对本次切块调用的输入文本并为层级全局换算预留；`chunk_id` 在单次切块调用产出集合内唯一且确定性生成。
- 建立四组元数据模型：`Metadata = Common + Organization + Strategy + Custom`；本 change 实现 Common、Strategy、Custom 三组以及 Organization 组的字段名约定（`parent_id`、`level`、`sequence`），组织字段的赋值与取值约定由后续组织层完成；每个策略声明 `metadata_keys`，Custom 经组装机制逐 Chunk 深拷贝附加、保留字段冲突抛 `MetadataConflictError`。
- 实现策略配置模型（字段名构成序列化契约）与 Flat/Hierarchical 配置模型，非法配置快速失败；Recursive 分隔符支持字面量字符串与正则表达式（`str`/`re.Pattern`，JSON 序列化为无损标签形式）。
- 定义策略协议（Protocol）：`chunk(text)` + `metadata_keys` 声明，策略只产出切分结果与 Strategy Metadata，不设置 `parent_id`、`level` 等组织字段。
- 实现 Strategy Registry：注册内置三种策略、支持用户注册自定义 Chunker、未注册策略与名称冲突给出清晰行为。
- 实现三种切块算法：
  - Sliding Window：`chunk_size` + `overlap`（码点），`overlap = 0` 即固定长度切块（不另设 FixedSize），校验 `0 <= overlap < chunk_size`，保证窗口始终前进。
  - Recursive：按分隔符优先级逐级切分产出叶子片段，再按原文顺序贪心合并至 `chunk_size`；支持字面量/正则分隔符、`keep_separator` 三态归属（`none` 允许未覆盖间隙）、长度约束、overlap（钳制保证 `start_offset` 严格递增）、空匹配与超长原子片段兜底，禁止死循环；句子/段落/标题切分一律通过分隔符规则实现，不另设 Sentence/Paragraph/Structural 算法。
  - Semantic：通过注入的 Provider 协议对相邻语义单元两两评分（`score(left, right)` 返回 `[0,1]` 相似度，`score < threshold` 成边界）；语义单元经 `unit_separators` 切分；块长受 `chunk_size` 约束、超长块以 `unit_separators` 兜底二次切分；`boundary_score` 记录边界分数；不绑定厂商、不强制下载模型、核心安装不依赖大型模型库；临时向量不作检索向量。
- 配置与结果序列化（JSON）稳定，四组元数据边界保留。
- 职责边界：本 change 不含 Flat/Hierarchical 组织执行、公共入口 API、文档/打包/CI（属于后续 change）。

## Capabilities

### New Capabilities

- `chunk-model`: Chunk 统一结果模型、Offset 与码点长度单位语义、四组元数据模型（含 `metadata_keys` 声明、Custom 组装与保留字段冲突规则）、配置字段契约与序列化。
- `chunking-strategies`: 三种切块算法（Sliding Window、Recursive 含贪心合并、Semantic 含语义单元与 Provider 协议）的行为约定、参数校验、边界与兜底行为、Strategy Metadata 产出。
- `strategy-registry`: 策略协议契约（含 `metadata_keys` 声明）、内置策略注册、自定义 Chunker 注册、未注册与命名冲突行为。

### Modified Capabilities

（无——绿地项目，无存量的 `openspec/specs/` 能力规格。）

## Impact

- 新增 Python 包源码（建议顶层包名 `chunkweave`）、`pyproject.toml`（`requires-python >= 3.11`）、pytest 测试套件。
- 核心依赖保持轻量；Semantic Provider 通过注入协议解耦，不引入模型库依赖。
- 为后续 `add-organization-and-api`、`add-packaging-and-release` 两个 change 提供基础。
- 对外影响：尚无发布物；不上传 PyPI、不创建远端 Release。
- 依据文档：`docs/autonomous_chunking_engine_agent_prompt.md`（产品模型约束，不得扩大职责）。
