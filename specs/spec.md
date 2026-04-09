# Extract Structured Info from Papers Optimizer - spec.md

## Purpose

This repository provides a CLI-first optimizer that evaluates bounded candidate bundles for `extract-structured-info-from-papers` using `extract-structured-info-from-papers-eval`.

It is intentionally orchestration-only:

- main app = execution
- eval app = scoring
- optimizer = orchestration and tracking

## Product behavior

The optimizer must:

1. Support explicit `compare` and `optimize` study modes.
2. Support a fast explicit preflight that validates config, paths, prompt bundles, metric mappings, and launch wiring without running a study.
3. Launch the main app through a stable automation entrypoint.
4. Launch the eval app through a stable automation entrypoint.
5. Record candidate-level machine-readable artifacts and summaries.
6. Preserve immutable candidate bundles with reproducible metadata.
7. Keep dev and holdout behavior separate.
8. Apply deterministic-first behavior by default.

## Study modes

### compare

`compare` evaluates a fixed explicit candidate set on a dev benchmark and reports ranked comparative results.

- No iterative promotion loop is required.
- Candidate records still include decision fields and provenance.
- Holdout checks are optional and post-dev-ranking.

### optimize

`optimize` runs a bounded incumbent-challenger loop on a dev benchmark.

Loop shape:

1. start from baseline candidate
2. propose deterministic bounded challengers
3. run main app and eval app for challengers
4. apply gated acceptance policy
5. promote a challenger only if gates pass
6. persist results, round summaries, best-candidate state, and plots

Deterministic bounded challengers must cover the configured search surface more truthfully than a single-axis-only numeric mutation policy. The optimizer may stay bounded and reproducible, but it should not systematically ignore multi-knob combinations within the approved search space.

## Benchmark policy

The optimizer supports named benchmark splits such as `smoke`, `dev`, and `holdout`.

Behavior requirements:

- `dev` drives comparison and optimization decisions.
- `holdout` is not used as the main search benchmark.
- `dev` and `holdout` must remain distinct when both are configured.
- `optimize` holdout validates the final optimizer recommendation after dev-loop search.
- `compare` holdout may validate top-k candidates after dev ranking.

## Candidate bundle contract

Each candidate bundle is immutable and candidate-specific.

Minimum required fields:

- candidate id
- parent candidate id (nullable)
- round index (nullable in compare)
- benchmark id
- prompt bundle id
- text model id
- optional vision model id
- optimizer-controlled knob values
- candidate hash

## Acceptance contract

Promotion decisions are gated, not single-scalar.

- Primary metric: required optimization target.
- Guardrail metrics: hard limits and/or delta constraints.
- Deterministic checks: required artifacts and successful stage completion.
- Diagnostic metrics: explanatory only.

Decisions must be persisted with explicit reason text.

Compare and optimize flows must also fail gracefully when no candidate completes successfully or no winner can be materialized. Those cases should produce explicit experiment-level failure or no-winner summaries rather than file-not-found crashes.

## Artifact contract

The optimizer writes experiment-owned artifacts to disk.

Minimum required outputs:

- `experiment.json`
- `compare_summary.json` for compare studies
- `summary.json`
- `candidates/<candidate_id>/candidate.json`
- `results/results.csv`
- `results/results.jsonl`
- `results/candidate_diagnostics.csv` for compare studies
- `plots/*.csv`
- `plots/*.png`
- `best_candidate.json` when a winner/incumbent is tracked
- `rounds/round_<n>.json` for optimize rounds

Candidate result records must include:

- schema version, experiment id, study type
- candidate lineage and identity fields
- benchmark id
- primary, guardrail, and diagnostic metrics
- runtime/timing fields
- decision and reason
- main-app run reference
- eval-output reference

Compare-study operator artifacts must also make unscored candidates explicit rather than silently dropping them from summaries or plots.

## Non-goals

The optimizer does not:

- edit code in any repository
- reimplement extraction logic
- reimplement eval scoring logic
- mutate eval metric definitions in-loop
- mutate benchmark definitions in-loop
- run open-ended autonomous agent loops
- provide a UI as an MVP requirement

## Acceptance criteria

A normal operator can:

1. run a fast `preflight` and catch wiring or contract problems before launching a study
2. run `compare` on explicit candidates and inspect ranked outputs
3. run bounded `optimize` rounds from a baseline candidate
4. inspect candidate-level JSONL/CSV artifacts and decision reasons
5. inspect current best-candidate state when a winner exists, or explicit no-winner artifacts when one does not
6. run holdout validation according to mode policy
7. regenerate summaries and plots from saved artifacts
