# ADR 0005: custom metadata inheritance

**Status:** superseded by 0010 · **Date:** 2026-11-25

> custom 继承与保留键冲突规则已由 `metadata.fields` 声明式来源与
> ADR 0010 的 include 复制语义、保留键校验替代。

## Context

In hierarchical mode custom metadata must flow to descendants with defined
conflict semantics, and reserved fields must be protected from silent
overwrites.

## Decision

- Engine-level `custom` applies to every chunk at every level.
- A level's `metadata` applies to its own chunks and is inherited by all
  descendants; on key conflicts the nearer level wins, and every level
  overrides the engine-level custom.
- Reserved fields = common names ∪ `{"parent_id","level","sequence"}` ∪ the
  producing strategy's `metadata_keys`. Any collision in the merged key set
  that would land on a level's chunks raises `MetadataConflictError` before
  execution starts.
- Every chunk receives an independent `deepcopy` — no shared mutable dicts.

Rejected: custom only on leaves — the document requires inheritance to
children, and carrying it on all chunks is more predictable.

## Consequences

- Deep-copy cost is paid once per assembly; correctness over micro-optimizing.
- Config-time (pre-execution) rejection, not silent override.
