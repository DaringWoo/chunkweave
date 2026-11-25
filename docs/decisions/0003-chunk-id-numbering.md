# ADR 0003: chunk_id numbering

**Status:** accepted · **Date:** 2026-11-25

## Context

`chunk_id` must be unique within one result set and deterministic for the
same input and config. In hierarchical mode the same `content`+offset pair
can occur under different parents (parent overlap), so a content hash can
collide.

## Decision

Sequential numbering `chunk-0000`, `chunk-0001`, … over the call's output.
Strategies number their own output; the hierarchical executor renumbers the
whole result breadth-first so parent ids assigned during descent stay
consistent.

Hierarchy information lives in `parent_id`/`level`/`sequence`, not encoded
in `chunk_id` — one source of truth.

## Consequences

- Deterministic, trivially unique; ids are not content-addressable (a
  documented limitation).
