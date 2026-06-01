# Architecture

- Status: Canonical focused spec
- Owner: Architecture
- Depends on: `spec.md`, `contracts.md`
- Consumed by: contributors, coding agents, `app/`, `tools/eval/`, `tools/optimizer/`, `docs/`

## Purpose

This file owns the repository layout, runtime boundaries, and cross-tool integration flow. Product behavior belongs in `spec.md` and `ui-review-workflow.md`; file contracts belong in `contracts.md`.

## Repository Layout

- `README.md`: concise repository entry point and happy-path commands.
- `AGENTS.md`: repo-wide operating rules for coding agents.
- `app/backend/src/backend/app/`: FastAPI backend, config resolution, preflight, pipeline execution, provider adapters, review/export APIs, and run-bundle writing.
- `app/frontend/`: React browser UI for run setup, status, proposal review, diagnostics, and export.
- `benchmark_datasets/`: checked-in benchmark inputs and external-result comparison data. Current active benchmark datasets are `massively_parallel_reporter_assays`, `genome_editing_tools`, and `spatial_transcriptomics`; historical/external result tables live under `benchmark_datasets/data/`.
- `docs/`: MkDocs manual for operators, agents, and developers.
- `skills/`: reusable external agent workflows. The current skill directories are `skills/papers-to-table-agent-kit/` and `skills/papers-to-table-local-app/`; there is no alternate active skill-root directory. `papers-to-table-agent-kit` is a portable rich review handoff kit whose authored input is `review_input.json` plus PDFs and optional table/schema files; its scripts generate static/local review, normalized, decision, summary, and export artifacts without running the main app backend or extraction pipeline.
- `specs/`: canonical active spec set plus historical archive.
- `tools/eval/`: file-driven evaluator companion tool.
- `tools/optimizer/`: orchestration-only optimizer companion tool.
- `tools/docs/`: MkDocs configuration and docs requirements.
- `scripts/`: repository-level wrapper scripts and checks.

## Runtime Boundaries

The monorepo has three runtime surfaces:

- Main app: extraction, review, export, and run-bundle emission.
- Eval: scoring persisted run bundles or external filled tables against gold data.
- Optimizer: launching repeated main-app and eval runs, aggregating study results, and reporting recommendations.

Eval must not import main-app runtime code to score a run bundle. Optimizer must not reimplement extraction or scoring logic. Integration happens through persisted artifacts and command-line entrypoints.

## Main-App Architecture

The browser frontend is the primary operator surface. It handles setup, status, review, diagnostics, and export actions through backend APIs.

The backend owns:

1. config loading and runtime path overrides
2. preflight and readiness checks
3. run lifecycle state
4. PDF parsing and normalized document artifacts
5. PDF-to-row matching
6. retrieval, style profiles, extraction, optional figure review, and candidate selection
7. proposal/evidence persistence
8. review decisions
9. accepted-only export artifacts

The backend writes run bundles under `{output_dir}/{run_id}/`, with `app/runs/` as the default output location when config does not override it.

## Integration Flow

The cross-tool flow is intentionally simple:

1. The main app executes extraction and writes a run bundle.
2. Eval reads the run bundle from files alone, scores against gold data, and writes per-run and comparison artifacts.
3. Optimizer launches the main app and eval for candidate x benchmark x replicate studies, then records candidate, benchmark, suite, and study summaries.

The optimizer must wait until the main-app run has completed proposal generation and written readable final summaries before starting eval. Eval judging starts after eval has loaded the completed run bundle and prepared deterministic and judge-needed cells.

## Wrapper Command Surface

The central command surface is `python scripts/papers_to_table.py ...`.

Primary commands:

- `install`
- `review`
- `preflight`
- `headless`
- `verify-contract`
- `eval`
- `optimizer compare-models`
- `optimizer dev-check`
- `optimizer full-benchmark`
- `docs serve`
- `docs build`

Lower-level scripts remain useful for tests and development, but operator docs should keep the wrapper command as the first path unless a lower-level command is explicitly needed.

## Source, Tests, Docs, Skills, Configs, And Artifacts

- Backend tests live under `app/tests/backend/`.
- Frontend tests live under `app/frontend/src/**/*.test.*`.
- E2E helpers live under `app/tests/e2e/`.
- Eval tests live under `tools/eval/tests/`.
- Optimizer tests live under `tools/optimizer/tests/`.
- Main-app config examples live at `app/config.example.json`; `app/config.json` is the normal local operator config created or edited during use.
- Optimizer presets live under `tools/optimizer/configs/`.
- Manual pages live under `docs/` and are navigated by `tools/docs/mkdocs.yml`.
- Browser screenshots referenced by docs live under `docs/screenshots/`.
- Agent skill packages live under `skills/`.
- Run bundles and optimizer study outputs are generated artifacts, not spec truth.

## Cross-Tool Truth Rule

If a statement applies to more than one runtime surface, put it in `contracts.md`, `architecture.md`, or `spec.md` rather than duplicating it in tool-specific docs. Tool docs may summarize behavior for operators, but they must not become the only source of implementation truth.
