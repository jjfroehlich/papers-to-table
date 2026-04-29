# papers-to-table integrated specification

- Status: Normative integrated spec

## 1. Product purpose

papers-to-table is a local-first system for extracting structured information from scientific papers into a spreadsheet while preserving reviewability.

The product has three coordinated surfaces:

- **main app**: browser-first extraction, review, and export workflow
- **eval companion**: scores run bundles against gold data
- **optimizer companion**: orchestrates repeated main-app plus eval studies

## 2. Core philosophy

- local-first by default
- browser UI is the primary human operator surface
- JSON config is the authoritative advanced-control surface
- run bundles are the canonical cross-tool contract
- unknown or obsolete provider identifiers fail early and clearly
- degraded-mode truth must stay explicit in UI, runtime, tests, docs, specs, and artifacts

## 3. Main-app inputs

The main app consumes:

- one table file
- one schema file
- one PDF directory
- one JSON config

The config controls provider selection, parser behavior, retrieval settings, prompt bundle, diagnostics, figure review, and output paths.

`app/config.example.json` is the canonical checked-in template. `app/config.json` is the normal local operator config.

## 4. Main-app modes

### 4.1 Human review mode

Human review mode is the default product workflow.

Required behavior:

1. operator starts the local app
2. operator runs preflight and sees resolved scope and provider readiness
3. extraction starts only after explicit operator action
4. operator reviews proposals in the browser UI
5. operator accepts, edits, rejects, or confirms no data explicitly
6. export writes a new workbook and audit artifacts

### 4.2 Headless / agent mode

The backend also exposes a stable non-UI automation path.

Headless mode must:

- run extraction from terminal inputs
- return machine-readable JSON
- preserve the same run-bundle truth as the browser workflow
- reject unattended export when reviewable proposals remain pending unless the caller passes explicit `--accept-all`
- record auto-accepted decisions explicitly in artifacts when `--accept-all` is used

Headless `--accept-all` is additive. It must not silently change the default human workflow.

## 5. Main-app workflow

### 5.1 Preflight and readiness

Preflight resolves:

- config path
- runtime input overrides
- run mode
- output directory
- provider model ids and locality
- table row count, schema column count, and PDF count when possible

Preflight must fail early on readiness defects instead of allowing cosmetically successful runs.

### 5.2 Parsing and normalized document contract

The parser layer produces normalized parsed documents with:

- paper metadata and front matter
- per-page text visibility
- typed blocks in reading order
- figure and caption relationships when available
- parser truth, fallback truth, and diagnostics

### 5.3 Matching

Each PDF is matched to at most one row.

The system must keep unmatched, ambiguous, and duplicate-row conflicts explicit in artifacts and review diagnostics.

### 5.4 Retrieval and extraction

- extraction is schema-first
- default retrieval path is `hybrid_experimental` with `top_k=12`
- recall rescue and whole-document mode are bounded optional modes
- one best proposal is persisted per eligible target cell
- evidence quality stays explicit and honest
- figure review is targeted and text-guided, not blanket page vision

### 5.5 Proposal and evidence truth

Proposal records must preserve:

- stable join identity (`row_id`, `column_name`, `cell_id`)
- proposed value
- support quality
- evidence ids
- degraded-mode, fallback, metadata-lane, and failure-attribution truth when relevant

Evidence must remain auditable and typed distinctly, including direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page, and figure evidence.

### 5.6 Review semantics

Valid explicit review outcomes are:

- accepted
- accepted with edit
- confirmed no data
- rejected

Decision records must distinguish `human_individual`, `human_bulk_accept`, and `automation_accept_all`. Legacy `human_reviewer` records remain readable for backward compatibility, but newly recorded manual decisions use explicit individual/bulk values.

### 5.7 Export semantics

Export writes a new workbook and audit artifacts.

Export includes only explicitly accepted changes.

The source workbook is never mutated in place.

## 6. Run bundle contract

A run bundle is the stable filesystem artifact at `{output_dir}/{run_id}/`.

Stable categories include:

- inputs
- style profiles
- parsed artifacts
- matching artifacts
- retrieval artifacts
- proposals
- evidence
- review decisions
- summaries
- diagnostics
- exports

Important shared files include:

Schemas for machine validation live under `specs/contracts/schemas/` and are consumed by `verify-contract`.


- `run.json`
- `config.snapshot.json`
- `inputs/input_summary.json`
- `proposals/proposals.jsonl`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/workbook_*.xlsx`
- `exports/audit_log_*.json`

## 7. Provider policy

The default live provider path is LM Studio with config token `lm_studio`.

Required truth to preserve:

- provider reachable vs unreachable
- model available vs unavailable
- negotiated structured-output mode
- prompt-only degraded fallback when used
- extraction-contract validity and warnings
- explicit model-management lifecycle assumptions and cleanup diagnostics

## 8. Eval companion

Eval is CLI-first and file-driven.

It must:

- read run bundles from files alone
- score against gold data
- keep correctness and evidence metrics separate
- preserve dual-judge details when configured
- publish per-run and compare artifacts under the caller's output directory

Real benchmark evaluation should use two judges by default.

## 9. Optimizer companion

Optimizer is orchestration-only.

It must:

- load explicit candidate bundles and search spaces
- launch main-app and eval runs
- keep compare and optimize workflows distinct
- distinguish real benchmark presets from fixture and smoke presets
- report winner and recommended default separately when trust caveats differ

Canonical operator workflows are:

- compare models
- optimize one model
- overnight sequence

## 10. Config families

### 10.1 Main app

Canonical template: `app/config.example.json`

### 10.2 Eval

Primary surface: CLI arguments plus optional eval schema JSON

### 10.3 Optimizer

Canonical presets:

- `compare_models.json`
- `compare_prompts.json`
- `compare_retrieval.json`
- `compare_retrieval_modes.json`
- `optimize_one_model.json`
- `compare_models_overnight.json`
- `optimize_overnight.json`

Smoke and fixture-manual configs remain explicitly labeled non-canonical benchmark evidence.

## 11. Operator command surface

The repo exposes one central operator and agent command surface:

- `python scripts/papers_to_table.py install`
- `python scripts/papers_to_table.py review`
- `python scripts/papers_to_table.py preflight --config ...`
- `python scripts/papers_to_table.py headless --config ... --accept-all --export`
- `python scripts/papers_to_table.py verify-contract --run ...`
- `python scripts/papers_to_table.py eval ...`
- `python scripts/papers_to_table.py optimizer compare-models`
- `python scripts/papers_to_table.py optimizer optimize-one-model`
- `python scripts/papers_to_table.py optimizer overnight`
- `python scripts/papers_to_table.py docs serve`
- `python scripts/papers_to_table.py docs build`

## 12. Diagnostics and limitations

The system must remain truthful about:

- readiness defects
- parser availability and fallback
- matching ambiguity
- degraded structured-output modes
- evidence weakness
- auto-accepted headless decisions

Known practical limits include parser dependency drift, live model readiness variance, judge disagreement on fuzzy text fields, and the need for real benchmark manifests outside the checked-in fixture set.

## 13. Documentation and agent-operating surfaces

- `README.md` is the concise repository entry point.
- `docs/` is the operator/developer manual and is also buildable as a local/static MkDocs Material site.
- `specs/` remains the canonical rebuild-grade implementation truth.
- `agent-skills/papers-to-table/` provides a focused headless operating procedure for external coding agents and must not replace installation or runtime readiness checks.
