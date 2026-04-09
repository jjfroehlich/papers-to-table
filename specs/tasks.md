# Extract Structured Info from Papers Optimizer - tasks.md

## Canonical task tracking

This file is the single source of truth for implementation status in this repository.

Rules:

- Keep one canonical checked/unchecked list.
- Keep each task listed exactly once.
- Keep completed tasks visible.
- Record temporary or historical notes only in appendices.

## Foundation / CLI / config / contracts

- [x] O001 Create base package layout for optimizer CLI and modules.
- [x] O002 Implement CLI parsing for `optimize`, `evaluate-candidate`, `validate-best`, and `summarize`.
- [x] O003 Implement optimizer config loading and validation.
- [x] O004 Define typed contracts for settings, benchmarks, search space, candidate bundles, candidate results, round summaries, and best-candidate records.

## Benchmarks and split validation

- [x] O005 Implement benchmark manifest loading for `smoke`, `dev`, and `holdout` style splits.
- [x] O006 Implement split validation so `dev` and `holdout` cannot be the same benchmark id.

## Search-space and candidate-bundle handling

- [x] O007 Implement explicit search-space validation for bounded optimizer-owned fields.
- [x] O008 Define baseline candidate contract and validation rules.
- [x] O009 Implement candidate hashing, lineage fields, and immutable bundle materialization.
- [x] O010 Implement candidate-owned resolved overlay generation for optimizer-controlled fields.
- [x] O017 Implement deterministic-first candidate generation for bounded per-round batches.
- [x] O018 Implement duplicate suppression across round proposals and prior seen candidates.
- [x] O044 Implement fixed-candidate-set loading/validation for compare mode with shared candidate contract.
- [ ] O045 Implement optional bounded confirmation-rerun policy hook for top candidates, disabled by default.

## Main-app launch integration

- [x] O011 Implement main-app launcher integration via stable automation command and run-artifact discovery.

## Eval-app launch integration

- [x] O012 Implement eval-app launcher integration via stable CLI command and eval-summary discovery.

## Result records and artifacts

- [x] O013 Implement candidate-level result records with lineage, metric groups, runtime, and decision fields for both study modes.
- [x] O014 Implement experiment-level artifact writes (`experiment.json`, candidate manifests, `results.csv`, `results.jsonl`, summary files, and current compare-study diagnostics artifacts).
- [x] O024 Implement best-candidate tracking and `best_candidate.json` updates.
- [x] O032 Add richer experiment summaries for lineage and promotion-history rollups.
- [x] O033 Add explicit contract checks for required metric names and required eval-summary fields.
- [x] O034 Add explicit contract checks for required main-app run metadata relevant to provenance.

## Compare-mode orchestration

- [x] O019 Implement mode-aware study control flow with compare single-pass and optimize multi-round behavior.
- [x] O025 Implement compare summaries with ranked fixed-candidate outcomes, winner materialization, and candidate-level explanation artifacts for scored and unscored candidates.

## Optimize-mode orchestration

- [x] O020 Implement primary-metric comparison rule for promotion decisions.
- [x] O021 Implement guardrail evaluation for evidence/runtime/null-failure constraints.
- [x] O022 Implement explicit deterministic pre-promotion checks as a dedicated acceptance gate stage.
- [x] O023 Implement structured promotion/rejection decision reasons in candidate records.

## Acceptance / promotion / guardrails

- [x] O027 Add focused unit tests for acceptance logic, guardrail failures, and tie-breaking paths.

## Holdout / confirmation / summary regeneration

- [x] O029 Ensure optimize holdout validation uses final promoted incumbent semantics only (not generic best-score ranking).
- [x] O030 Implement separate holdout validation artifacts and summary records.
- [x] O031 Implement `summarize` to regenerate mode-appropriate plots from persisted artifacts.

## Plotting

- [x] O026 Complete mode-specific plotting contract coverage, including bounded parameter sweep views where relevant.

## Tests / docs / contract hardening

- [x] O015 Add tests for config loading, search-space handling, benchmark split checks, and candidate hashing.
- [x] O016 Add mocked subprocess contract tests for main-app and eval-app launch flows.
- [x] O028 Add smoke-level end-to-end tests for compare and optimize flows on tiny mocked benchmarks.
- [x] O035 Add end-to-end tests for holdout validation and summarize regeneration.
- [x] O036 Maintain README operator documentation aligned with current behavior.
- [x] O037 Keep spec stack consistency (`spec.md`, `plan.md`, `research.md`, `tasks.md`).

## Optional bounded LM proposer

- [ ] O038 Define optional proposer request/response schema constrained to existing search surface.
- [ ] O039 Implement LM Studio-backed proposer adapter for bounded deltas.
- [ ] O040 Persist proposer prompts/responses and applied candidate deltas for audit.
- [ ] O041 Route proposer outputs through the same candidate validation, hashing, and acceptance flow.
- [ ] O042 Add tests for invalid proposer outputs, duplicate handling, and proposer audit persistence.
- [ ] O043 Document proposer feature as optional and disabled by default.