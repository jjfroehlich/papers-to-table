# Extraction Experiment Results

This file is the durable record of extraction experiments, benchmark results, and ideas that were ruled out. Use it to decide what should be kept, rolled back, retested, or promoted.

New, untested ideas belong in `specs/extraction-improvement-backlog.md`. Once an idea is implemented, benchmarked, dev-checked, or rejected for conceptual reasons, move it here with enough detail that future work does not repeat the same experiment unknowingly.

## How To Use This File

- Add one experiment entry per implementation or conceptual decision.
- Record what changed, why it was tried, which branch/commit/run folder contains it, and what happened.
- Put quick single-suite results under `## Dev-Check Runs`.
- Put broader benchmark comparisons under `## Multi-Benchmark Comparisons`.
- Prefer comparing variants with the same model, benchmark set, replicate count, judge configuration, and cache state.

## Target

The current product target is to improve content correctness on the benchmark suite. 

## Current Recommendation

Keep `main` at `6efabd7` as the default extraction architecture for now. The per-cell baseline remains the best measured local architecture. Preserve the grouped extraction branches as research artifacts, but do not merge them into `main`.

## Branches

The requested slash-namespaced branch names could not be created in this working tree, so the experiment branches use flat names:

| Branch | Commit | Purpose |
|---|---|---|
| `main` | `6efabd7` | Pushed baseline before implementing the accuracy/speed ideas; kept as the per-cell accuracy reference. |
| `experiment-field-group-deterministic` | `ce960c2` | Field-group extraction with deterministic column planning and per-cell fallback. |
| `experiment-paper-batch` | `361f4f4` | Paper/row batch extraction without deterministic planning, using grouped structured calls and per-cell fallback. |

## Experiment Notes

### Per-Cell Baseline

- Status: keep as default.
- Branch/commit: `main` at `6efabd7`.
- Core behavior: extract each eligible cell independently.
- Strengths observed: best aggregate score in the three-benchmark comparison; conceptually most general.
- Weaknesses observed: many completion calls and long runtime.
- Decision: keep as current reference architecture while pursuing accuracy improvements with better models, retrieval, prompts, and parameter sweeps.

### Field-Group Deterministic

- Status: tested; preserve branch only.
- Branch/commit: `experiment-field-group-deterministic` at `ce960c2`.
- Ideas tested from the old improvement plan:
  - deterministic schema-level column planning
  - evidence cards
  - retrieval profiles driven by column planning
  - `field_group` extraction mode
  - grouped structured calls with per-cell fallback
  - optimizer knobs for extraction mode and planner mode
- Ideas only partially covered:
  - LLM-primary column planning was tried in earlier dev-check work, but the preserved branch uses deterministic planning because LLM planning was unstable.
  - schema-triggered vision and lazy rendering were configured/touched in the experiment path, but the decisive comparison did not prove a useful runtime win.
- Result: reduced completion-call count, but lower accuracy and no end-to-end runtime improvement in the broader comparison.
- Decision: do not merge into `main`. The deterministic planner may be too narrow for unexpected schemas unless it is made advisory rather than routing-authoritative.

### Paper-Batch

- Status: tested; preserve branch only.
- Branch/commit: `experiment-paper-batch` at `361f4f4`.
- Why it was tried: answer whether batching all cells from the same paper/row could give the speed benefits of batching without deterministic column planning.
- Core behavior:
  - no deterministic column planner
  - default retrieval behavior
  - one structured extraction call per paper/row batch
  - split outputs back into normal per-cell proposal/evidence artifacts
  - per-cell fallback for invalid, missing, or weak batch outputs
- Result: lowest aggregate score and no runtime improvement in the broader comparison.
- Decision: do not merge into `main`. Whole-paper/row batching is more general than deterministic field grouping, but current prompt/output reliability is not good enough.

### LLM-Primary Column Planning

- Status: tested in earlier dev-check iterations; not preserved as the recommended branch.
- Ideas tested from the old improvement plan:
  - LLM planner proposes grouping/retrieval/visual policies from schema text
  - deterministic validation clamps invalid planner output
- Observed issue: planning drift and overly aggressive validation lowered score in dev-check runs.
- Decision: keep as a future research direction only if planner output is advisory, heavily validated, and evaluated on synthetic non-benchmark schemas.

### Conservative Batch Gate

- Status: tested and rejected.
- Run: `dev_check_20260519-001805`.
- Idea: avoid batching unless the column group looked safe.
- Result: worse score and runtime than the faster field-group deterministic dev-check.
- Decision: do not continue this specific gating approach.

## Dev-Check Runs

Use this table for quick checks, especially single-dataset optimizer `dev-check` runs. These are useful for iteration but should not decide architecture alone.

| Run | Variant | Benchmark Scope | Score | Runtime | Notes |
|---|---|---|---:|---:|---|
| `20260518_144007_compare_models / run_20260518_134825_8etyzg` | per-cell-like model compare | Genome editing, partial interrupted replicate | 0.60 | 8.65 min app | Second genome-editing replicate; not final aggregate. |
| `dev_check_20260518-192047` | per-cell before figure-review state/hit fix | Genome editing dev-check | 0.56 | 9.46 min total | Before figure-review state/hit fix. |
| `dev_check_20260518-195533` | per-cell baseline | Genome editing dev-check | 0.62 | 9.28 min total | Best prior genome-editing dev-check score; corresponds conceptually to `main` at `6efabd7`. |
| `dev_check_20260518-230132` | partial planner/evidence-card wiring | Genome editing dev-check | 0.56 | 11.45 min total | Contract valid; not a recommended endpoint. |
| `dev_check_20260518-234727` | early real field-group attempt | Genome editing dev-check | n/a | 1.02 min total | Failed before scoring due grouped proposal diagnostics bug. |
| `dev_check_20260518-234927` | LLM planner field-group | Genome editing dev-check | 0.56 | 9.21 min total | Real grouped extraction plus LLM planner; valid contract. |
| `dev_check_20260519-000015` | stricter LLM planner validation | Genome editing dev-check | 0.50 | 10.10 min total | LLM planning/validation was too aggressive. |
| `dev_check_20260519-001119` | field-group deterministic | Genome editing dev-check | 0.58 | 5.59 min total | Fast single dev-check result; did not generalize to the broader comparison. |
| `dev_check_20260519-001805` | conservative batch gate | Genome editing dev-check | 0.54 | 11.86 min total | Worse score and runtime; rejected. |

## Multi-Benchmark Comparisons

### 2026-05 Three-Architecture Comparison

Configuration:

- model: `google/gemma-4-e4b`
- benchmarks: genome editing, MPRA, spatial transcriptomics
- replicates: 3
- runner: direct optimizer CLI from `tools/optimizer` because the Windows/WSL wrapper failed in this sandbox

Aggregate results:

| Variant | Branch | Run Folder | Score | Total Runtime | Completion Calls | Result |
|---|---|---|---:|---:|---:|---|
| Per-cell baseline | `main` | `manual_baseline_per_cell_3bench_3rep_retry` | 0.6517 | 86.22 min | 138 | Best score; keep as default. |
| Field-group deterministic | `experiment-field-group-deterministic` | `manual_field_group_deterministic_3bench_3rep` | 0.6040 | 87.57 min | 114 | Fewer calls, lower score, not faster overall. |
| Paper-batch | `experiment-paper-batch` | `manual_paper_batch_3bench_3rep` | 0.5681 | 88.81 min | 113 | Lowest score, not faster overall. |

Per-benchmark results:

| Variant | MPRA Score | MPRA Runtime | Genome Editing Score | Genome Runtime | Spatial Score | Spatial Runtime |
|---|---:|---:|---:|---:|---:|---:|
| Per-cell baseline | 0.7083 | 23.46 min | 0.6067 | 30.14 min | 0.6400 | 32.61 min |
| Field-group deterministic | 0.6319 | 16.61 min | 0.5267 | 28.54 min | 0.6533 | 42.43 min |
| Paper-batch | 0.6042 | 16.51 min | 0.5067 | 31.38 min | 0.5933 | 40.92 min |

Operational notes:

- All three successful comparison runs completed with `scored=true`, `contract_valid=true`, and zero failed or degraded replicates.
- The first baseline attempt at `manual_baseline_per_cell_3bench_3rep` completed app execution but evaluation could not write its run folder due a permissions error; the successful retry is the comparable baseline.
- The grouped variants reduced structured completion calls but did not reduce end-to-end runtime in the full comparison.
- Field-group deterministic and paper-batch per-benchmark rows were marked with `judge_instability_observed`; that caveat did not affect run completion but should temper fine-grained interpretation.

## Lessons Learned

- The old improvement plan was tested substantially, but not all parts earned promotion.
- Batching multiple cells into one response can reduce call count while still losing wall-clock time elsewhere.
- Accuracy loss from grouped extraction is currently more costly than the call-count savings.
- Deterministic planning is fast and auditable, but it risks making the app less general when schemas do not fit the planner's assumptions.
- Paper-batch is conceptually more general than deterministic field grouping, but it still lost accuracy because the model had to satisfy too many cells in one response.
- The next accuracy push should start from the per-cell baseline and test more capable models, retrieval changes, prompt changes, and benchmark parameters.

## Result Entry Template

Use this when adding future experiments:

```markdown
### Experiment Name

- Status:
- Branch/commit:
- Run folders:
- Idea tested:
- Implementation summary:
- Dev-check result:
- Multi-benchmark result:
- Failure modes:
- Decision:
```
