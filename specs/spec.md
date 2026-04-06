# Extract Structured Info from Papers Optimizer - spec.md

## Status

Initial product specification for a separate CLI-first optimizer repository.

## Purpose

This repository optimizes prompt, model, and bounded configuration bundles for `extract-structured-info-from-papers` by repeatedly running the main app on a fixed benchmark and scoring the resulting runs with `extract-structured-info-from-papers-eval`.

The optimizer is intentionally narrow. It is an orchestration harness over an explicit search surface, not a self-modifying agent, not an autonomous software-engineering loop, and not a general benchmark platform.

---

## Product summary

The optimizer should:

1. start from a baseline candidate bundle
2. generate a small batch of candidate variants from a bounded search surface
3. run the main app on a fixed dev benchmark through a stable automation entrypoint
4. run the eval app on the produced runs through a stable automation entrypoint
5. compare candidate scores using a gated acceptance rule
6. promote the winner only if it satisfies the acceptance rule
7. record machine-readable artifacts, logs, and plots for every round
8. repeat for a fixed number of rounds
9. validate the promoted best candidate on holdout outside the main search loop

Conceptually, the loop is:

propose -> run main app -> run eval app -> score -> log -> plot -> keep winner -> repeat

---

## Goals

- Improve extraction quality through benchmark-driven iteration on prompt, model, and bounded config variants.
- Keep the optimizer deterministic-first, inspectable, and reproducible.
- Preserve a strict separation of concerns:
  - main app = execution
  - eval app = scoring
  - optimizer = orchestration and tracking
- Support small realistic benchmarks that can finish in bounded time on local hardware.
- Preserve candidate lineage, hashes, and result history for later audit.
- Support dev-set optimization plus separate holdout validation.

## Non-goals

- Editing source code in the main app, eval app, or optimizer during optimization.
- Redefining eval metrics or mutating eval policy inside the optimizer loop.
- Mutating the runtime contracts or architecture of the main app or eval app.
- Broad autonomous prompt rewriting as the MVP baseline.
- Unrestricted config mutation across the full main-app config surface.
- UI work, PR creation, or agent-framework features for MVP.
- Re-implementing extraction logic or scoring logic inside the optimizer.

---

## MVP decisions

### A. Deterministic-first MVP

The first shipping optimizer must be deterministic-first by default.

That means:

- the optimizer operates on explicit prompt, model, and config variants
- code mutation is out of scope
- eval-definition mutation is out of scope
- unrestricted LLM-driven prompt rewriting is deferred
- any later LLM-based proposer must remain optional, bounded, and auditable

### B. Explicit and bounded search surface

The MVP search surface must stay small and explicit.

The initial search surface may include:

- prompt bundle variants
- text model identity
- optional vision model identity when relevant
- a few bounded numeric knobs such as:
  - retrieval top-k
  - rescue-related settings
  - evidence or support thresholds
  - a small number of other clearly useful extraction or retrieval knobs

The MVP must not expose a broad free-form config mutation surface.

### C. Mandatory dev versus holdout split

The optimizer must support at least:

- a dev benchmark used for search
- a holdout benchmark used only for final or periodic validation

An optional smoke benchmark may also be supported for fast preflight checks.

The holdout set must not participate in the main search loop.

### D. Gated acceptance rule

Promotion must not rely on one blind scalar score.

A candidate is only promotable when it:

- improves the configured primary correctness metric or main score on the dev benchmark
- stays within guardrail limits for evidence quality
- stays within runtime limits or acceptable runtime deltas
- does not create excessive null, abstention, or failure behavior
- passes required deterministic checks

Primary metrics, guardrail metrics, and diagnostic metrics must remain distinct.

### E. Orchestration-only responsibility

The optimizer must orchestrate the other repos rather than duplicating them.

- The main app executes extraction runs.
- The eval app scores those runs.
- The optimizer launches, compares, records, and promotes.

### F. Immutable and auditable candidate bundles

The optimizer must never mutate the live baseline in place.

Each candidate must have an explicit immutable bundle or candidate directory that records:

- candidate id
- parent or lineage information
- prompt bundle identity and snapshot or hash
- selected model identities
- selected config overlay
- benchmark identity
- relevant hashes and metadata for reproducibility

### G. CLI-first MVP

The optimizer is CLI-first in MVP.

It must support simple commands for:

- optimize
- evaluate a candidate bundle
- validate the current best on holdout
- summarize results

No UI is required in MVP.

---

## Relationship to the main app

The optimizer treats `extract-structured-info-from-papers` as the execution engine.

The optimizer must not duplicate extraction logic.

The optimizer should call the main app through a stable automation surface such as:

- a CLI entrypoint
- a stable API entrypoint
- another explicit automation entrypoint that is published for tooling use

The optimizer is designed against the current main-app product direction:

- local-first operation
- config-authoritative runtime behavior
- filesystem artifact bundles
- eval-mode-compatible run paths
- prompt identity and run metadata persisted in artifacts
- stable output artifacts and summaries
- no database dependency required for MVP orchestration

If the main app needs small contract improvements to support optimization cleanly, those improvements should happen in the main app rather than being reverse-engineered inside the optimizer.

---

## Relationship to the eval app

The optimizer treats `extract-structured-info-from-papers-eval` as the scoring oracle.

The optimizer must not duplicate scoring logic.

The optimizer should consume machine-readable eval outputs such as:

- per-run summary metrics
- per-cell or per-field scored details when needed for diagnostics
- stable metric names and categories

The optimizer assumes scoring belongs outside the main app and should remain in the separate eval repository.

---

## Scope

### In scope

- Loading a baseline prompt or config bundle.
- Loading an explicit bounded search space.
- Generating a small candidate batch per round.
- Launching the main app on a fixed benchmark.
- Launching the eval app on produced runs.
- Applying a gated acceptance rule.
- Promoting the best accepted candidate.
- Recording candidate lineage, metadata, scores, and summaries.
- Producing machine-readable results tables and simple progress plots.
- Supporting dev-set optimization and holdout validation.

### Out of scope for MVP

- Code editing in any repo.
- Prompt generation with unrestricted open-ended LLM rewriting.
- Eval-metric editing during optimization.
- Automatic changes to benchmark definitions during optimization.
- Open-ended agent loops.
- Repo mutation, PR creation, or automated code review flows.
- Replacing the main app or eval app with optimizer-owned logic.

---

## Core optimization loop

### Baseline and initialization

The optimizer begins from one explicit baseline bundle.

The baseline bundle should identify:

- prompt bundle
- selected model ids
- selected optimizer-controlled config values
- baseline lineage root
- reproducibility metadata such as hashes and source references

### Per-round loop

For each round, the optimizer should:

1. load the current best candidate bundle
2. generate a small batch of candidate variants from the allowed search surface
3. materialize immutable candidate bundles for that batch
4. launch the main app against the fixed dev benchmark for each candidate
5. launch the eval app on the resulting run artifacts
6. compare candidate results against the incumbent using the acceptance rule
7. promote the best candidate only if it passes the gate
8. persist round summaries, candidate records, and plots

The loop should run for a configured fixed number of rounds or until an explicit stopping condition is met.

### Deterministic checks

The optimizer should support required deterministic checks before promotion, such as:

- required artifacts exist
- run completed without contract-breaking failures
- eval completed successfully
- configured benchmark cardinality matches expectation
- candidate metadata is complete and hashable

---

## Benchmark policy

The optimizer must support small fixed benchmarks because runs are slow.

The benchmark structure may include:

- optional smoke set for quick preflight validation
- dev set for optimization
- holdout set for final or periodic validation

Benchmark definitions should support:

- a handful of papers
- a defined worksheet or table slice when needed
- an optional field subset when needed
- a bounded runtime budget

The optimizer must not use holdout results to choose candidates during the main search loop.

---

## Candidate bundle contract

Candidate bundles must be immutable, auditable, and candidate-specific.

Each candidate bundle should record at minimum:

- candidate id
- round index
- parent candidate id
- baseline id
- prompt bundle identity
- prompt bundle snapshot path or content hash
- text model id
- optional vision model id
- optimizer-controlled config overlay
- benchmark id
- candidate hash or manifest hash
- creation metadata

Candidate bundles should be materialized as explicit bundle directories or equivalent candidate-owned manifests, not inferred later from scattered logs.

---

## Acceptance rule

The acceptance rule is gated, not purely scalar.

### Primary metrics

Primary metrics are the main optimization target, such as:

- correctness-focused headline score
- configured primary eval metric

### Guardrail metrics

Guardrail metrics block promotion when they regress beyond acceptable thresholds.

MVP guardrails should include:

- evidence-quality metric limits
- runtime ceilings or acceptable runtime deltas
- null, abstention, or failure-rate limits
- required deterministic checks

### Diagnostic metrics

Diagnostic metrics help explain behavior but do not directly drive promotion.

Examples include:

- per-field breakdowns
- candidate-specific warning counts
- error categories
- detailed null trends

The optimizer should persist accepted and rejected candidate decisions together with the reason each decision was made.

---

## Outputs and artifacts

The optimizer should produce enough output for reproducibility, audit, and comparison.

Expected artifacts include:

- machine-readable results table such as `results.csv`
- one candidate record per candidate run
- `best_candidate.json` or equivalent current-best record
- round summaries
- candidate bundle manifests and hashes
- launch metadata for main-app and eval-app invocations
- plots such as:
  - best score by round
  - candidate scores by round
  - runtime by round
  - correctness versus evidence quality
  - null or failure trends

The optimizer should keep enough metadata to reproduce how a promoted candidate was chosen.

---

## Operator workflows

### Optimize on dev

An operator points the optimizer at:

- a baseline bundle
- a bounded search-space definition
- a dev benchmark
- paths or commands for the main app and eval app

The optimizer runs several rounds and records the best candidate.

### Evaluate one candidate bundle

An operator can run one candidate bundle against a chosen benchmark without starting a full multi-round optimization loop.

### Validate current best on holdout

An operator can run the current best candidate on the holdout set without using that result to drive the main search loop.

### Summarize results

An operator can regenerate summaries and plots from recorded candidate-level result artifacts.

---

## Product quality bar

The MVP is done only when a normal operator can:

- define a bounded search space
- start from a baseline bundle
- run a fixed number of optimization rounds on a dev benchmark
- see candidate-by-candidate machine-readable results
- understand why a candidate was or was not promoted
- inspect the current best candidate and its lineage
- validate the current best on holdout
- regenerate summary tables and plots without hand-editing artifacts

The optimizer should remain small, understandable, and truthful about what it controls.

---

## Final constraint

The optimizer must preserve the repo separation:

- main app = execution
- eval app = scoring
- optimizer = orchestration

If a future design starts to blur those roles, that change should be treated as a deliberate product decision rather than a convenience shortcut.