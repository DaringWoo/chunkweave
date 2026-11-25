# ADR 0001: Python >= 3.11, hatchling build backend

**Status:** accepted · **Date:** 2026-11-25

## Context

Greenfield library; no existing toolchain constraints. Need a broadly
available baseline that supports modern typing (`X | Y`, `itertools.pairwise`)
and a low-friction build backend.

## Decision

`requires-python = ">=3.11"`, CI matrix 3.11–3.13. Build backend `hatchling`
with a `src/` layout.

## Consequences

- `match`/`pairwise`/`Self`-era typing available; users on <3.11 are excluded.
- Hatchling needs zero config for src-layout beyond the packages line;
  `setuptools` was rejected for more verbose config, Poetry/PDM for pulling
  in a workflow tool.
