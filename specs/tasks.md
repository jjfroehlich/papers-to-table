# Current Tasks

## Active Backlog

- [ ] Add or expand checks that validate docs-referenced wrapper commands and canonical spec links.
- [ ] Continue removing personal-path assumptions from benchmark preset examples and historical external-result references where they affect active workflows.
- [ ] Inspect evidence-anchor and artifact diffs behind the C2/D3/E2 evidence-quality guardrail failures before retesting recovery, prompt, or figure value-acceptance changes.
- [ ] Test the next improvement loop from current main with ignored `.tmp/` or external sibling worktrees; avoid visible top-level `w/` worktrees.
- [ ] Evaluate generic candidate selection and normalization on the active three-dataset benchmark suite.
- [ ] Keep `improvement-ideas.md` and `experiment-results.md` current as improvement ideas are tested, kept, rejected, or superseded.
- [ ] Refresh screenshots of the web interface (for docs).
- [ ] Consider optional agent-kit XLSX export, `main_compat/` generation, bbox overlays, figure/page-image assets, and Playwright coverage after the rich review MVP stabilizes.

## Blocked

- [ ] None currently recorded.

## Recently Verified

- [x] 2026-07-10 negative-control calibration augmented `tools/optimizer/runs/20260615_004637_compare_models` to 17 candidates and 153 replicate rows: word shuffle scored 0.5589, cross-field scored 0.0000, and all 18 new replicates completed the configured dual-judge Eval path without failed or degraded status.
- [x] Active spec system consolidated around `README.md`, `spec.md`, `architecture.md`, `contracts.md`, `ui-review-workflow.md`, `eval-and-optimizer.md`, `decisions.md`, `plan.md`, `tasks.md`, and `contracts/schemas/*.json`.
- [x] Actual agent skill directories are `skills/papers-to-table-agent-kit/` and `skills/papers-to-table-local-app/`.
- [x] Active benchmark dataset directories are `massively_parallel_reporter_assays`, `genome_editing_tools`, and `spatial_transcriptomics`.
- [x] Optimizer active benchmark ids are `bench_massively_parallel_reporter_assays`, `bench_genome_editing`, and `bench_spatial_transcriptomics`; `bench_smoke` is fixture-only.
- [x] Headless mode supports explicit `--accept-all` and records automation decisions as `automation_accept_all`.
- [x] Main-app, eval, and optimizer use run bundles and summary artifacts as their integration boundary.
- [x] JSON schemas remain under `specs/contracts/schemas/` as machine-readable contract checks.
- [x] Active improvement ledgers remain in `specs/improvement-ideas.md` and `specs/experiment-results.md`.
- [x] Portable agent kit now uses `review_input.json` plus PDFs and optional table/schema files as the authored boundary for rich static/local review.
- [x] 2026-06-17 wave-2 improvement dev-checks completed for A3, A4, A2b, and B1 against matched `google/gemma-4-e4b` current main; A2b and A4 are current main behavior, while A3/B1 should not be merged unchanged.
- [x] 2026-06-17 next-batch dev-checks completed for C2, D3, E2, and F against fresh current-main baseline `main_next_batch_baseline_e4b_20260617`; C2/D3/E2 should not be merged unchanged, while F is current eval/reporting behavior.
- [x] A2b regression check completed: current main rechecks scored 0.54 and 0.50 versus detached pre-A2b controls at 0.56 and 0.52, so the 0.48 baseline is treated as suspicious single-run noise rather than proof of regression.
- [x] Visible top-level `w/` experiment worktrees were removed; experiment branches were preserved.

## Archived Task Ledgers

Older completed task history was moved to `specs/archive/task-ledgers/2026-05-30-pre-spec-simplification.md`.
