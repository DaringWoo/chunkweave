# ADR 0006: Flat is not single-level Hierarchical

**Status:** accepted · **Date:** 2026-11-25

## Context

Flat could theoretically reuse the hierarchical executor with one level, but
the spec forbids meaningless hierarchy fields on flat output while the
hierarchical executor always writes `level`/`parent_id`/`sequence`.

## Decision

`FlatOrganization` calls the strategy and assembles metadata directly,
skipping organization-field writes. `HierarchicalOrganization` owns all
hierarchy semantics.

## Consequences

- Clean flat output (`organization` group stays empty) and a single place
  that owns parent-child logic, at the price of one small extra executor.
