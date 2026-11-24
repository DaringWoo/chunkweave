# Spec Delta

## Purpose

定义三种切块策略（Sliding Window、Recursive、Semantic）的外部行为契约：参数语义、配置校验、边界与兜底行为，以及各策略产出的 Strategy Metadata。

## ADDED Requirements

### Requirement: Sliding Window 参数与校验

Sliding Window MUST 以 `chunk_size` 与 `overlap` 为核心参数，校验 `chunk_size > 0` 且 `0 <= overlap < chunk_size`。`overlap = 0` 即固定长度切块，MUST NOT 另设 FixedSize 算法。

#### Scenario: overlap 为 0 等价固定长度

- **WHEN** 以 `overlap = 0` 对文本切块
- **THEN** 产生连续、互不重叠、长度不超过 `chunk_size` 的窗口

#### Scenario: 非法 overlap 报错

- **WHEN** `overlap < 0` 或 `overlap >= chunk_size`
- **THEN** 校验阶段抛出清晰异常，不产生任何 Chunk

### Requirement: 窗口推进与边界

窗口 MUST 始终向前推进，不产生死循环。文本短于或等于窗口时产出单个 Chunk；最后一个窗口允许短于 `chunk_size`；空文本产出空结果。每个 Chunk 的 Strategy Metadata MUST 含 `window_index` 与 `overlap_size`。

#### Scenario: 文本短于窗口

- **WHEN** 输入文本长度小于 `chunk_size`
- **THEN** 产出恰好一个覆盖全文的 Chunk，`window_index` 为 0、`overlap_size` 为 0

#### Scenario: 最后窗口与 Offset

- **WHEN** 文本长度不是窗口步长的整数倍
- **THEN** 最后一个 Chunk 覆盖到文本末尾且 Offset 正确，`content == text[start:end]`

### Requirement: Recursive 分隔符优先级

Recursive MUST 按分隔符列表的优先级逐级切分：先以最高优先级分隔符切分，结果仍不满足长度约束的片段 MUST 继续使用更细粒度分隔符，直至满足约束或到达兜底规则。句子、段落、标题等切分 MUST 通过分隔符规则实现，不另设独立算法。

#### Scenario: 多级分隔符逐级切分

- **WHEN** 配置 `separators = ["\n\n", "\n", "。", ""]` 且 `chunk_size` 较小
- **THEN** 段落先用 `\n\n` 切分，超长片段再用 `\n`、再按句读切分，最终兜底按字符切分

#### Scenario: 正则分隔符

- **WHEN** 分隔符使用正则表达式（如标题模式）
- **THEN** 按正则匹配位置切分，匹配行为与优先级规则同普通字符串分隔符一致

### Requirement: 分隔符保留与归属

Recursive MUST 明确定义分隔符的保留与归属规则：默认分隔符保留在文本中并归属前一个 Chunk；该规则 MUST 一致适用于字符串与正则分隔符，且可通过配置调整。

#### Scenario: 分隔符归属前块

- **WHEN** 按 `"\n\n"` 切分段落且采用默认归属规则
- **THEN** 各 Chunk 保留其结尾分隔符，拼接结果可还原原文对应范围

### Requirement: Recursive 兜底与终止性

无匹配分隔符时 MUST 将文本作为整体或按长度约束兜底切分；空分隔符 MUST 作为最终兜底按字符切分；超过 `chunk_size` 且无法再分的原子片段 MUST 按长度强制切分。任何输入下 MUST NOT 出现无限递归或死循环。

#### Scenario: 超长原子片段强制切分

- **WHEN** 文本中存在无任何分隔符匹配且超过 `chunk_size` 的连续片段
- **THEN** 该片段被按 `chunk_size` 强制切分，不抛出异常也不死循环

#### Scenario: 空文本与无匹配

- **WHEN** 输入为空文本或所有分隔符均无匹配
- **THEN** 分别产出空结果或按约束切分的整体结果，过程正常终止

### Requirement: Recursive 必要 Overlap

Recursive MUST 支持可选的相邻块重叠参数，使相邻 Chunk 在边界处保留指定长度的上下文；不强制所有策略共享无意义参数。

#### Scenario: 相邻块重叠

- **WHEN** 配置 Recursive 的 overlap 参数
- **THEN** 相邻 Chunk 的内容在边界处重叠指定长度，且各 Chunk Offset 正确

### Requirement: Semantic Provider 注入协议

Semantic MUST 通过调用方注入的相似度/Embedding 协议计算语义边界，协议 MUST 轻量、不绑定厂商或模型；未配置 Provider 时 MUST 抛出清晰异常；核心安装 MUST NOT 依赖大型模型库，内部临时向量 MUST NOT 作为检索向量暴露。

#### Scenario: 未配置 Provider 报错

- **WHEN** 未注入 Provider 即执行 Semantic 切块
- **THEN** 抛出指明缺少 Provider 的清晰异常

#### Scenario: Provider 异常透传

- **WHEN** Provider 在计算相似度时抛出异常
- **THEN** 异常向上传播或包装为带上下文的清晰异常，不被静默吞掉

### Requirement: Semantic 边界判定与兜底

Semantic MUST 在相邻语义单元的相似度低于 `threshold` 处判定边界，`threshold` 的含义与取值域 MUST 明确。当语义边界产生的块超过最大长度约束时，MUST 执行二次切分兜底，保证块长上限可靠。每个 Chunk 的 Strategy Metadata MUST 含 `boundary_score`。

#### Scenario: 主题变化处切分

- **WHEN** 文本中相邻单元相似度在主题变化处低于 `threshold`
- **THEN** 在低相似度位置产生边界，`boundary_score` 记录触发分数

#### Scenario: 语义块超长兜底

- **WHEN** 某语义块长度超过最大长度约束
- **THEN** 该块被二次切分为满足长度上限的多个 Chunk，无任何 Chunk 超限

### Requirement: 结果顺序与元数据归属

三种策略产出的 Chunk MUST 按原文顺序稳定排列；策略 MUST 只产出切分结果与各自的 Strategy Metadata，MUST NOT 设置 `parent_id`、`level`、`sequence` 等组织字段。

#### Scenario: 输出顺序稳定

- **WHEN** 同一输入重复切块
- **THEN** Chunk 顺序与内容完全一致，且按 `start_offset` 单调递增排列
