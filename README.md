# extract-structured-info-from-papers-optimizer

CLI-first orchestration optimizer for evaluating bounded candidate bundles against fixed benchmarks.

## What this optimizer does

- Supports two study modes:
  - `compare`: evaluate an explicit fixed candidate set.
  - `optimize`: run bounded deterministic rounds with gated promotion.
- Treats the main app as execution engine.
- Treats the eval app as scoring oracle.
- Writes machine-readable artifacts and static plots.

## What this optimizer does not do

- Does not edit code in any repository.
- Does not reimplement extraction logic.
- Does not reimplement scoring logic.
- Does not mutate eval definitions or benchmark definitions.

## Install

```bash
pip install -e .[dev]
```

## CLI

```bash
paper-optimizer optimize --study-type compare --config optimizer.json --out runs/compare
paper-optimizer optimize --study-type optimize --config optimizer.json --out runs/optimize
paper-optimizer evaluate-candidate --config optimizer.json --candidate-file candidate.json --benchmark dev --out runs/eval_one
paper-optimizer validate-best --config optimizer.json --experiment runs/optimize --out runs/holdout
paper-optimizer summarize --experiment runs/optimize
```

## Config overview

The optimizer config controls only orchestration and bounded search fields.

- `schema_version`
- `experiment_id`
- `baseline_candidate`
- `compare_candidates` (for compare mode)
- `search_space` (for optimize mode deterministic proposer)
- `benchmarks`
- `main_app`
- `eval_app`
- `acceptance`
- `optimize`

For real runs, the optimizer adapts candidate bundles into the already-published main-app and eval-app contracts instead of expecting either repo to understand optimizer-owned manifests directly.

### Main-app integration config

The real main-app adapter expects:

- `main_app.repo_root`: checkout root of `extract-structured-info-from-papers`
- `main_app.base_config_path`: baseline main-app JSON config to clone and overlay per candidate
- `main_app.command_prefix` or `main_app.python_executable` + optional `main_app.module`
- optional `main_app.optimizer_knob_map` for optimizer knob name -> main-app config path mapping

For each candidate, the optimizer writes:

- `runs/<candidate_id>/main/main_config_overlay.json`
- `runs/<candidate_id>/main/resolved_main_config.json`
- `runs/<candidate_id>/main/automation_result.json`

The resolved config snapshot remains main-app-config-authoritative. Benchmark-specific `table_path`, `schema_path`, and `pdf_dir` values are bound into that snapshot before launch.

### Eval-app integration config

The real eval adapter expects:

- `eval_app.repo_root`: checkout root of `extract-structured-info-from-papers-eval`
- `eval_app.command_prefix` or `eval_app.python_executable` + optional `eval_app.module`
- optional `eval_app.metric_groups` mapping optimizer metric names to flat eval summary metric names

Each benchmark manifest can provide:

- `table_path`
- `schema_path`
- `pdf_dir`
- `gold_path`
- `gold_sheet`
- `eval_schema_path`

The optimizer treats eval `run_summary.json` and compare artifacts as source-of-truth outputs, then projects flat eval metrics into optimizer-owned `primary`, `guardrail`, and `diagnostic` groups.

### First real compare-study shape

The current adapter slice is designed for the first practical compare study:

- fixed prompt bundle
- fixed retrieval `top_k = 6`
- `recall_rescue_enabled = true`
- `whole_document_mode = false`
- style profiles fixed
- vision off
- compare three explicit text model ids
- benchmark splits for `smoke`, `dev`, and `holdout`

See tests for minimal working examples.

## Artifacts

The experiment directory contains:

- `experiment.json`
- `summary.json`
- `candidates/<candidate_id>/candidate.json`
- `results/results.csv`
- `results/results.jsonl`
- `rounds/round_<n>.json` (optimize mode)
- `best_candidate.json` (optimize mode and compare winner when available)
- `plots/*.png`
- `plots/*.csv`

Candidate-level result rows now include candidate lineage/hash data plus real integration references such as:

- main-app run id and run path
- main-app resolved config snapshot path
- eval output directory and per-run summary path
- grouped primary, guardrail, and diagnostic metrics
- runtime metadata and status fields

## Holdout behavior

- `optimize`: validate final promoted best on holdout.
- `compare`: optional top-k holdout checks for reporting, not dev-search ranking.
