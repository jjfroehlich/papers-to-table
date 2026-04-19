# Optimizer Documentation

The optimizer is an internal calibration and orchestration tool for bounded compare and optimize studies.

It is not the product surface. It exists to run development-time studies against the main app and eval tool.

## Purpose

- Load an optimizer config, benchmark manifests, and a bounded search space.
- Materialize immutable candidate bundles.
- Launch the main app and eval tool for each candidate.
- Apply acceptance gates in optimize mode.
- Persist experiment summaries, candidate records, plots, and reports.

Run optimizer commands from `tools/optimizer/`.

## Install

```bash
cd tools/optimizer
pip install -e .[dev]
```

## Study modes

### compare

- evaluates an explicit fixed candidate set on the dev benchmark
- produces ranked summaries and compare plots
- can optionally run holdout validation for top candidates

### optimize

- evaluates a baseline candidate first
- proposes bounded deterministic challengers round by round
- promotes challengers only when the primary metric and guardrails pass
- writes incumbent tracking, round summaries, plots, and reports

## CLI examples

```bash
paper-optimizer optimize --study-type compare --config config.example.json --out runs/compare
paper-optimizer optimize --study-type optimize --config config.example.json --out runs/optimize
paper-optimizer evaluate-candidate --config config.example.json --candidate-file candidate.json --benchmark dev --out runs/eval_one
paper-optimizer validate-best --config config.example.json --experiment runs/optimize --out runs/holdout
paper-optimizer summarize --config config.example.json --experiment runs/optimize
```

## Recommended monorepo layout

- repo root: this repository
- main app: `app/`
- eval tool: `tools/eval/`
- optimizer tool: `tools/optimizer/`

Prepared configs under `tools/optimizer/configs/` use monorepo-local relative paths.

## Overnight workflow

The optimizer includes two main shell wrappers:

- `scripts/run_study.sh`: run one compare or optimize study, summarize it, and optionally validate holdout
- `scripts/run_overnight.sh`: run the recommended multi-stage overnight sequence

Recommended study order:

1. `compare_models_dev.json`
2. `compare_prompts_dev.json`
3. `compare_retrieval_dev.json`
4. `optimize_overnight.json`

## Artifact layout

Each experiment directory contains:

- `experiment.json`
- `summary.json`
- `best_candidate.json` when a winner or incumbent exists
- `results/results.csv`
- `results/results.jsonl`
- `rounds/round_<n>.json` for optimize mode
- `plots/*.csv`
- `plots/*.png`
- `runs/<candidate_id>/main/` launch artifacts
- `runs/<candidate_id>/eval/` launch artifacts
- `report.html`

## Why this tool stays internal

The optimizer is intentionally orchestration-only:

- main app = execution and review product
- eval tool = scoring and benchmarking
- optimizer = orchestration, candidate tracking, and decision reporting

This keeps product behavior, scoring behavior, and study orchestration separate without introducing a large shared runtime package.

## Related docs

- Main app docs: [../main-app/README.md](../main-app/README.md)
- Eval docs: [../eval/README.md](../eval/README.md)
- Contract surfaces: [../contracts/tool-contract-surfaces.md](../contracts/tool-contract-surfaces.md)
