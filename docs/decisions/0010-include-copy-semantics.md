# ADR 0010: include 复制语义与保留键

**Status:** accepted · **Date:** 2026-11-26

## Context

`metadata.include` 的语义在候选方案间徘徊：关闭时隐藏 Chunk 属性，
还是仅控制保留键是否进入业务 `metadata`。同时需要防止业务字段与
系统字段同名造成歧义。

## Decision

- include 是复制语义：`include.organization` 控制 `parent_id`/`level`/
  `sequence`/`level_name` 四键，`include.strategy` 控制 `strategy`/
  `strategy_metadata` 两键是否复制进每个 Chunk 的 `metadata`（独立
  副本）；缺省均 `true`。
- Chunk 属性（含 `strategy_metadata`）无论开关始终完整，属性是系统
  契约，不被输出选项破坏。
- `metadata.fields` 字段名不得使用保留键（`chunk_id`/`content`/
  `parent_id`/`level`/`sequence`/`start_offset`/`end_offset`/
  `strategy`/`strategy_metadata`/`metadata`/`level_name`），与 include
  开关无关，加载时即拒绝。

Rejected: 关闭时清空 `strategy_metadata` 属性——破坏系统契约，且
向量化场景下策略信息无处存放。

## Consequences

- 向量库只存 `metadata` 的用法天然可用（副本进入过滤面）。
- 每个 Chunk 持有独立深拷贝，存在一个 deepcopy/块的运行时成本。
