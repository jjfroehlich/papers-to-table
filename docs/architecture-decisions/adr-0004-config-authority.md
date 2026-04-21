# ADR-0004: config file remains the authoritative advanced-control surface

- Status: Accepted
- Date: 2026-04-21

## Decision

The JSON config file remains the authoritative advanced-control surface, while the browser UI focuses on launch, preflight clarity, review, and export.

## Why

- reproducibility and provider/config parity depend on one explicit advanced-control surface
- the UI should help operators understand resolved context without becoming a sprawling settings editor
- tooling and automation already depend on stable config semantics

## Consequences

- the UI may expose narrow overrides and staged handles, but not broad duplicated settings
- preflight must show the resolved config consequences clearly before launch
- docs and tests must keep config semantics aligned across runtime and UI summaries
