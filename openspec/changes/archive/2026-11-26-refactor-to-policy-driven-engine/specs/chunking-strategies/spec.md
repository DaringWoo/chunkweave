# Spec Delta

## MODIFIED Requirements

### Requirement: Semantic Provider 注入协议

Semantic MUST 通过调用方注入的相似度/Embedding 协议计算语义边界。Provider MUST 实现轻量协议：对相邻两个语义单元计算相似度 `score(left, right)`，返回值 MUST 在 `[0,1]` 内且越大表示越相似；可选提供 `score_batch` 批量接口。协议 MUST 不绑定厂商或模型；执行含 `semantic` 层的 Policy 而未通过 `execute(provider=...)` 提供 Provider 时，MUST 在任何切块开始前抛出清晰异常；核心安装 MUST NOT 依赖大型模型库；内部临时向量 MUST NOT 作为检索向量暴露；Provider 实例 MUST NOT 写入 Policy、进入 Execution IR 或参与序列化。

#### Scenario: 未配置 Provider 报错

- **WHEN** 执行含 `semantic` 层的 Policy 而未通过 `execute(provider=...)` 提供 Provider
- **THEN** 在任何切块开始前抛出指明缺少 Provider 的清晰异常

#### Scenario: Provider 异常透传

- **WHEN** Provider 在计算相似度时抛出异常
- **THEN** 异常向上传播或包装为带上下文的清晰异常，不被静默吞掉

### Requirement: 结果顺序与元数据归属

三种策略 MUST 产出按原文顺序稳定排列、相对其输入文本 `start_offset` 严格递增的 ChunkSpan 序列；每个 ChunkSpan 只含片段文本、相对其输入文本的 `start_offset`/`end_offset` 与 `strategy_metadata`；策略 MUST NOT 决定 `chunk_id`、`parent_id`、`level`、`sequence` 或业务 `metadata`。

#### Scenario: 输出顺序稳定

- **WHEN** 同一输入重复切块
- **THEN** ChunkSpan 顺序与内容完全一致，且按 `start_offset` 单调递增排列
