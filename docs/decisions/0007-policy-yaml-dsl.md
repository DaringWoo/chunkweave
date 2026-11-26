# ADR 0007: Policy YAML DSL

**Status:** accepted · **Date:** 2026-11-26

## Context

旧配置有 Flat/Hierarchical 两种组织类型与 dict/dataclass 两种传递形式，
无法版本化，也无法在执行期追溯配置来源。需要一种可声明、可校验、
可追溯的配置形式。

## Decision

引入 YAML Policy DSL：`api_version`（固定 `chunkweave/v1`）、`policy`
身份信息（`id`/`name`/`version`，`MAJOR.MINOR.PATCH`）、`pipeline.levels`
（`name`/`strategy`/`params`，非空列表，一层即平铺、多层即层级）与
`metadata`（`fields` + `include`）。`Policy.from_file`/`from_yaml` 经
`yaml.safe_load` 加载；结构校验由 Pydantic 模型完成，未知字段严格
拒绝。Flat/Hierarchical 组织类型删除，统一为层级列表语义。

Rejected: 保留 dict 形式作为第二入口——双配置面会重演旧问题；
`execute` 对非 `Policy` 参数直接 `TypeError`。

## Consequences

- 配置可版本化、可哈希（见 ADR 0008）、可静态校验。
- YAML 隐式类型成为用户面坑点，已在 configuration.md 中提醒。
