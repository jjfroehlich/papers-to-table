# Experiment Results

This file is the durable evidence and decision record for tested app-improvement ideas. It should make clear what was tried, how it was evaluated, what decision followed, and what should or should not be retested.

## Outline

- [Purpose And Rules](#purpose-and-rules)
- [Decision Entry Format](#decision-entry-format)
- [Dev-Check Runs](#dev-check-runs)
- [Full-Benchmark Idea Evaluations](#full-benchmark-idea-evaluations)
- [Kept Or Partially Kept Ideas](#kept-or-partially-kept-ideas)
- [Rejected Or Superseded Ideas](#rejected-or-superseded-ideas)
- [Appendix: Historical Branches](#appendix-historical-branches)

## Purpose And Rules

This file owns tested evidence and decisions. `improvement-ideas.md` owns prioritized ideas that are untested, partly tested, or still worth testing.

- Record ideas and decisions, not long chronological run narratives.
- Add a decision entry once an idea has been benchmarked, dev-checked, rejected, superseded, kept, or partly kept.
- Use the run tables for comparability, then keep detailed interpretation in the linked decision entry.
- A dev-check run is the default first evaluation for an implemented idea. Every dev-check row should link to the decision entry it informs.
- A full-benchmark evaluation should usually use three benchmark datasets, three replicates, and `google/gemma-4-e4b` unless the model itself is the idea. Prefer the model-compare config where possible so retrieval, prompts, and other parameters stay comparable.
- Every result entry must include candidate or variant names, model IDs, benchmark scope, score, runtime, key diagnostics, interpretation, and decision.
- Never refer only to `cand_0001` or similar IDs. Include the model or source next to the candidate ID, for example `cand_0001 / google/gemma-4-e4b`.
- Do not add broad sections named after analyses such as "model comparison" or "three-architecture comparison". Distill those analyses into kept, partly kept, rejected, or superseded idea entries, or use them to update `improvement-ideas.md`.
- If an idea is rejected, remove it from `improvement-ideas.md` and add a clear retest boundary here.
- If an idea remains worth testing after partial evidence, keep or reprioritize it in `improvement-ideas.md` and add an `Evidence so far` line there.

Normal decision entries should be 120-250 words. Larger multi-benchmark decisions may be 300-600 words, but must start with the conclusion in the `Decision` or `Result` row. Run table rows stay one line each.

## Decision Entry Format

Use one table per tested idea. Keep row names consistent so future agents can scan decisions quickly.

| Field | Required content |
| --- | --- |
| Status | `Kept`, `Partially kept`, `Rejected`, or `Superseded`. |
| Tested idea | Short name of the idea or implementation strategy. |
| What was tested | Branch, commit, config, mode, candidate IDs with model/source IDs, and any important implementation constraints. |
| Why tested | The hypothesis or expected benefit. |
| Evidence | Links or IDs for dev-check runs, full-benchmark runs, model-compare runs, or proposal/log analyses. |
| Scope and models | Benchmark datasets, replicate count, model IDs, and comparison baseline. |
| Result | Score, runtime, call count when available, key diagnostics, and whether the expected benefit appeared. |
| Decision | What to keep, reject, supersede, or carry forward. |
| Retest boundary | Conditions under which this exact idea should or should not be tried again. |

## Dev-Check Runs

| Date | Run | Idea entry | Model/source | Scope | Score | Runtime | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-18 | `20260518_144007_compare_models / run_20260518_134825_8etyzg` | [Model Sweep And Failure Analysis](#model-sweep-and-failure-analysis) | model not recorded | Genome editing partial interrupted replicate | 0.60 | 8.65 min app | Partial second replicate; not a final aggregate. |
| 2026-05-18 | `dev_check_20260518-192047` | [Per-Cell Baseline Architecture](#per-cell-baseline-architecture) | `google/gemma-4-e4b` | Genome editing | 0.56 | 9.46 min | Superseded by the later baseline dev-check after figure-review state/hit fixes. |
| 2026-05-18 | `dev_check_20260518-195533` | [Per-Cell Baseline Architecture](#per-cell-baseline-architecture) | `google/gemma-4-e4b` | Genome editing | 0.62 | 9.28 min | Best prior baseline dev-check, main `6efabd7`. |
| 2026-05-18 | `dev_check_20260518-230132` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.56 | 11.45 min | Partial planner/evidence-card wiring; not a recommended endpoint. |
| 2026-05-18 | `dev_check_20260518-234727` | [Field-Group Deterministic](#field-group-deterministic) | `google/gemma-4-e4b` | Genome editing | n/a | 1.02 min | Failed before scoring due grouped proposal diagnostics bug. |
| 2026-05-18 | `dev_check_20260518-234927` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.56 | 9.21 min | Valid contract, but no score improvement. |
| 2026-05-19 | `dev_check_20260519-000015` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.50 | 10.10 min | Planning and validation were too aggressive. |
| 2026-05-19 | `dev_check_20260519-001119` | [Field-Group Deterministic](#field-group-deterministic) | `google/gemma-4-e4b` | Genome editing | 0.58 | 5.59 min | Fast single dev-check, but the speed benefit did not generalize. |
| 2026-05-19 | `dev_check_20260519-001805` | [Conservative Batch Gate](#conservative-batch-gate) | `google/gemma-4-e4b` | Genome editing | 0.54 | 11.86 min | Worse score and runtime; rejected. |
| 2026-06-02 | `dev_check_20260602_structured_calibration / run_20260601_223720_dh6afy` | [Per-Cell Baseline Architecture](#per-cell-baseline-architecture) | `cand_0001 / google/gemma-4-e4b` | MPRA dev-check, one replicate, current commit `17eb3a0` | 0.50 | 15.51 min total; 14.22 min app; 1.30 min eval | Current-code calibration datapoint: structured scorer emitted one numeric hard mismatch, zero adjudication-eligible failures; dual text judges completed but disagreed on 25% of comparable text cells. |

## Full-Benchmark Idea Evaluations

Use this table for full idea evaluations that should be compared across runs. Prefer three benchmark datasets, three replicates, and `google/gemma-4-e4b` unless the evaluated idea is model choice.

| Date | Evaluation | Idea entry | Run folder | Model/source | Scope | Score | Runtime | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05 | Three-architecture comparison | [Per-Cell Baseline Architecture](#per-cell-baseline-architecture) | `manual_baseline_per_cell_3bench_3rep_retry` | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics; 3 reps | 0.6517 | 86.22 min; 138 calls | Kept as comparison baseline. |
| 2026-05 | Three-architecture comparison | [Field-Group Deterministic](#field-group-deterministic) | `manual_field_group_deterministic_3bench_3rep` | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics; 3 reps | 0.6040 | 87.57 min; 114 calls | Rejected as default architecture. |
| 2026-05 | Three-architecture comparison | [Paper-Batch](#paper-batch) | `manual_paper_batch_3bench_3rep` | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics; 3 reps | 0.5681 | 88.81 min; 113 calls | Rejected as default architecture. |
| 2026-05-24 | Model-compare and failure analysis | [Model Sweep And Failure Analysis](#model-sweep-and-failure-analysis) | `tools/optimizer/runs/20260524_020807_compare_models` | `cand_0001 / google/gemma-4-e4b`; `cand_0002 / openai/gpt-oss-20b`; `cand_0003 / mistralai/ministral-3-14b-reasoning`; `cand_0004 / zai-org/glm-4.6v-flash`; `cand_0005 / qwen/qwen3.6-27b`; external gold; external Codex outputs | Genome editing, MPRA, spatial transcriptomics; 3 reps | Best app: `cand_0005 / qwen/qwen3.6-27b` 0.6748; fastest app: `cand_0002 / openai/gpt-oss-20b` 0.5552; best external non-gold 0.8237 | Best app runtime 12255 sec; fastest app runtime 2871 sec | Partially kept as evidence for model selection, retrieval, and structured-output ideas; no default model change from this alone. |
| 2026-06-02 | Direct model comparison and proposal failure analysis | [Model Sweep And Failure Analysis](#model-sweep-and-failure-analysis) | `tools/optimizer/runs/20260602_compare_models_direct` | `cand_0001 / google/gemma-4-e4b`; `cand_0002 / openai/gpt-oss-20b`; `cand_0003 / mistralai/ministral-3-14b-reasoning`; `cand_0004 / zai-org/glm-4.6v-flash`; `cand_0005 / qwen/qwen3.6-27b`; `ext_codex`; `ext_agentkit`; `ext_kitchin`; `ext_gold` | Genome editing, MPRA, spatial transcriptomics; 3 reps | Best app: `cand_0005 / qwen/qwen3.6-27b` 0.6469; fastest app: `cand_0002 / openai/gpt-oss-20b` 0.5319; best external non-gold `ext_agentkit` 0.8000 | Best app 11496 sec; fastest app 4332 sec; external non-gold 2992-3346 sec | Partially kept. Confirms model-only gains are not enough; proposal analysis points to schema-semantic value selection, paper-level candidate inventories, recovery, and structured-output reliability. |

## Kept Or Partially Kept Ideas

### Per-Cell Baseline Architecture

| Field | Details |
| --- | --- |
| Status | Kept as the comparison baseline. |
| Tested idea | Per-cell extraction with focused retrieval and independent proposals for target cells. |
| What was tested | `main` at commit `6efabd7`, run `manual_baseline_per_cell_3bench_3rep_retry`, model `google/gemma-4-e4b`. |
| Why tested | Establish a stable reference before grouped, batched, or planner-led extraction changes. |
| Evidence | Dev-checks `dev_check_20260518-192047` and `dev_check_20260518-195533`; full-benchmark row in [Full-Benchmark Idea Evaluations](#full-benchmark-idea-evaluations). |
| Scope and models | Genome editing, MPRA, and spatial transcriptomics; three replicates; `google/gemma-4-e4b`. |
| Result | Score 0.6517, runtime 86.22 min, 138 completion calls. It beat field-group deterministic and paper-batch variants on score and runtime stability. |
| Decision | Keep this as the baseline architecture for future experiments until a new idea beats it on correctness without increasing runtime materially. |
| Retest boundary | Retest the baseline only after core retrieval, prompt, scoring, or model defaults change. New experiments should compare against this or a clearly documented newer baseline. |

### Model Sweep And Failure Analysis

| Field | Details |
| --- | --- |
| Status | Partially kept as evidence for active ideas, not as a direct default-model decision. |
| Tested idea | Compare several local and external model/source candidates and inspect failure modes on hard columns. |
| What was tested | Runs `tools/optimizer/runs/20260524_020807_compare_models` and `tools/optimizer/runs/20260602_compare_models_direct` with external gold, external Codex-style outputs, `cand_0001 / google/gemma-4-e4b`, `cand_0002 / openai/gpt-oss-20b`, `cand_0003 / mistralai/ministral-3-14b-reasoning`, `cand_0004 / zai-org/glm-4.6v-flash`, and `cand_0005 / qwen/qwen3.6-27b`. |
| Why tested | Determine whether model choice alone could improve correctness while keeping runtime stable, and identify columns that remained hard across candidates. |
| Evidence | Full-benchmark rows in [Full-Benchmark Idea Evaluations](#full-benchmark-idea-evaluations), `experiment/results/proposal_tables/column_difficulty.csv`, `column_difficulty_by_candidate.csv`, proposal logs, candidate diagnostics, and model-compare summary artifacts. |
| Scope and models | Genome editing, MPRA, and spatial transcriptomics; three replicates; multi-model plus external sources. |
| Result | The 2026-06-02 run again made `cand_0005 / qwen/qwen3.6-27b` the best app candidate, but only at 0.6469 and 11496 sec versus `cand_0001 / google/gemma-4-e4b` at 0.5718 and 8061 sec. `cand_0002 / openai/gpt-oss-20b` was faster at 4332 sec but scored 0.5319. `cand_0004 / zai-org/glm-4.6v-flash` was not competitive at 0.3965 and had the most structured errors. External non-gold outputs scored 0.7841-0.8000 in 2992-3346 sec, showing that the missing capability is not just model strength. The largest app-vs-external gaps were MPRA sequence length, episomal/genomic status, section thickness, architecture/source-figure fields, DNA extraction/genotyping method, barcode length/location, and links. Proposal logs show wrong-value selection: spacer lengths chosen instead of insert length, barcode count chosen instead of barcode length, STARR-seq 3' UTR treated as barcode location when no barcode was used, broad genome/species evidence treated as model system, and figure numbers returned without the required panel. |
| Follow-up | The 2026-05-26 compare run confirmed text fields used LLM judges by default, including exact matches in `20260517_gold` (formerly `20260517_gold_positive_control`); deterministic text scored-cell count was 0 for external and app candidates. It also exposed Windows path failures for long external-result candidate ids, now addressed by short explicit ids such as `ext_codex`, `ext_agentkit`, `ext_kitchin`, and `ext_gold`. The 2026-06-02 diagnostics show retrieval chunk and IDF repeated-work counters at zero for app candidates, so runtime work should focus on fewer/better model calls rather than rebuilding the same retrieval state. Figure review was broadly triggered but sparsely useful: app candidates triggered 26-60 cells each, attempted 0-6, and found only 0-2 useful cells. |
| Decision | Keep model sweep, candidate-selection, retrieval, targeted recovery, judge-calibration, and structured-output improvements as active ideas in `improvement-ideas.md`. Do not switch the default model based on these runs because the best app model came with a large runtime cost and still missed schema-semantic distinctions. Deprioritize `zai-org/glm-4.6v-flash` for this workflow unless its structured-output and evidence quality improve. |
| Retest boundary | Repeat model sweeps only with a comparable three-benchmark config and record model IDs, score, runtime, calls, structured-output failures, failed structured elapsed time, figure-review trigger/attempt/useful counts, retrieval repeated-work counters, and hard-column changes. A default-model change needs a full benchmark result that improves correctness without unacceptable runtime or reliability cost. |

## Rejected Or Superseded Ideas

### Field-Group Deterministic

| Field | Details |
| --- | --- |
| Status | Rejected as a default extraction architecture; partly superseded by advisory-only planning ideas. |
| Tested idea | Deterministically group related columns into field groups, extract grouped proposals, then fall back to per-cell extraction when needed. |
| What was tested | Branch `experiment-field-group-deterministic` at commit `ce960c2`; dev-checks `dev_check_20260518-234727` and `dev_check_20260519-001119`; full run `manual_field_group_deterministic_3bench_3rep`; model `google/gemma-4-e4b`. |
| Why tested | Reduce completion calls and runtime by sharing evidence and model calls across related columns while preserving per-cell fallback. |
| Evidence | Dev-check table rows and full-benchmark row in this file. |
| Scope and models | Genome editing dev-checks; full benchmark across genome editing, MPRA, and spatial transcriptomics with three replicates; `google/gemma-4-e4b`. |
| Result | Full score 0.6040 versus 0.6517 for the per-cell baseline. Runtime was 87.57 min versus baseline 86.22 min, despite fewer calls: 114 versus 138. The promising single dev-check runtime of 5.59 min did not generalize. |
| Decision | Do not merge or restore this as an authoritative extraction architecture. The exact grouped-routing approach lost correctness and did not produce stable runtime gains. |
| Retest boundary | Do not retest deterministic field grouping as the primary answer path. Retest only if planning is advisory, retrieval-only, or used as non-authoritative metadata, and compare on the full three-benchmark suite. |

### Paper-Batch

| Field | Details |
| --- | --- |
| Status | Rejected as a default extraction architecture; superseded by narrower batch-then-verify ideas. |
| Tested idea | Use larger paper-level or row-level batch extraction with structured calls and per-cell fallback. |
| What was tested | Branch `experiment-paper-batch` at commit `361f4f4`; full run `manual_paper_batch_3bench_3rep`; model `google/gemma-4-e4b`. |
| Why tested | Reduce repeated retrieval and completion overhead by extracting many cells from a paper in one batch. |
| Evidence | Full-benchmark row in [Full-Benchmark Idea Evaluations](#full-benchmark-idea-evaluations). |
| Scope and models | Genome editing, MPRA, and spatial transcriptomics; three replicates; `google/gemma-4-e4b`. |
| Result | Score 0.5681, runtime 88.81 min, and 113 completion calls. It was lower scoring and slightly slower than the per-cell baseline despite fewer calls. |
| Decision | Do not use paper-batch extraction as the default architecture. The approach lost too much cell-specific precision and did not deliver the expected runtime improvement. |
| Retest boundary | Do not retest whole-paper batch extraction as the primary answer source. A future test should be a materially different [Batch-Then-Verify Hybrid](improvement-ideas.md#batch-then-verify-hybrid), where batch output is only a candidate generator and per-cell verification remains authoritative. |

### LLM-Primary Column Planning

| Field | Details |
| --- | --- |
| Status | Superseded as an authoritative planning strategy. |
| Tested idea | Let an LLM planner choose or validate extraction strategy before cell-level extraction. |
| What was tested | Partial planner/evidence-card wiring in `dev_check_20260518-230132`, LLM planner field-group run `dev_check_20260518-234927`, and stricter planner validation in `dev_check_20260519-000015`; model `google/gemma-4-e4b`. |
| Why tested | Improve evidence targeting and reduce wasted extraction by planning column strategy before proposal generation. |
| Evidence | Dev-check table rows in this file. |
| Scope and models | Genome editing dev-check scope; `google/gemma-4-e4b`; compared against per-cell baseline dev-check `dev_check_20260518-195533`. |
| Result | Scores were 0.56, 0.56, and 0.50, with runtimes 11.45 min, 9.21 min, and 10.10 min. Baseline scored 0.62 at 9.28 min. Stricter validation lowered score, suggesting planner errors and over-aggressive filtering removed useful evidence or answers. |
| Decision | Do not use LLM planning as an authoritative gate or route selector. |
| Retest boundary | Do not retest LLM-primary planning unless it is redesigned as advisory metadata, such as [Advisory Schema Planning](improvement-ideas.md#advisory-schema-planning), and cannot block per-cell extraction or discard candidates by itself. |

### Conservative Batch Gate

| Field | Details |
| --- | --- |
| Status | Rejected. |
| Tested idea | Add a conservative gate around batch-style extraction so only apparently safe grouped answers are accepted. |
| What was tested | Dev-check `dev_check_20260519-001805`; model `google/gemma-4-e4b`. |
| Why tested | Preserve the runtime benefits of grouping while preventing lower-confidence batch answers from replacing per-cell answers. |
| Evidence | Dev-check row in [Dev-Check Runs](#dev-check-runs). |
| Scope and models | Genome editing dev-check; `google/gemma-4-e4b`; compared with baseline and field-group deterministic dev-checks. |
| Result | Score 0.54 and runtime 11.86 min. It was worse than the per-cell baseline dev-check at 0.62 and 9.28 min, and worse than the faster field-group deterministic dev-check at 0.58 and 5.59 min. |
| Decision | Do not continue this specific gating design. It added cost without protecting correctness. |
| Retest boundary | Do not retest this gate unchanged. A future verifier must define explicit acceptance metrics, preserve per-cell fallback as authoritative, and pass a dev-check before any full benchmark. |

## Appendix: Historical Branches

These branches are kept as historical references for tested ideas. Each branch must link to the idea entry that explains what was tested and why it was kept, rejected, or superseded.

| Branch | Commit | Idea entry | What it represents |
| --- | --- | --- | --- |
| `main` | `6efabd7` | [Per-Cell Baseline Architecture](#per-cell-baseline-architecture) | Baseline before grouped and batched extraction experiments. |
| `experiment-field-group-deterministic` | `ce960c2` | [Field-Group Deterministic](#field-group-deterministic) | Deterministic column grouping with per-cell fallback. |
| `experiment-paper-batch` | `361f4f4` | [Paper-Batch](#paper-batch) | Paper/row batch extraction without deterministic planning, with grouped structured calls and per-cell fallback. |
