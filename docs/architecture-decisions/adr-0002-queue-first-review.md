# ADR-0002: queue-first review workspace

- Status: Accepted
- Date: 2026-04-21

## Decision

The review UI remains queue-first rather than becoming a freeform document exploration tool.

## Why

- the reviewer’s job is deciding whether proposed spreadsheet updates are supported
- sustained curation depends on fast sequential review and explicit decision state
- diagnostics still matter, but they should not dominate the main evidence flow

## Consequences

- actionable proposals stay central
- unresolved diagnostics live in a dedicated diagnostics surface
- review summaries distinguish actionable work from broader diagnostic outcomes
