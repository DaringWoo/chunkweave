# ADR 0011: Provider 按次注入与 requires_provider

**Status:** accepted · **Date:** 2026-11-26

## Context

旧 API 用引擎级 `set_provider()` 注入语义 Provider：可变全局状态、
与序列化契约纠缠（Provider 不能出现在配置/结果里），且"缺 Provider"
错误要到层执行时才出现，可能已产生部分切块。

## Decision

- Provider 按次注入：`execute(text, policy, context=None, provider=None)`，
  引擎不再持有 Provider；`set_provider` 删除。
- 策略在注册时声明 `requires_provider`（`StrategySpec` 布尔字段），
  编译进 `PlanLevel.requires_provider`（IR 中的布尔声明，非实例）。
  `execute` 在编译后、切块前检查：任一 `requires_provider` 层缺
  Provider 立即 `ProviderMissingError`。
- Provider 不进入 Policy、IR 与序列化结果；Provider 协议本身
  （`score`/可选 `score_batch`）不变。

## Consequences

- 无引擎级可变状态，Provider 边界清晰；不同次执行可用不同 Provider。
- "缺 Provider"是 fail-fast 校验错误，不会留下部分切块。
