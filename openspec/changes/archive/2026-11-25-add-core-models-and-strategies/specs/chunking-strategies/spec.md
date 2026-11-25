# Spec Delta

## Purpose

定义三种切块策略（Sliding Window、Recursive、Semantic）的外部行为契约：参数语义、配置校验、边界与兜底行为，以及各策略产出的 Strategy Metadata。

## ADDED Requirements

### Requirement: Sliding Window 参数与校验

Sliding Window MUST 以 `chunk_size` 与 `overlap` 为核心参数（单位均为 Unicode 码点），校验 `chunk_size > 0` 且 `0 <= overlap < chunk_size`。`overlap = 0` 即固定长度切块，MUST NOT 另设 FixedSize 算法。

#### Scenario: overlap 为 0 等价固定长度

- **WHEN** 以 `overlap = 0` 对文本切块
- **THEN** 产生连续、互不重叠、长度不超过 `chunk_size` 的窗口

#### Scenario: 最大合法 overlap

- **WHEN** 以 `overlap = chunk_size - 1` 对文本切块
- **THEN** 窗口步长为 1，切块正常前进结束，不死循环

#### Scenario: 非法 overlap 报错

- **WHEN** `overlap < 0` 或 `overlap >= chunk_size`
- **THEN** 校验阶段抛出清晰异常，不产生任何 Chunk

### Requirement: 窗口推进与边界

窗口 MUST 始终向前推进，不产生死循环。文本短于或等于窗口时产出单个 Chunk；最后一个窗口允许短于 `chunk_size`；空文本产出空结果。`window_index` MUST 从 0 起编号；`overlap_size` 为该窗口与前一窗口的重叠码点数（首个窗口为 0，其余窗口等于 `overlap` 配置值）。

#### Scenario: 文本短于窗口

- **WHEN** 输入文本长度小于 `chunk_size`
- **THEN** 产出恰好一个覆盖全文的 Chunk，`window_index` 为 0、`overlap_size` 为 0

#### Scenario: 最后窗口与 Offset

- **WHEN** 文本长度不是窗口步长的整数倍
- **THEN** 最后一个 Chunk 覆盖到文本末尾且 Offset 正确，`content == text[start:end]`

### Requirement: Recursive 分隔符优先级

Recursive MUST 按分隔符列表的优先级逐级切分：先以最高优先级分隔符切分，结果仍超过 `chunk_size` 的片段 MUST 继续使用更细粒度分隔符，直至满足约束或到达兜底规则；不超过 `chunk_size` 的片段成为叶子片段。句子、段落、标题等切分 MUST 通过分隔符规则实现，不另设独立算法。

#### Scenario: 多级分隔符逐级切分

- **WHEN** 配置 `separators = ["\n\n", "\n", "。", ""]` 且 `chunk_size` 较小
- **THEN** 段落先用 `\n\n` 切分，超长片段再用 `\n`、再按句读切分，最终兜底按字符切分

#### Scenario: 正则分隔符

- **WHEN** 分隔符使用正则表达式（如标题模式）
- **THEN** 按正则匹配位置切分，匹配行为与优先级规则同字面量分隔符一致

### Requirement: Recursive 片段合并

Recursive MUST 将叶子片段按原文顺序贪心合并为最终 Chunk：从左到右累加相邻片段，合并后长度不超过 `chunk_size` 时并入当前块，否则开启新块；空片段 MUST NOT 产出 Chunk。

#### Scenario: 小片段贪心合并

- **WHEN** 分隔符切分得到多个不超过 `chunk_size` 的相邻片段
- **THEN** 相邻片段被贪心合并为更少的 Chunk，每个 Chunk 长度不超过 `chunk_size`

#### Scenario: 合并不超限

- **WHEN** 相邻片段合并后将超过 `chunk_size`
- **THEN** 该片段开启新块，不产生超限 Chunk

### Requirement: 分隔符保留与归属

Recursive MUST 明确定义分隔符的保留与归属规则，取值 `previous`（默认，分隔符保留并归属前一 Chunk）、`next`（归属后一 Chunk）、`none`（分隔符不保留，相邻 Chunk 间允许出现未覆盖间隙）。该规则 MUST 一致适用于字面量与正则分隔符（正则保留其匹配文本），且可通过配置调整。

#### Scenario: 分隔符归属前块

- **WHEN** 按 `"\n\n"` 切分段落且采用默认归属规则
- **THEN** 各 Chunk 保留其结尾分隔符，拼接结果可还原原文对应范围

#### Scenario: 分隔符丢弃产生间隙

- **WHEN** 配置 `keep_separator = "none"`
- **THEN** 分隔符不进入任何 Chunk，相邻 Chunk 的 Offset 之间存在未覆盖间隙，且每个 Chunk 仍满足 `content == text[start:end]`

### Requirement: Recursive 兜底与终止性

无匹配分隔符时 MUST 将文本作为整体或按长度约束兜底切分；空分隔符 MUST 作为最终兜底按字符切分；超过 `chunk_size` 且无法再分的原子片段 MUST 按长度强制切分；`separators` 为空列表时 MUST 仅按兜底规则切分。匹配空串的分隔符 MUST NOT 产生空切分或死循环；超过 `max_depth` 的剩余片段 MUST 按字符兜底。任何输入下 MUST NOT 出现无限递归或死循环。

#### Scenario: 超长原子片段强制切分

- **WHEN** 文本中存在无任何分隔符匹配且超过 `chunk_size` 的连续片段
- **THEN** 该片段被按 `chunk_size` 强制切分，不抛出异常也不死循环

#### Scenario: 空文本与无匹配

- **WHEN** 输入为空文本或所有分隔符均无匹配
- **THEN** 分别产出空结果或按约束切分的整体结果，过程正常终止

#### Scenario: 空匹配分隔符不死循环

- **WHEN** 正则分隔符可匹配空串（如 `x*`）
- **THEN** 引擎忽略空匹配或按兜底处理，切块正常终止

### Requirement: Recursive 必要 Overlap

Recursive MUST 支持可选的相邻块重叠参数 `overlap`（`>= 0`，码点），相邻 Chunk 在边界处保留指定长度的上下文；携带量 MUST 不超过前一块长度减一，且 MUST NOT 跨越 `keep_separator="none"` 产生的未覆盖间隙；不强制所有策略共享无意义参数。

#### Scenario: 相邻块重叠

- **WHEN** 配置 Recursive 的 overlap 参数
- **THEN** 相邻 Chunk 的内容在边界处重叠不超过指定长度，且各 Chunk Offset 正确

#### Scenario: 小块 overlap 钳制

- **WHEN** 前一块长度小于等于 `overlap`
- **THEN** 实际重叠被钳制，后块 `start_offset` 仍严格大于前块 `start_offset`，不产生逆序或重复起点

### Requirement: Recursive Strategy Metadata

每个 Recursive Chunk 的 Strategy Metadata MUST 含 `separator_used`（产生其内容的分隔符）与 `separator_level`（该分隔符在 `separators` 列表中的优先级序号，从 0 起）；合并产生的 Chunk MUST 记录其首个叶子片段的分隔符信息。

#### Scenario: 元数据记录分隔符

- **WHEN** Recursive 切块完成
- **THEN** 每个 Chunk 携带 `separator_used` 与 `separator_level`，可据此追溯其内容的切分粒度

### Requirement: Semantic Provider 注入协议

Semantic MUST 通过调用方注入的相似度/Embedding 协议计算语义边界。Provider MUST 实现轻量协议：对相邻两个语义单元计算相似度 `score(left, right)`，返回值 MUST 在 `[0,1]` 内且越大表示越相似；可选提供 `score_batch` 批量接口。协议 MUST 不绑定厂商或模型；未配置 Provider 时 MUST 抛出清晰异常；核心安装 MUST NOT 依赖大型模型库；内部临时向量 MUST NOT 作为检索向量暴露；Provider 实例不属于配置、不参与序列化。

#### Scenario: 未配置 Provider 报错

- **WHEN** 未注入 Provider 即执行 Semantic 切块
- **THEN** 抛出指明缺少 Provider 的清晰异常

#### Scenario: Provider 异常透传

- **WHEN** Provider 在计算相似度时抛出异常
- **THEN** 异常向上传播或包装为带上下文的清晰异常，不被静默吞掉

### Requirement: Semantic 边界判定与兜底

Semantic MUST 先将文本按 `unit_separators`（缺省为句读类分隔符）切分为语义单元（单元不再细分，单元序列覆盖全文无间隙），对相邻单元两两计算 `score`，在 `score < threshold` 处判定边界；`threshold` ∈ `[0,1]`，值越大切分越激进。当语义边界产生的块超过 `chunk_size` 上限时，MUST 以 `unit_separators` 经 Recursive 机制执行二次切分兜底，保证块长上限可靠。每个 Chunk 的 Strategy Metadata MUST 含 `boundary_score`：Chunk 起始边界为语义边界时记录对应分数，长度兜底产生的边界与结果首块为 `null`。

#### Scenario: 主题变化处切分

- **WHEN** 文本中相邻单元相似度在主题变化处低于 `threshold`
- **THEN** 在低相似度位置产生边界，`boundary_score` 记录触发分数

#### Scenario: 语义块超长兜底

- **WHEN** 某语义块长度超过 `chunk_size`
- **THEN** 该块被二次切分为满足长度上限的多个 Chunk，无任何 Chunk 超限

#### Scenario: 单元不足不评分

- **WHEN** 文本切分后不足两个语义单元（含空文本）
- **THEN** 不产生语义边界，整体作为单块（空文本产出空结果），超限时仍经兜底切分

### Requirement: 结果顺序与元数据归属

三种策略产出的 Chunk MUST 按原文顺序稳定排列，按 `start_offset` 严格递增；策略 MUST 只产出切分结果与各自的 Strategy Metadata，MUST NOT 设置 `parent_id`、`level`、`sequence` 等组织字段。

#### Scenario: 输出顺序稳定

- **WHEN** 同一输入重复切块
- **THEN** Chunk 顺序与内容完全一致，且按 `start_offset` 单调递增排列
