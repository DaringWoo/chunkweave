# ADR 0009: 未知字段严格拒绝

**Status:** accepted · **Date:** 2026-11-26

## Context

静默忽略未知字段会让拼写错误（如 `chunkSize`、`overlaP`）悄悄变成
"参数没生效"，且违背 Policy 作为严格契约的定位。

## Decision

Policy 全部模型 `extra="forbid"`：顶层、`policy`、`pipeline`、每个
level、`metadata`、`metadata.include`、每个字段配置（仅 `value`/
`source`）。`params` 内的未知键由对应策略的参数 Schema 拒绝；
`value` 的内容不受未知字段约束（它本就是自由值）。错误统一为
`PolicyValidationError`，`path` 精确到出错位置（如
`pipeline.levels[1].params.overlap`）。

## Consequences

- 拼错参数立即报带路径的错误，调试成本低。
- Schema 演进即公共契约演进：新增合法键需要升级参数模型。
