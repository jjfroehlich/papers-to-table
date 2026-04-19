# Optimizer Candidate Contract

## Purpose

This file defines the shared optimizer-owned contract for candidate bundles, candidate results, and decision records.

## Candidate bundle rules

Each candidate bundle is immutable and candidate-specific.

Minimum required fields include:

- candidate id
- parent candidate id when applicable
- round index when applicable
- benchmark id
- prompt bundle id
- text model id
- optional vision model id
- optimizer-controlled knob values
- candidate hash

## Result-record rules

Candidate result records must include:

- schema version
- experiment id and study type
- candidate identity and lineage
- benchmark id
- primary, guardrail, and diagnostic metrics
- runtime or timing fields
- decision and reason
- main-app run reference
- eval-output reference
- explicit scored, degraded-score, unscored, or failed state

## Acceptance and winner semantics

Promotion decisions are gated rather than single-scalar only.

The optimizer must distinguish, when needed:

- best raw completed candidate
- eligible winner under configured gates and degraded-score policy
- provisional winner when a raw leader exists but is not yet eligible for promotion or materialization

Tie handling within an epsilon may use ordered secondary objectives only after deterministic and guardrail gates pass.

## Experiment-state rules

Interrupted studies must still leave truthful current-state artifacts on disk, including explicit no-winner or failed-study summaries when applicable.

## Ownership boundary

This file owns optimizer candidate, result, and decision semantics.

Shared scorer outputs consumed by those records belong in `eval-summary.md`.