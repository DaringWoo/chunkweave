# ADR 0005: custom metadata inheritance

**Status:** accepted · **Date:** 2026-11-25

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
