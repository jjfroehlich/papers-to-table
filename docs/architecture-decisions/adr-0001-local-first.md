# ADR-0001: local-first main app

- Status: Accepted
- Date: 2026-04-21

## Decision

The main app remains local-first by default, with LM Studio as the primary live provider path.

## Why

- operator trust depends on visible local execution and explicit readiness failures
- the repo’s product direction centers on browser review over locally owned artifacts
- downstream tools already consume filesystem outputs directly

## Consequences

- docs, tests, and UI must treat local-first as the happy path
- optional cloud providers stay behind the same contracts and must not weaken the local path
