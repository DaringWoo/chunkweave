# ADR 0008: Policy Hash 规范化

**Status:** accepted · **Date:** 2026-11-26

## Context

执行结果需要声明"是按哪份 Policy 跑的"：要求等价 YAML（键顺序、
空白、注释、引号风格不同）得到相同 Hash，任一声明值变化得到不同
Hash，且与 Context、text、Provider、Registry 无关。

## Decision

对 `policy.model_dump(mode="json")` 规范化（`sort_keys`、
`ensure_ascii=False`、紧凑分隔符）→ UTF-8 → sha256，输出
`sha256:<64 hex>`。规范化只含 Policy 模型的结构缺省值，不含编译期由
参数 Schema 补全的 `params` 缺省值，因此 Hash 不依赖 Registry。
`MetadataFieldConfig` 自定义序列化只输出实际声明的来源键，使
`{"value": null}` 与 `{"source": ...}` 可区分。

Rejected: 对原始 YAML 文本做 Hash——等价文本会得到不同 Hash。

## Consequences

- `policy_hash` 可比较两个 Policy 声明是否一致，进入 `ChunkResult`
  追溯字段。
- 未来修改 Policy 模型结构缺省值需评估 Hash 兼容性。
