# Extraction Benchmark Ledger

This file records extraction/runtime experiments so implementation variants can be compared without relying on memory or transient optimizer folders.

## Goal

The current product target is to reach or exceed `0.80` content correctness on the benchmark suite. That target is based on the best known external Codex-agent result, and local app variants should be judged against it rather than only against each other.

## How To Read This

- `Score` is the optimizer/eval primary metric, currently `content_correctness`, unless noted otherwise.
- `Runtime` is the reported app or dev-check runtime from the run artifact. Keep the unit explicit.
- Single dev-check runs are useful for direction, but not enough to select a default by themselves.
- Prefer comparing variants on the same benchmark suite, model set, replicate count, and judge configuration.

## Current Variants

| Variant | Intended Branch | Main Behavior | Status |
|---|---|---|---|
| `per_cell_accuracy` | `main` or `baseline/per-cell-accuracy` | Per-cell extraction, figure review enabled, no deterministic planner/batching | Current best accuracy reference |
| `field_group_deterministic` | `experiment/field-group-deterministic` | Deterministic schema planner, grouped extraction by paper/group, fallback per cell | Fastest useful measured variant so far |
| `paper_batch` | `experiment/paper-batch` | No deterministic planner; group all eligible cells from the same paper/row into one extraction call, fallback per cell | Proposed next experiment |
| `llm_planner_field_group` | `experiment/llm-planner-field-group` | LLM-primary column planner plus grouped extraction | Implemented/tested, not recommended as default yet |

## Run Results

| Run | Variant | Benchmark Scope | Score | Runtime | Notes |
|---|---|---|---:|---:|---|
| `20260518_144007_compare_models / run_20260518_134825_8etyzg` | per-cell-like model compare | Genome editing, partial interrupted replicate | 0.60 | 8.65 min app | Second genome-editing replicate; not final aggregate |
| `dev_check_20260518-192047` | per-cell before figure-review state/hit fix | Genome editing dev-check | 0.56 | 9.46 min total | Before figure-review state/hit fix |
| `dev_check_20260518-195533` | `per_cell_accuracy` | Genome editing dev-check | 0.62 | 9.28 min total | Best score observed; figure-review state/hit fix included |
| `dev_check_20260518-230132` | partial planner/evidence-card wiring | Genome editing dev-check | 0.56 | 11.45 min total | Contract valid; not a recommended endpoint |
| `dev_check_20260518-234727` | early real field-group attempt | Genome editing dev-check | n/a | 1.02 min total | Failed: grouped proposal diagnostics bug before scoring |
| `dev_check_20260518-234927` | `llm_planner_field_group` | Genome editing dev-check | 0.56 | 9.21 min total | Real grouped extraction plus LLM planner; valid contract |
| `dev_check_20260519-000015` | stricter LLM planner validation | Genome editing dev-check | 0.50 | 10.10 min total | LLM planning/validation was too aggressive |
| `dev_check_20260519-001119` | `field_group_deterministic` | Genome editing dev-check | 0.58 | 5.59 min total | Best speed/accuracy tradeoff observed; deterministic planner, grouped extraction |
| `dev_check_20260519-001805` | conservative batch gate | Genome editing dev-check | 0.54 | 11.86 min total | Worse score and runtime; gate was rolled back |

## Observations

- `dev_check_20260518-195533` remains the accuracy leader on the genome-editing dev-check.
- `dev_check_20260519-001119` is materially faster while staying close in score, but it uses deterministic schema routing and grouped extraction.
- Neither local variant is close to the longer-term `0.80` target yet; these runs are mainly about choosing the right local architecture for the next round of accuracy work.
- LLM-primary column planning has not yet earned default status. It introduced planning drift and worse scores in the tested runs.
- Conservative manual gating of batch columns made both speed and accuracy worse in the measured run.
- The next useful experiment is `paper_batch`: no deterministic planner, normal per-cell retrieval, one structured extraction call per paper/row, per-cell fallback for missing/invalid/weak cells.

## Branch Strategy

Recommended branch layout:

| Branch | Purpose |
|---|---|
| `main` | Keep the pushed, best-known accuracy baseline if it corresponds to `dev_check_20260518-195533`. |
| `experiment/field-group-deterministic` | Preserve the `dev_check_20260519-001119` implementation and results. |
| `experiment/paper-batch` | Build and test the no-planner whole-paper/row batch mode. |
| `experiment/llm-planner-field-group` | Keep LLM planner work isolated until it proves stable across datasets. |

Use one benchmark command family per branch and record results here immediately after each run.

## Proposed Next Comparison

Run the same suite for:

1. `per_cell_accuracy`
2. `field_group_deterministic`
3. `paper_batch`

Minimum useful comparison:

- same model: `google/gemma-4-e4b`
- benchmarks: genome editing, MPRA, spatial transcriptomics
- replicates: at least 3 if runtime permits

Decision rule:

- Choose `per_cell_accuracy` if it consistently wins by more than about 0.03-0.04 score.
- Choose `field_group_deterministic` or `paper_batch` as a fast mode if it stays within about 0.03-0.04 score while cutting runtime meaningfully.
- Promote `paper_batch` over deterministic field groups if it matches speed closely and generalizes better across datasets.
