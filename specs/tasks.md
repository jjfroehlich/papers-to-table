# Extract Structured Info from Papers Optimizer - tasks.md

## Status

Initial implementation checklist for the narrow optimizer MVP. No implementation batches have started yet.

## Purpose

This document turns `spec.md`, `plan.md`, and `research.md` into a concrete implementation task list for future coding work.

It is intentionally focused on the narrow MVP described in the spec stack:

- orchestration-only
- deterministic-first
- explicit study modes (`compare` and `optimize`)
- explicit bounded search surface
- immutable candidate bundles
- dev-set optimization with separate holdout validation

---

## Working rules

- Keep the repo CLI-first.
- Keep responsibilities separate:
  - main app executes
  - eval app scores
  - optimizer orchestrates
- Keep the search surface explicit and bounded.
- Keep one shared execution-and-scoring contract across study modes.
- Do not add code editing, eval-definition mutation, or benchmark mutation to MVP.
- Keep candidate bundles immutable and auditable.
- Keep holdout out of dev-search selection loops.
- Keep result artifacts inspectable on disk.
- Prefer one solid batch at a time over broad shallow scaffolding.

---

## Proposed implementation batches

### Batch 1 - Skeleton, contracts, single-run orchestration, and result logging

Goal: make one baseline or candidate bundle runnable through the main app and eval app with inspectable optimizer-owned artifacts.

- [ ] O001 Create the base package layout for the optimizer CLI and supporting modules.
- [ ] O002 Implement CLI parsing for `optimize`, `evaluate-candidate`, `validate-best`, and `summarize`, with explicit `--study-type` support for `compare` and `optimize` where applicable.
- [ ] O003 Implement optimizer config loading and validation.
- [ ] O004 Define typed contracts for optimizer settings, benchmark manifests, search-space definitions, candidate bundles, candidate results, round summaries, and best-candidate records, including required result fields: schema version, experiment id, study type, candidate lineage, benchmark id, prompt or model identities, flattened optimizer knobs, metric groups, runtime fields, decision fields, and run references.
- [ ] O005 Implement benchmark manifest loading with support for named splits such as `smoke`, `dev`, and `holdout`.
- [ ] O006 Implement benchmark split validation so holdout cannot be used as the main dev-search benchmark in either study mode.
- [ ] O007 Implement explicit search-space validation for prompt bundle variants, model ids, and bounded config knobs only.
- [ ] O008 Define the baseline bundle contract and validation rules.
- [ ] O009 Implement candidate-bundle hashing, lineage fields, and immutable bundle materialization.
- [ ] O010 Implement resolved candidate-owned config overlay generation for optimizer-controlled fields.
- [ ] O011 Implement main-app launcher support through a stable automation command plus run-artifact discovery.
- [ ] O012 Implement eval-app launcher support through a stable CLI command plus eval-summary discovery.
- [ ] O013 Implement candidate-level result records that capture launch metadata, metrics, runtimes, and decision fields for both study modes, with nullable `round_index` and `parent_candidate_id` handling for `compare`.
- [ ] O014 Write optimizer-owned experiment manifests, candidate manifests, and flat results tables such as `results.csv` and `results.jsonl`.
- [ ] O015 Add unit tests for config loading, benchmark validation, search-space validation, and candidate hashing.
- [ ] O016 Add mocked subprocess contract tests for main-app and eval-app launch flows.

### Batch 2 - Multi-round optimization loop, gated acceptance, promotion, and plotting

Goal: make the optimizer run several deterministic rounds on the dev benchmark and promote a winner under explicit rules.

- [ ] O017 Implement deterministic-first candidate generation for a small batch per round.
- [ ] O044 Implement fixed-candidate-set loading and validation for `compare` mode using the same candidate bundle contract.
- [ ] O018 Implement duplicate suppression across the current round and prior rounds.
- [ ] O019 Implement study-mode loop control: fixed single-pass evaluation flow for `compare` and multi-round incumbent loop for `optimize`.
- [ ] O020 Implement primary-metric selection and comparison rules.
- [ ] O021 Implement guardrail metric evaluation for evidence quality, runtime, and null or failure behavior.
- [ ] O022 Implement deterministic pre-promotion checks for required artifacts and successful run completion.
- [ ] O023 Implement structured promotion and rejection decision records with explicit reasons, including non-promotion decision annotations for `compare` mode summaries.
- [ ] O024 Implement best-candidate tracking and `best_candidate.json` updates.
- [ ] O025 Implement mode-aware summaries: round summaries with promoted candidate ids for `optimize`, and fixed-comparison summaries for `compare`.
- [ ] O026 Implement mode-specific static plot generation (CSV + PNG): `compare` plots for grouped primary comparisons, correctness-runtime, correctness-evidence, null or failure trends, and bounded parameter sweeps; `optimize` plots for best-by-round, all-scores-by-round, runtime-by-round, lineage, delta-by-round, and optimization-history lines.
- [ ] O045 Implement a bounded optional confirmation-rerun policy hook for top candidates, disabled by default, with explicit result linkage fields.
- [ ] O027 Add unit tests for acceptance logic, tie-breaking, and promotion decisions.
- [ ] O028 Add end-to-end smoke tests for both study modes on tiny mocked benchmarks.

### Batch 3 - Holdout validation, richer summaries, and contract hardening

Goal: validate that promoted winners can be checked cleanly on holdout and that the repo is trustworthy to operate.

- [ ] O029 Implement holdout validation behavior by study mode: final promoted candidate for `optimize`, optional top-k validation for `compare`, without feeding holdout into dev-search ranking.
- [ ] O030 Implement separate holdout validation artifacts and summary records.
- [ ] O031 Implement `summarize` to rebuild mode-aware summary tables and plots from recorded optimizer artifacts.
- [ ] O032 Add richer candidate and experiment summaries for lineage, benchmark identity, and promotion history.
- [ ] O033 Add contract checks for required metric names, required eval-summary fields, and required optimizer result-schema fields.
- [ ] O034 Add contract checks for required main-app run metadata relevant to optimization provenance.
- [ ] O035 Add end-to-end tests for holdout validation and summary regeneration.
- [ ] O036 Write the initial `README.md` and operator docs once real commands and artifact paths exist.
- [ ] O037 Review `spec.md`, `plan.md`, `research.md`, and `tasks.md` together for consistency before or during the first code batch.

### Batch 4 - Optional bounded LM Studio candidate proposer

Goal: add an optional LLM-assisted proposer only if it remains clearly bounded, auditable, and off by default.

- [ ] O038 Define the optional proposer request and response schema constrained by the existing explicit search surface.
- [ ] O039 Implement an LM Studio-backed proposer adapter that can suggest bounded candidate deltas without writing code or editing benchmarks.
- [ ] O040 Persist proposer prompts, responses, and resulting candidate deltas for auditability.
- [ ] O041 Ensure proposer output still goes through the same candidate validation, hashing, and acceptance flow as deterministic candidates.
- [ ] O042 Add tests for invalid proposer outputs, duplicate candidate suppression, and audit-log persistence.
- [ ] O043 Document the proposer as optional, bounded, and secondary to the deterministic-first baseline.

---

## Near-term implementation order

The recommended implementation sequence is:

1. Batch 1
2. Batch 2
3. Batch 3
4. Batch 4 only if the narrow deterministic-first MVP is already working and still easy to audit

That order keeps the repo focused on the smallest useful orchestration loop before adding optional intelligence.

---

## MVP completion standard

The narrow MVP should be considered complete only when a normal operator can:

- point the optimizer at a baseline bundle, search space, and dev benchmark
- run several optimization rounds
- inspect candidate-level machine-readable outputs
- understand why candidates were promoted or rejected
- inspect the current best candidate and its lineage
- validate the current best on holdout
- regenerate summaries and plots from saved artifacts

The repo should remain small and understandable even after those tasks are done.