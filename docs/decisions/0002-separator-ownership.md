# ADR 0002: keep_separator — separator ownership in recursive chunking

**Status:** accepted · **Date:** 2026-11-25

## Context

When recursive splitting hits a separator, its text must go somewhere:
previous chunk, next chunk, or nowhere. The requirement document demands an
explicit, configurable rule covering literals and regexes.

## Decision

`keep_separator` tri-state:

- `"previous"` (default): match text is appended to the preceding piece;
  concatenating chunks restores the source span.
- `"next"`: match text starts the following piece (heading-style splits).
- `"none"`: match text is dropped; adjacent chunks have uncovered gaps, and
  the gap can never be crossed by merge or overlap.

Ownership is decided at leaf-splitting time; merging only concatenates
adjacent leaves and never spans a `"none"` gap.

## Consequences

- Predictable round-trip for `previous`/`next`; `none` accepts gaps as an
  explicit trade-off.
- Regex separators keep their matched text per occurrence.
