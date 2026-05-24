# Experiment Results

This file is the durable evidence record for completed experiments, benchmark results, rejected ideas, and decisions. Its current contents focus on extraction quality and runtime. Untested or not-yet-resolved improvement ideas belong in `specs/improvement-ideas.md`.

## Outline

- [Purpose And Rules](#purpose-and-rules)
- [Current Recommendation](#current-recommendation)
- [Result Entry Format](#result-entry-format)
- [Latest Key Findings](#latest-key-findings)
- [Experiment Results](#experiment-results)
- [Dev-Check Runs](#dev-check-runs)
- [Multi-Benchmark Comparisons](#multi-benchmark-comparisons)
- [Rejected Or Superseded Ideas](#rejected-or-superseded-ideas)
- [Lessons Learned](#lessons-learned)
- [Appendix: Historical Branches](#appendix-historical-branches)

## Purpose And Rules

- Add completed tests, evals, benchmark comparisons, dev-checks that change a decision, and conceptual rejections here.
- New ideas start in `specs/improvement-ideas.md`; when implemented, benchmarked, dev-checked, rejected, or ruled out, record the evidence here.
- If partial evidence informs an idea but does not decide it, keep the idea in the ideas file with an `Evidence so far:` line and record the tested evidence here.
- If an idea is rejected, remove it from the ideas file and add it under [Rejected Or Superseded Ideas](#rejected-or-superseded-ideas).
- Always include model IDs or source labels alongside optimizer candidate IDs. Do not write only `cand_0001`; write `cand_0001 / google/gemma-4-e4b`.
- Prefer comparisons with the same benchmark set, replicate count, model, judge configuration, and cache state.

Entry length guidance:

- Normal result entries: 120-250 words plus one compact table if useful.
- Large multi-benchmark entries: 300-600 words, starting with a short conclusion before details.
- Dev-check table rows: one line each. Add a dated result entry only when the dev-check changes a decision.

Every result entry should include:

- date
- run folder or commit
- candidate/variant names and model IDs or source labels
- benchmark scope
- score and runtime
- key diagnostics
- interpretation
- decision

## Current Recommendation

Keep `main` at `6efabd7` as the default extraction architecture for now. The per-cell baseline remains the best measured local architecture. Preserve grouped extraction branches as research artifacts, but do not merge them into `main`.

The next improvement push should start from per-cell extraction and focus on schema-aware value selection, retrieval/context quality, prompt repair by failure class, and model/runtime tradeoffs.

## Result Entry Format

```markdown
### YYYY-MM-DD Short Experiment Name

Conclusion: one sentence with the decision.

- Run/commit:
- Candidates and models:
- Benchmark scope:
- Result:
- Runtime/cost:
- Key diagnostics:
- Interpretation:
- Decision:
```

## Latest Key Findings

- The strongest app candidate in the 2026-05-24 model comparison was `cand_0005 / qwen/qwen3.6-27b` with score `0.6748`, but it was much slower than the other app candidates.
- The fastest app candidate was `cand_0002 / openai/gpt-oss-20b` with score `0.5552`; speed alone did not justify the accuracy loss.
- External Codex tables scored higher than app candidates, which shows headroom but is not directly comparable to normal app execution.
- Hard columns are mostly schema/value-semantics failures: representative figure panels, exact architecture strings, numeric maxima, sequence/barcode length disambiguation, and methods-section physical parameters.
- Batching/grouped extraction has repeatedly reduced call count without improving end-to-end runtime or correctness enough to replace per-cell extraction.

## Experiment Results

### 2026-05-24 Model Comparison And Failure Analysis

Conclusion: `cand_0005 / qwen/qwen3.6-27b` was the best app candidate, but its runtime cost means the next work should improve per-cell value selection and retrieval rather than simply switching every run to the slowest model.

- Run/commit: `tools/optimizer/runs/20260524_020807_compare_models`
- Candidates and models: external gold, external Codex outputs, `cand_0001 / google/gemma-4-e4b`, `cand_0002 / openai/gpt-oss-20b`, `cand_0003 / mistralai/ministral-3-14b-reasoning`, `cand_0004 / zai-org/glm-4.6v-flash`, `cand_0005 / qwen/qwen3.6-27b`
- Benchmark scope: genome editing, MPRA, spatial transcriptomics; 3 replicates
- Result: best app score was `0.6748` from `cand_0005 / qwen/qwen3.6-27b`; best external non-gold score was `0.8237`
- Runtime/cost: `cand_0005 / qwen/qwen3.6-27b` took `12255 sec` total; `cand_0002 / openai/gpt-oss-20b` took `2871 sec`
- Key diagnostics: all non-gold candidates had `judge_instability_observed`; structured-output failures were material for Qwen, GLM, and Ministral candidates
- Interpretation: model choice matters, but many failures are generic extraction semantics that should be addressed before making a slower model the default
- Decision: keep stronger-model sweeps active, but prioritize schema-aware candidate selection, retrieval improvements, and runtime-aware gates

Hard-column analysis from `results/proposal_tables/column_difficulty.csv` and app-only cell review:

| Benchmark | Column | App Accuracy | Common failure mode |
|---|---:|---:|---|
| Spatial transcriptomics | Representative spatial figure | 0.04 | Selected plausible but non-gold panels; often favored visually descriptive panels over the canonical representative panel. |
| MPRA | Length of sequences (bp) | 0.28 | Confused insert/library length with spacer length, motif length, barcode length, or unrelated percentages. |
| Genome editing | Main or best editor architecture | 0.31 | Returned shorthand system names or enhancement components instead of full architecture/component strings. |
| Genome editing | Max editing efficiency (%) | 0.33 | Missed maxima in figures/tables, returned blanks, or selected non-maximum/nearby percentages. |
| Genome editing | Architecture source figure | 0.35 | Chose figures that mention architecture generally instead of the specific source panel for the selected architecture. |
| Spatial transcriptomics | Section thickness (micrometer) | 0.36 | Retrieval often missed methods/supplementary sectioning details; models substituted unrelated section/span text or blanked. |
| MPRA | Barcode length (bp) | 0.43 | Confused barcode length with sequence length, motif embedding length, or decided `no BC` despite barcode evidence. |

### 2026-05 Three-Architecture Comparison

Conclusion: keep per-cell extraction as the default architecture; grouped extraction variants reduced completion-call count but lost correctness and did not improve end-to-end runtime.

- Run/commit: `manual_baseline_per_cell_3bench_3rep_retry`, `manual_field_group_deterministic_3bench_3rep`, `manual_paper_batch_3bench_3rep`; baseline branch `main` at `6efabd7`
- Candidates and models: per-cell baseline / `google/gemma-4-e4b`; field-group deterministic / `google/gemma-4-e4b`; paper-batch / `google/gemma-4-e4b`
- Benchmark scope: genome editing, MPRA, spatial transcriptomics; 3 replicates
- Result: per-cell baseline scored `0.6517`; field-group deterministic scored `0.6040`; paper-batch scored `0.5681`
- Runtime/cost: per-cell baseline took `86.22 min`; field-group deterministic took `87.57 min`; paper-batch took `88.81 min`
- Key diagnostics: all successful comparison runs completed with `scored=true`, `contract_valid=true`, and zero failed or degraded replicates; grouped variants had `judge_instability_observed`
- Interpretation: batching can reduce structured completion calls, but the current grouped prompts make the model satisfy too many cells at once and lose accuracy
- Decision: preserve grouped branches as research artifacts only; pursue accuracy improvements from the per-cell baseline

Aggregate results:

| Variant | Branch | Model | Run Folder | Score | Total Runtime | Completion Calls | Result |
|---|---|---|---|---:|---:|---:|---|
| Per-cell baseline | `main` | `google/gemma-4-e4b` | `manual_baseline_per_cell_3bench_3rep_retry` | 0.6517 | 86.22 min | 138 | Best score; keep as default. |
| Field-group deterministic | `experiment-field-group-deterministic` | `google/gemma-4-e4b` | `manual_field_group_deterministic_3bench_3rep` | 0.6040 | 87.57 min | 114 | Fewer calls, lower score, not faster overall. |
| Paper-batch | `experiment-paper-batch` | `google/gemma-4-e4b` | `manual_paper_batch_3bench_3rep` | 0.5681 | 88.81 min | 113 | Lowest score, not faster overall. |

## Dev-Check Runs

Use this table for quick checks, especially single-dataset optimizer `dev-check` runs. These are useful for iteration but should not decide architecture alone.

| Run | Variant | Model / Source | Benchmark Scope | Score | Runtime | Notes |
|---|---|---|---|---:|---:|---|
| `20260518_144007_compare_models / run_20260518_134825_8etyzg` | per-cell-like model compare | not recorded in summary | Genome editing, partial interrupted replicate | 0.60 | 8.65 min app | Second genome-editing replicate; not final aggregate. |
| `dev_check_20260518-192047` | per-cell before figure-review state/hit fix | `google/gemma-4-e4b` | Genome editing dev-check | 0.56 | 9.46 min total | Before figure-review state/hit fix. |
| `dev_check_20260518-195533` | per-cell baseline | `google/gemma-4-e4b` | Genome editing dev-check | 0.62 | 9.28 min total | Best prior genome-editing dev-check score; corresponds conceptually to `main` at `6efabd7`. |
| `dev_check_20260518-230132` | partial planner/evidence-card wiring | `google/gemma-4-e4b` | Genome editing dev-check | 0.56 | 11.45 min total | Contract valid; not a recommended endpoint. |
| `dev_check_20260518-234727` | early real field-group attempt | `google/gemma-4-e4b` | Genome editing dev-check | n/a | 1.02 min total | Failed before scoring due grouped proposal diagnostics bug. |
| `dev_check_20260518-234927` | LLM planner field-group | `google/gemma-4-e4b` | Genome editing dev-check | 0.56 | 9.21 min total | Real grouped extraction plus LLM planner; valid contract. |
| `dev_check_20260519-000015` | stricter LLM planner validation | `google/gemma-4-e4b` | Genome editing dev-check | 0.50 | 10.10 min total | LLM planning/validation was too aggressive. |
| `dev_check_20260519-001119` | field-group deterministic | `google/gemma-4-e4b` | Genome editing dev-check | 0.58 | 5.59 min total | Fast single dev-check result; did not generalize to broader comparison. |
| `dev_check_20260519-001805` | conservative batch gate | `google/gemma-4-e4b` | Genome editing dev-check | 0.54 | 11.86 min total | Worse score and runtime; rejected. |

## Multi-Benchmark Comparisons

| Date | Run Folder | Candidates / Models | Scope | Best Score | Decision |
|---|---|---|---|---:|---|
| 2026-05-24 | `20260524_020807_compare_models` | app model comparison plus external Codex/gold sources | 3 benchmarks, 3 replicates | 0.6748 app; 0.8237 external | Keep model sweep active, but fix value semantics and runtime gates first. |
| 2026-05 | manual three-architecture runs | per-cell, field-group deterministic, paper-batch / `google/gemma-4-e4b` | 3 benchmarks, 3 replicates | 0.6517 | Keep per-cell baseline as default. |

## Rejected Or Superseded Ideas

### Field-Group Deterministic

- Status: tested; preserve branch only.
- Branch/commit: `experiment-field-group-deterministic` at `ce960c2`.
- Model/source: `google/gemma-4-e4b`.
- Result: fewer structured completion calls than per-cell extraction, but lower aggregate score and no end-to-end runtime improvement in the broader comparison.
- Decision: do not merge. Deterministic planning may return as advisory metadata, but it should not be routing-authoritative.

### Paper-Batch

- Status: tested; preserve branch only.
- Branch/commit: `experiment-paper-batch` at `361f4f4`.
- Model/source: `google/gemma-4-e4b`.
- Result: lowest aggregate score in the three-architecture comparison and no runtime improvement.
- Decision: do not merge. Whole-paper/row batching is conceptually general, but current prompt/output reliability is not good enough.

### LLM-Primary Column Planning

- Status: tested in earlier dev-check iterations; not preserved as the recommended branch.
- Model/source: `google/gemma-4-e4b`.
- Result: planning drift and overly aggressive validation lowered score in dev-check runs.
- Decision: only revisit if planner output is advisory, heavily validated, and evaluated on synthetic non-benchmark schemas.

### Conservative Batch Gate

- Status: tested and rejected.
- Run: `dev_check_20260519-001805`.
- Model/source: `google/gemma-4-e4b`.
- Result: worse score and runtime than the faster field-group deterministic dev-check.
- Decision: do not continue this specific gating approach.

## Lessons Learned

- Accuracy loss from grouped extraction is currently more costly than call-count savings.
- Deterministic planning is fast and auditable, but risks making the app less general when schemas do not fit planner assumptions.
- The best near-term path is better per-cell evidence/value selection, schema-aware numeric and identifier handling, and runtime-aware model/vision gating.
- Judge disagreement and `judge_instability_observed` require caution when interpreting small score differences.
- Structured-output reliability must be tracked alongside correctness and runtime in future model sweeps.

## Appendix: Historical Branches

The requested slash-namespaced branch names could not be created in this working tree, so the experiment branches use flat names:

| Branch | Commit | Purpose |
|---|---|---|
| `main` | `6efabd7` | Pushed baseline before implementing the accuracy/speed ideas; kept as the per-cell accuracy reference. |
| `experiment-field-group-deterministic` | `ce960c2` | Field-group extraction with deterministic column planning and per-cell fallback. |
| `experiment-paper-batch` | `361f4f4` | Paper/row batch extraction without deterministic planning, using grouped structured calls and per-cell fallback. |
