# Extract Structured Info from Papers Optimizer - spec.md

## Status

Initial product specification for a separate CLI-first optimizer repository.

## Purpose

This repository optimizes prompt, model, and bounded configuration bundles for `extract-structured-info-from-papers` by repeatedly running the main app on a fixed benchmark and scoring the resulting runs with `extract-structured-info-from-papers-eval`.

The optimizer is intentionally narrow. It is an orchestration harness over an explicit search surface, not a self-modifying agent, not an autonomous software-engineering loop, and not a general benchmark platform.

---

## Product summary

The optimizer should:

1. support two explicit study modes: `compare` and `optimize`
2. evaluate candidate bundles by running the main app on fixed benchmarks through a stable automation entrypoint
3. score produced runs by running the eval app through a stable automation entrypoint
4. compare candidate outcomes under a gated acceptance policy when promotion is enabled
5. record machine-readable artifacts, logs, and static plots
6. keep immutable candidate bundles and lineage for audit and reproducibility
7. keep holdout usage separate from dev-set search behavior

In `optimize` mode, the loop is:

propose -> run main app -> run eval app -> score -> gate -> promote or keep incumbent -> log -> plot -> repeat

In `compare` mode, there is no iterative promotion loop:

materialize fixed candidates -> run main app -> run eval app -> score -> log -> plot -> compare

---

## Study modes

The optimizer must support two study modes in MVP.

Both modes use the same main-app execution contract and eval-app scoring contract; only study control flow and summaries differ.

### A. `compare`

`compare` mode evaluates a fixed explicit set of candidate bundles and reports comparative results.

Typical uses:

- compare text model ids
- compare optional vision model ids
- compare prompt bundle variants
- compare bounded parameter presets

`compare` mode does not require multi-round incumbent promotion.

### B. `optimize`

`optimize` mode runs the iterative incumbent/challenger loop:

1. start from a baseline candidate
2. generate a small deterministic batch from the bounded search surface
3. evaluate challengers on the dev benchmark
4. promote only if the gated acceptance rule passes
5. repeat for bounded rounds

`optimize` mode is where optimization-history lineage and round-based progress plots are expected.

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
- Running fixed-candidate comparative studies in `compare` mode.
- Generating a small candidate batch per round in `optimize` mode.
- Launching the main app on a fixed benchmark.
- Launching the eval app on produced runs.
- Applying a gated acceptance rule when promotion is in play.
- Promoting the best accepted candidate in `optimize` mode.
- Recording candidate lineage, metadata, scores, and summaries.
- Producing machine-readable results tables and mode-appropriate static plots.
- Supporting dev-set search and holdout validation policies by study mode.

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

This section defines `optimize` mode behavior.

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

Holdout behavior by mode:

- `optimize`: validate the final promoted candidate on holdout after dev-loop search.
- `compare`: optionally validate top-k candidates on holdout after dev comparison, but do not use holdout as the main ranking driver during dev comparisons.

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
- plots and summaries appropriate to study mode

### Minimum optimizer-owned result record contract

Each candidate result record must include at minimum:

- `schema_version`
- `experiment_id`
- `study_type` (`compare` or `optimize`)
- `candidate_id`
- `parent_candidate_id` (nullable)
- `round_index` (nullable in `compare` mode)
- `benchmark_id`
- prompt bundle identity
- text model id
- vision model id when present
- flattened optimizer-controlled config knobs
- primary metrics
- guardrail metrics
- diagnostic metrics
- runtime and timing fields
- promotion or rejection decision and reason
- main-app run reference
- eval output reference

The record format should be practical and machine-readable in both flat and rich forms (for example CSV plus JSONL).

### Plotting requirements

MVP plotting should remain simple and static (CSV-backed summaries plus PNG outputs are sufficient).

Required `compare` mode plot families:

- primary metric by candidate, model, and preset
- correctness versus runtime scatter
- correctness versus evidence-quality scatter
- null or failure trend summaries
- parameter-comparison plots for bounded sweeps
- optional higher-dimensional parameter relationship plots later

Required `optimize` mode plot families:

- best score by round
- all candidate scores by round
- runtime by round
- incumbent or champion lineage
- score delta or improvement by round
- autoresearch-style optimization-history line plot

### Optional confirmation reruns

Top candidates may optionally be re-run to reduce noise before final promotion (`optimize`) or final recommendation (`compare`).

This confirmation policy may be deferred to a later implementation batch, but it is in scope for planning and research rationale.

The optimizer should keep enough metadata to reproduce how a promoted candidate was chosen.

---

## Operator workflows

### Compare fixed candidate bundles

An operator points the optimizer at:

- an explicit candidate set
- a benchmark split (normally dev)
- paths or commands for the main app and eval app

The optimizer evaluates all listed candidates, writes comparable result records, and generates `compare`-mode summaries and plots.

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

- run `compare` mode on explicit candidate bundles and inspect candidate-by-candidate results
- define a bounded search space
- start from a baseline bundle
- run a fixed number of `optimize` rounds on a dev benchmark
- see candidate-by-candidate machine-readable results
- understand why a candidate was or was not promoted
- inspect the current best candidate and its lineage
- validate holdout in a way consistent with the selected study mode
- regenerate summary tables and plots without hand-editing artifacts

The optimizer should remain small, understandable, and truthful about what it controls.

---

## Final constraint

The optimizer must preserve the repo separation:

- main app = execution
- eval app = scoring
- optimizer = orchestration

If a future design starts to blur those roles, that change should be treated as a deliberate product decision rather than a convenience shortcut.