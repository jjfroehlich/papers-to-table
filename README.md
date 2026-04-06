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

See tests for minimal working examples.

## Artifacts

The experiment directory contains:

- `experiment.json`
- `candidates/<candidate_id>/candidate.json`
- `results/results.csv`
- `results/results.jsonl`
- `rounds/round_<n>.json` (optimize mode)
- `best_candidate.json` (optimize mode)
- `plots/*.png`
- `plots/*.csv`

## Holdout behavior

- `optimize`: validate final promoted best on holdout.
- `compare`: optional top-k holdout checks for reporting, not dev-search ranking.
