# ADR-0003: filesystem artifacts as the canonical cross-tool boundary

- Status: Accepted
- Date: 2026-04-21

## Decision

The main app, eval, and optimizer integrate through persisted filesystem artifacts rather than runtime imports.

## Why

- the tools remain separate runtimes
- run bundles are easier to inspect, diff, archive, and score independently
- downstream tools should not depend on main-app runtime internals

## Consequences

- shared contracts live in `specs/contracts/`
- run-bundle compatibility matters more than in-process convenience
- UI helper artifacts such as lookup indexes may exist, but canonical streams stay published in the run bundle
