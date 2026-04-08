# extract-structured-info-from-papers-optimizer

CLI-first orchestration for running bounded compare and optimize studies across:

- `extract-structured-info-from-papers` for extraction
- `extract-structured-info-from-papers-eval` for scoring

This repo owns study orchestration, candidate materialization, result tracking, and plots. It does not own extraction logic or scoring logic.

## What this app does

- Loads an optimizer config, benchmark manifests, and a bounded search space.
- Materializes immutable candidate bundles with stable candidate ids and hashes.
- Launches the main app and eval app for each candidate.
- Applies acceptance gates in optimize mode.
- Persists experiment summaries, candidate records, round summaries, and plots.

## Study modes

### compare

- Evaluates an explicit fixed candidate set on the `dev` benchmark.
- Produces ranked summaries and compare plots.
- Can optionally run holdout validation for the top `k` candidates via `compare.holdout_top_k`.

### optimize

- Evaluates a baseline candidate first.
- Proposes bounded deterministic challengers round by round.
- Promotes challengers only when the primary metric and guardrails pass.
- Produces incumbent tracking, round summaries, and optimize plots.

## Install

```bash
pip install -e .[dev]
```

## CLI

```bash
paper-optimizer optimize --study-type compare --config config.example.json --out runs/compare
paper-optimizer optimize --study-type optimize --config config.example.json --out runs/optimize
paper-optimizer evaluate-candidate --config config.example.json --candidate-file candidate.json --benchmark dev --out runs/eval_one
paper-optimizer validate-best --config config.example.json --experiment runs/optimize --out runs/holdout
paper-optimizer summarize --config config.example.json --experiment runs/optimize
```

## Recommended setup

Use [config.example.json](config.example.json) as the generic template and the files under `configs/` as the ready-to-edit study configs for unattended runs.

Recommended layout for the current multi-repo workspace:

- optimizer repo: this repository
- main app repo: sibling checkout at `../extract-structured-info-from-papers`
- eval app repo: sibling checkout at `../extract-structured-info-from-papers-eval`

The recommended `main_app` config is:

- `repo_root`: path to the main app repo
- `base_config_path`: path to the main app config that the optimizer will overlay per candidate
- `command_prefix`: optional explicit launcher, usually needed when the main app runs in a different Python environment
- `optimizer_knob_map`: optional mapping from optimizer knob names to nested main-app config paths

The recommended `eval_app` config is:

- `repo_root`: path to the eval repo
- `command_prefix`: optional explicit launcher, usually needed when the eval app runs in a different Python environment
- `metric_groups`: mapping from eval summary metrics into optimizer `primary`, `guardrail`, and `diagnostic` groups

If you need a non-standard wrapper, both `main_app` and `eval_app` also support explicit `command` arrays. The recommended repo-root plus config-overlay path is the cleaner default.

## Study configs

Prepared configs in `configs/`:

- `compare_models_smoke.json`: small preflight compare that points the optimizer's `dev` split at the smoke fixture benchmark.
- `compare_models_dev.json`: overnight compare of three explicit text models in this order: `qwen/qwen3.5-9b`, `google/gemma-4-26b-a4b`, `qwen/qwen3.5-35b-a3b`.
- `compare_prompts_dev.json`: temporarily reduced to a disabled-tonight placeholder because only the `default` prompt bundle exists in the checked-in main repo.
- `compare_retrieval_dev.json`: tonight's retrieval sweep on `google/gemma-4-26b-a4b` for `retrieval_top_k = 6 / 8 / 10`.
- `optimize_overnight.json`: tonight's bounded optimize config fixed to `google/gemma-4-26b-a4b` with the requested deterministic search surface.

Two repo-grounded TODOs remain before every config is trustworthy in production:

- The checked-in main repo currently exposes only the `default` prompt bundle, so prompt comparison is skipped for tonight.
- A distinct real holdout benchmark is still not configured, so tonight's configs intentionally skip holdout instead of pretending `dev == holdout`.

## Config model

Top-level fields used by the current code:

- `schema_version`
- `experiment_id`
- `baseline_candidate`
- `compare_candidates`
- `search_space`
- `benchmarks`
- `main_app`
- `eval_app`
- `acceptance`
- `optimize`
- `compare`

Important current behavior:

- `compare_candidates` drives compare mode. If omitted, compare mode falls back to the baseline candidate.
- Optimize mode varies `prompt_bundle_id`, `text_model_id`, `vision_model_id`, and `search_space.numeric_knobs`.
- Manual compare candidates can still vary any candidate fields that the candidate bundle contract supports.
- `benchmarks.dev` drives compare and optimize decisions.
- `benchmarks.holdout` is only used for post-study validation.
- CLI commands now run an explicit preflight before launching work. Missing benchmark files, missing prompt bundles, invalid command prefixes, and missing metric mappings fail early.

For tonight's unattended runs, holdout is intentionally skipped and `diagnostics.verbose_provider_logging` is enabled in the main app's checked-in base config.

## Overnight workflow

[scripts/run_study.sh](scripts/run_study.sh) creates timestamped output and log directories and then runs:

1. the study itself
2. summary regeneration
3. holdout validation, unless `PAPER_OPTIMIZER_SKIP_HOLDOUT=1`

[scripts/run_overnight.sh](scripts/run_overnight.sh) is the higher-level wrapper for the recommended unattended path:

1. smoke compare preflight
2. overnight compare-model study
3. Gemma retrieval sweep
4. overnight optimize study on Gemma

### Recommended order

Run studies in this order:

1. `compare_models_smoke.json`
2. `compare_models_dev.json`
3. `compare_retrieval_dev.json`
4. `optimize_overnight.json`

Skip `compare_prompts_dev.json` tonight.

### Exact Git Bash commands

Smoke preflight compare:

```bash
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh compare configs/compare_models_smoke.json smoke_models
```

Overnight compare of explicit models:

```bash
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh compare configs/compare_models_dev.json compare_models_dev
```

Prompt-bundle compare after you have a real `evidence_strict` bundle:

```bash
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh compare configs/compare_prompts_dev.json compare_prompts_dev
```

Retrieval sweep compare:

```bash
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh compare configs/compare_retrieval_dev.json compare_retrieval_dev
```

Direct optimize run from the prepared optimize template:

```bash
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh optimize configs/optimize_overnight.json optimize_overnight
```

Recommended unattended wrapper that derives optimize from the compare winner:

```bash
bash scripts/run_overnight.sh overnight_batch_01
```

### Output layout for operator scripts

By default `run_study.sh` writes to:

- `runs/<timestamp>_<study-type>_<label>/experiment`
- `runs/<timestamp>_<study-type>_<label>/holdout`
- `logs/<timestamp>_<study-type>_<label>.log`
- `runs/<timestamp>_<study-type>_<label>/run_metadata.json`

Practical operator guidance for overnight runs:

- Run the smoke compare first. If it fails, do not start the longer studies.
- Set explicit `command_prefix` values if the optimizer, main app, and eval app do not share one Python environment.
- Keep `optimize.rounds` and `optimize.batch_size` bounded to match expected runtime.
- Holdout is skipped for tonight. Do not call `validate-best` until you configure a real holdout split.

### What to inspect next morning

Start with:

- the run log under `logs/`
- `experiment/summary.json`
- `experiment/best_candidate.json`
- `experiment/results/results.csv`

If a run failed, inspect candidate-specific reasons in:

- `experiment/results/results.jsonl`
- `experiment/candidates/<candidate_id>/candidate.json`
- `experiment/runs/<candidate_id>/main/automation_result.json`
- `experiment/runs/<candidate_id>/eval/eval_result.json`

For real eval-app launches, the optimizer records the resolved gold input in the eval launch artifact. When the main-app run bundle exposes an eval-ready gold snapshot in `run.json`, that bundled snapshot is preferred over the benchmark manifest `gold_path`.

The optimizer now fails candidates explicitly when:

- main-app automation payloads are missing required provenance metadata
- eval summaries are missing required fields or configured metrics
- deterministic contract checks fail before promotion

## Artifact layout

Each experiment directory contains:

- `experiment.json`
- `summary.json`
- `best_candidate.json` when a winner or incumbent is recorded
- `candidates/<candidate_id>/candidate.json`
- `results/results.csv`
- `results/results.jsonl`
- `rounds/round_<n>.json` for optimize mode
- `plots/*.csv`
- `plots/*.png`
- `runs/<candidate_id>/main/` launch artifacts including `main_config_overlay.json`, `resolved_main_config.json`, and `automation_result.json`
- `runs/<candidate_id>/eval/` launch artifacts including `eval_result.json`

`summary.json` now also rolls up:

- winner or incumbent identity
- model and prompt rollups
- rejection reason counts
- promotion history and incumbent lineage for optimize studies
- holdout-validation status when holdout has run

## Known limitations

- Confirmation reruns are still not implemented.
- The checked-in repo does not currently include an `evidence_strict` prompt bundle.
- A trustworthy real holdout split still needs to be configured before re-enabling overnight holdout validation.

## Verification snapshot

Targeted local optimizer tests pass with a non-interactive plotting backend:

```bash
python -m pytest -q tests/test_acceptance_and_contracts.py tests/test_compare_mode.py tests/test_optimize_mode.py tests/test_holdout_and_summarize.py tests/test_real_integration_adapters.py tests/test_pipeline_subprocess.py tests/test_settings_and_search_space.py
```
