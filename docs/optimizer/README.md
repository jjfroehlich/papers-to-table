# Optimizer companion

The optimizer is a CLI-first orchestration tool for bounded model, prompt, and retrieval studies.

It launches main-app runs, launches eval on the resulting run bundles, then writes experiment reports.

## What it is for

Use optimizer when you need to answer questions like:

- which model should be the current default?
- which prompt bundle performs best on the dev benchmark?
- which retrieval setting is safest to recommend?
- did a challenger beat the incumbent under the acceptance guardrails?

## Install

From the repository root:

```bash
python scripts/papers_to_table.py install
```

Low-level install:

```bash
cd tools/optimizer
python -m pip install -e .[dev]
```

## Recommended commands

### Compare models

```bash
python scripts/papers_to_table.py optimizer compare-models
```

### Optimize one model

```bash
python scripts/papers_to_table.py optimizer optimize-one-model
```

### Overnight sequence

```bash
python scripts/papers_to_table.py optimizer overnight
```

## Canonical presets

- `tools/optimizer/configs/compare_models.json`
- `tools/optimizer/configs/compare_prompts.json`
- `tools/optimizer/configs/compare_retrieval.json`
- `tools/optimizer/configs/compare_retrieval_modes.json`
- `tools/optimizer/configs/optimize_one_model.json`
- `tools/optimizer/configs/compare_models_overnight.json`
- `tools/optimizer/configs/optimize_overnight.json`

Smoke and fixture-manual presets exist for contract checks only.

## What each workflow means

### compare-models

- fixed candidate list
- same benchmark, same prompt stack, same retrieval defaults
- use when choosing among explicit model candidates

### optimize-one-model

- one baseline candidate
- bounded search space for a single model family
- use when you want to tune retrieval or similar knobs without changing the model family

### overnight

- multi-stage sequence
- compare models, prompts, retrieval settings, retrieval modes, then run the optimization stage
- writes a combined overnight manifest and aggregate report

## How outputs are organized

Each experiment writes an experiment directory with:

- `experiment.json`
- `summary.json`
- `best_candidate.json` when a winner exists
- `results/results.csv`
- `results/results.jsonl`
- `runs/{candidate_id}/main/`
- `runs/{candidate_id}/eval/`
- `plots/`
- `report.html`

## How to interpret reports

- **winner**: best benchmark result under the scoring and acceptance rules
- **recommended default**: operational recommendation after trust, degraded-mode, evidence, or runtime caveats are considered
- **degraded candidate**: a candidate that ran with capability degradation or contract caveats and should not be treated like a healthy peer

## Diagnosing bad runs

Check:

- experiment `summary.json`
- candidate rows in `results/results.jsonl`
- the candidate's nested main-app `run.json` and reviewer summary
- the nested eval `run_summary.json`
