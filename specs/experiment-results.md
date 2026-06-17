# Experiment Results

This file is the durable evidence and decision record for tested app-improvement ideas. It should make clear what was tried, how it was evaluated, what decision followed, and what should or should not be retested.

## Outline

- [Purpose And Rules](#purpose-and-rules)
- [Decision Entry Format](#decision-entry-format)
- [Dev-Check Runs](#dev-check-runs)
- [Full-Benchmark Idea Evaluations](#full-benchmark-idea-evaluations)
- [Model-Comparison Decisions](#model-comparison-decisions)
- [Kept Or Partially Kept Ideas](#kept-or-partially-kept-ideas)
- [Rejected Or Superseded Ideas](#rejected-or-superseded-ideas)
- [Appendix: Historical Branches](#appendix-historical-branches)

## Purpose And Rules

This file owns tested evidence and decisions for app, harness, architecture, procedure, retrieval, prompt, eval, optimizer, and workflow improvement ideas. `improvement-ideas.md` owns prioritized ideas that are untested, partly tested, or still worth testing.

- Record ideas and decisions, not long chronological run narratives.
- Add a decision entry once an idea has been benchmarked, dev-checked, rejected, superseded, kept, or partly kept.
- Use the run tables for comparability, then keep detailed implementation constraints and interpretation in the linked decision entry.
- A dev-check run is the default first evaluation for an implemented idea.
- The dev-check table is a compact comparison table: `Model` is only the model id, `Benchmark Dataset` is only the dataset name, and `Runtime Total` is only total runtime.
- The dev-check table should end with a current-main comparison row. If the current-main reference cannot be scored, keep an explicit unscored row with the readiness reason rather than hiding the gap.
- The full-benchmark table is only for default-model app-idea evaluations over the three benchmark datasets in triplicate. Model-comparison studies do not belong in that table.
- The full-benchmark table should end with a current-main comparison row. If no current-main full-benchmark exists, keep an explicit missing-reference row until one is run.
- Model-comparison runs can inform ideas and default-model reports, but model choice alone is not an app-improvement idea for this ledger.
- If an idea is rejected, remove the rejected implementation from `improvement-ideas.md` and add a clear retest boundary here.
- If a broader idea remains worth testing after a rejected implementation, keep or reprioritize it in `improvement-ideas.md` with a concise `Evidence so far` line.

Normal decision entries should be 120-250 words. Larger multi-benchmark decisions may be 300-600 words, but must start with the conclusion in the `Decision` or `Result` row. Run table rows stay one line each.

## Decision Entry Format

Use one table per rejected or superseded idea. Kept ideas are summarized in the compact kept table unless they need a longer rationale.

| Field | Required content |
| --- | --- |
| Status | `Kept`, `Partially kept`, `Rejected`, or `Superseded`. |
| Tested idea | Short name of the idea or implementation strategy. |
| What was tested | Branch, commit, config, mode, candidate ids when needed, model ids, and important implementation constraints. |
| Why tested | The hypothesis or expected benefit. |
| Evidence | Links or IDs for dev-check runs, full-benchmark runs, proposal/log analyses, and focused tests. |
| Scope and models | Benchmark datasets, replicate count, model IDs, and comparison baseline. |
| Result | Score, runtime, call count when available, key diagnostics, and whether the expected benefit appeared. |
| Decision | What to keep, reject, supersede, or carry forward. |
| Retest boundary | Conditions under which this exact idea should or should not be tried again. |

## Dev-Check Runs

| Date | Run | Idea entry | Model | Benchmark Dataset | Score | Runtime Total | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-18 | `dev_check_20260518-192047` | [Per-Cell Baseline Architecture](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.56 | 9.46 min | Superseded by the later baseline dev-check after figure-review state/hit fixes. |
| 2026-05-18 | `dev_check_20260518-195533` | [Per-Cell Baseline Architecture](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.62 | 9.28 min | Best prior baseline dev-check, main `6efabd7`. |
| 2026-05-18 | `dev_check_20260518-230132` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.56 | 11.45 min | Partial planner/evidence-card wiring; not a recommended endpoint. |
| 2026-05-18 | `dev_check_20260518-234727` | [Field-Group Deterministic](#field-group-deterministic) | `google/gemma-4-e4b` | Genome editing | n/a | 1.02 min | Failed before scoring due grouped proposal diagnostics bug. |
| 2026-05-18 | `dev_check_20260518-234927` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.56 | 9.21 min | Valid contract, but no score improvement. |
| 2026-05-19 | `dev_check_20260519-000015` | [LLM-Primary Column Planning](#llm-primary-column-planning) | `google/gemma-4-e4b` | Genome editing | 0.50 | 10.10 min | Planning and validation were too aggressive. |
| 2026-05-19 | `dev_check_20260519-001119` | [Field-Group Deterministic](#field-group-deterministic) | `google/gemma-4-e4b` | Genome editing | 0.58 | 5.59 min | Fast single dev-check, but the speed benefit did not generalize. |
| 2026-05-19 | `dev_check_20260519-001805` | [Conservative Batch Gate](#conservative-batch-gate) | `google/gemma-4-e4b` | Genome editing | 0.54 | 11.86 min | Worse score and runtime; rejected. |
| 2026-06-02 | `dev_check_20260602_structured_diagnostics / run_20260601_223720_dh6afy` | [Per-Cell Baseline Architecture](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | MPRA | 0.50 | 15.51 min | Current-code structured-diagnostics datapoint; not directly comparable to genome-editing dev-checks. |
| 2026-06-03 | `dev_check_20260603-115610 / run_20260603_095630_79vtoe` | [Schema-Semantic Candidate Selection Guardrails](#schema-semantic-candidate-selection-guardrails) | `google/gemma-4-e4b` | Genome editing | 0.40 | 8.69 min | Worse than prior genome-editing baselines; rejected. |
| 2026-06-03 | `dev_check_20260603-122747` | [Schema-Semantic Candidate Selection Guardrails](#schema-semantic-candidate-selection-guardrails) | `google/gemma-4-e4b` | Genome editing | 0.46 | 11.80 min | Narrower selector-only guardrail improved over v1 but still underperformed and added reliability cost; rejected. |
| 2026-06-03 | `retrieval_score_shape_gating_20260603 / run_20260603_104949_pmw6sy` | [Retrieval Score-Shape Prompt Gating](#retrieval-score-shape-prompt-gating) | `google/gemma-4-e4b` | Genome editing | 0.56 | 9.71 min | Conservative gate applied to 0 proposals with text-prompt diagnostics; no-op/inconclusive. |
| 2026-06-03 | `retrieval_score_shape_gating_v2_20260603 / run_20260603_134126_pufw3u` | [Retrieval Score-Shape Prompt Gating](#retrieval-score-shape-prompt-gating) | `google/gemma-4-e4b` | Genome editing | 0.52 | 10.35 min | V2 gated 20 proposals but lowered score and added structured-output errors; rejected. |
| 2026-06-03 | `main_reference_retry_20260603 / run_20260603_195702_otoed8` | Current main reference | `google/gemma-4-e4b` | Genome editing | unscored | 0.20 min | Current-main comparison attempted on `main` commit `3f0b2bf`; LM Studio listed the model but failed to load it through app readiness, raw `/v1/chat/completions`, raw `/api/v1/models/load`, and `lms load`; `nvidia/nemotron-3-nano-4b` loaded successfully, so this is a model-specific LM Studio load failure rather than an app score. |
| 2026-06-16 | `exp_a1_evidence_index_branchpy_20260617 / run_20260616_223105_7my7n6` | [Persistent Evidence Index](#kept-or-partially-kept-ideas) | `google/gemma-4-12b` | Genome editing | 0.54 | 13.01 min | Prepared retrieval index artifacts proved viable; infrastructure value, no standalone score lift. |
| 2026-06-16 | `exp_a2_typed_retrieval_context_20260617 / run_20260616_225354_i8d16k` | [Typed Retrieval Context (A2)](#typed-retrieval-context-a2) | `google/gemma-4-12b` | Genome editing | 0.50 | 19.29 min | Typed retrieval/prompt markers lowered score and increased runtime; rejected as tested. |
| 2026-06-16 | `exp_c1_uncertainty_recovery_20260617 / run_20260616_235459_xvhsrp` | [Recall Rescue With Current Retrieval (C1)](#recall-rescue-with-current-retrieval-c1) | `google/gemma-4-12b` | Genome editing | 0.50 | 22.69 min | Broad current-retrieval rescue used 33/33 eligible cells but lowered score and reliability; rejected as tested. |
| 2026-06-17 | `exp_d2_vision_gate_diagnostics_20260617 / run_20260617_063031_f0p0j2` | [Targeted Vision Gate Diagnostics](#kept-or-partially-kept-ideas) | `google/gemma-4-12b` | Genome editing | 0.50 | 21.84 min | Diagnostic rollups are useful; score/runtime do not justify a default behavior change. |
| 2026-06-16 | `main_gemma4_12b_baseline_20260616 / run_20260616_214652_a2cozj` | Current main reference | `google/gemma-4-12b` | Genome editing | 0.56 | 14.07 min | Current-main comparison baseline at `main` commit `0b96027`; use as the matched 12B reference for this loop, with judge-instability caveat. |

## Full-Benchmark Idea Evaluations

This table contains only default-model app-idea evaluations over genome editing, MPRA, and spatial transcriptomics in triplicate. Model-comparison studies are intentionally excluded.

| Date | Run folder | Idea entry | Model | Benchmark Datasets | Replicates | Score | Runtime Total | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05 | `manual_baseline_per_cell_3bench_3rep_retry` | [Per-Cell Baseline Architecture](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics | 3 | 0.6517 | 86.22 min | Kept as the historical full-benchmark comparison baseline. |
| 2026-05 | `manual_field_group_deterministic_3bench_3rep` | [Field-Group Deterministic](#field-group-deterministic) | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics | 3 | 0.6040 | 87.57 min | Rejected as default architecture. |
| 2026-05 | `manual_paper_batch_3bench_3rep` | [Paper-Batch](#paper-batch) | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics | 3 | 0.5681 | 88.81 min | Rejected as default architecture. |
| 2026-06-02 | `tools/optimizer/runs/20260602_compare_models_direct` | Current main reference | `google/gemma-4-e4b` | Genome editing, MPRA, spatial transcriptomics | 3 | 0.5718 | 134.35 min | Current-main default-model row from the latest compare-model run; full suite coverage, scored, with judge-instability caveat. |

## Model-Comparison Decisions

This section records model-comparison conclusions that affect future experiment defaults. These runs are not app-improvement ideas, so they remain outside the full-benchmark idea table.

### 2026-06-15 Compare Models Default

| Field | Details |
| --- | --- |
| Status | Partially kept as a default-model and comparison-set decision. |
| Tested idea | Broad local model comparison for the current per-cell pipeline. |
| What was tested | `tools/optimizer/runs/20260615_004637_compare_models`, stage `compare_models`, over the dev suite with figure review enabled, recall rescue disabled, retrieval `hybrid_experimental`, top-k 12, and parser fallback allowed. The run compared 11 local candidates plus external gold and external agent-style baselines. |
| Why tested | Determine whether near-term gains should come from a better local default model or from workflow, prompt, retrieval, evidence handling, recovery, and figure/table handling. |
| Evidence | Run artifacts under `tools/optimizer/runs/20260615_004637_compare_models/compare/experiment/`, especially `summary.json`, `candidate_diagnostics.json`, `results/results.csv`, `results/candidate_diagnostics.csv`, and `report.html`. |
| Scope and models | Three benchmark datasets in the dev suite. Best local score: `google/gemma-4-12b-qat` at 0.6784 in 2.93 h. Practical default: `google/gemma-4-12b` at 0.6467 in 1.87 h. Best non-Gemma quality reference: `qwen/qwen3.6-27b` at 0.6562 in 3.25 h. |
| Result | QAT won locally but was much slower than regular Gemma 12B for a modest score gain. `qwen3.6-27b-mtp` scored lower than regular Qwen with only modest runtime improvement. `nuextract3` scored but was not competitive. External agent-style baselines remained substantially higher at 0.8019-0.8259. |
| Decision | Use `google/gemma-4-12b` as the default model for upcoming local improvement experiments. Keep `qwen/qwen3.6-27b` as the non-Gemma quality reference and `google/gemma-4-12b-qat` only as an occasional slow ceiling, not the default. Drop weaker or slower variants from routine comparison unless a future change specifically targets their failure mode. |
| Retest boundary | Do not run another broad model sweep until the extraction workflow changes materially or a new local model is expected to change the quality/runtime frontier. Near-term experiments should test retrieval, context, recovery, figure/table handling, and evidence behavior with regular Gemma 12B. |

### 2026-06-15 Compare Models Diagnostics Note

The constant internal `join_failure_count=16` in the report is an eval/reporting diagnostic artifact, not a PDF or row-matching failure. The current eval schema excludes default metadata columns through `DEFAULT_EXCLUDED_SCORE_COLUMNS`, but proposal diagnostics for unmatched proposal keys still include metadata proposals and `aggregate.py` counts `unmatched_proposal` records as join problems. In inspected `cand_0002` scored-cell rollups, all unmatched proposal rows were default-excluded metadata fields: `Title`, `Authors`, `Publication Year`, `Journal`, and `DOI` where the benchmark template included DOI. Content cells were matched, and the run diagnostics reported `matched_pdf_count=5`.

The targeted future fix is to split excluded-column proposal diagnostics from true join failures. For example, eval can emit an `excluded_proposal` status or `proposal_for_excluded_column` diagnostic for proposals whose columns are intentionally not scored, keep those counts visible separately, and exclude them from `join_failure_count`. Tests should prove that proposals for excluded metadata columns do not increment `join_failure_count`, while true extra non-excluded proposal columns still do.

Figure-review counters show that the dominant issue is not simply "use more vision." The current behavior is mostly planner gating and acceptance behavior: regular Gemma 12B had 34 triggers, 34 planner skips, and 0 vision calls; QAT had 38 triggers, 28 skips, 13 calls, 12 no-hit outcomes, and 1 figure-derived evidence item; regular Qwen had 31 triggers, 27 skips, 6 calls, 3 failed attempts, and 2 figure-derived evidence items. Figure evidence currently mostly rescues empty or weak proposals and is not a broad override path for non-empty text answers. This supports a targeted vision/planner audit rather than broader uncapped vision use.

## Kept Or Partially Kept Ideas

| Date | Commit | Idea | Details |
| --- | --- | --- | --- |
| 2026-05 | `6efabd7` | Per-Cell Baseline Architecture | Kept as the historical comparison baseline after `manual_baseline_per_cell_3bench_3rep_retry` scored 0.6517 over the three benchmark datasets in triplicate with `google/gemma-4-e4b`. Retest current main when architecture, retrieval, prompt, model default, or scoring defaults change materially. |
| 2026-06 | `baf66cd` | Persistent Evidence Index (A1) | Partially kept as enabling infrastructure branch `exp-20260616-a1-evidence-index`, not as a standalone quality lift. The corrected branch-PYTHONPATH dev-check scored 0.54 versus the matched current-main 12B baseline at 0.56, but created five persistent `_indexes` artifacts and showed index source counts `built=5`, `memory=70` with no repeated retrieval work. Continue only as substrate for later index-backed retrieval or recovery tests. |
| 2026-06 | `2215246` | Targeted Vision Gate Diagnostics (D2) | Partially kept as diagnostic instrumentation branch `exp-20260616-d2-vision-gate-diagnostics`, not as a default extraction change. The dev-check scored 0.50 versus the matched current-main 12B baseline at 0.56, but the new rollups exposed the decision funnel: 20 triggered cells, 5 reviewed cells, 1 accepted figure hit, 4 missing-value/no-hit outcomes, 15 planner skips, and 1 structured vision failure. Use this branch to guide future vision acceptance tests. |

## Rejected Or Superseded Ideas

### Typed Retrieval Context (A2)

| Field | Details |
| --- | --- |
| Status | Rejected as a default retrieval prompt-context implementation. |
| Tested idea | Bundle A2: prepend typed page, element, section, caption, table, and figure metadata to retrieval text and extraction prompt passage headers while preserving reviewer-facing display text. |
| What was tested | Branch `exp-20260616-a2-typed-retrieval-context`, commit `6a1348b`; retrieval text gained typed markers and extraction prompts surfaced section/figure/table metadata. |
| Why tested | The hypothesis was that lightweight typed context would help `google/gemma-4-12b` distinguish captions, figures, tables, and sections without changing source evidence artifacts. |
| Evidence | Focused tests passed: `TestRetrievalChunks` plus prompt-context coverage (`25 passed`) and `python scripts/check_specs.py`. Dev-check `exp_a2_typed_retrieval_context_20260617 / run_20260616_225354_i8d16k` completed and scored. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-12b`; default prompt bundle; retrieval `hybrid_experimental`, top-k 12; recall rescue and whole-document mode disabled. |
| Result | Score was 0.50 versus matched current-main 12B baseline 0.56. Runtime rose to 19.29 min versus 14.07 min. The run had 16 structured errors, 14 provider retries, 8 structured-output repairs, 75 retrieval calls, no repeated retrieval work, 35 recall-rescue eligible/skipped cells, and only 1 useful figure-derived evidence item. |
| Decision | Do not merge this exact typed-marker prompt expansion as default behavior. The broader retrieval-quality idea remains open, but this implementation appears to add prompt/runtime cost without improving answer selection. |
| Retest boundary | Retest only with a materially different, measured answerability strategy such as table-aware units, evidence-aware reranking, or shorter typed hints with token/runtime diagnostics and a matched current-main dev-check. |

### Recall Rescue With Current Retrieval (C1)

| Field | Details |
| --- | --- |
| Status | Rejected as a default recovery strategy. |
| Tested idea | Bundle C1: enable uncertainty-gated recall rescue against current retrieval, without whole-document mode, through a run-local dev-check override. |
| What was tested | Branch `exp-20260616-c1-uncertainty-recovery`, commit `aa64a77`; added `optimizer dev-check --recall-rescue` and materialized only the run-local candidate config with `recall_rescue_enabled=true`, `whole_document_mode=false`. |
| Why tested | The 2026-06-15 model comparison showed many recall-rescue-eligible cells but rescue disabled, making current-retrieval rescue a low-scope lever to test. |
| Evidence | Focused CLI/config tests passed (`3 passed`) and `python scripts/check_specs.py` passed. Dev-check `exp_c1_uncertainty_recovery_20260617 / run_20260616_235459_xvhsrp` completed and scored. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-12b`; default prompt bundle; retrieval `hybrid_experimental`, top-k 12; recall rescue enabled; whole-document mode disabled. |
| Result | Score was 0.50 versus matched current-main 12B baseline 0.56. Runtime rose to 22.69 min versus 14.07 min. Rescue ran on 33/33 eligible cells, but provider retries rose to 23 in the summary, structured errors to 27, text structured completions to 152, and candidate selection to 17 attempts with 9 value changes. |
| Decision | Do not use broad current-retrieval recall rescue as default. The tested gate spends substantial runtime and reliability budget without net quality gain. |
| Retest boundary | Future recovery should be narrower: require schema-specific absent-feature handling, stronger evidence candidates, persistent-index or candidate-census inputs, and recovered-correct versus recovered-wrong accounting before another model-heavy run. |

### Retrieval Score-Shape Prompt Gating

| Field | Details |
| --- | --- |
| Status | Rejected as a default prompt-context gating strategy. |
| Tested idea | Persist per-chunk retrieval scores, derive a smaller prompt-only context view from score shape, suppress zero-score context, keep dominant lead chunks with neighbors, and trim low-score tails while preserving full retrieval artifacts. |
| What was tested | Branch `codex/retrieval-score-shape-gating`, commit `0142947`, added selected-score rows, score-shape summaries, prompt-context gating diagnostics, focused tests, and `specs/spec.md` guidance. Follow-up branch `codex/retrieval-score-shape-gating-v2`, commit `9f5838e`, widened the gating threshold so the policy actually applied on the observed hybrid score distribution. |
| Why tested | The hypothesis was that extraction prompts were diluted by topical but non-answering chunks, so score-shape-aware prompt trimming might improve answer selection without changing reviewer-visible evidence or adding model calls. |
| Evidence | Focused backend tests passed for retrieval score persistence, prompt-tail trimming without mutating retrieval artifacts, and zero-score context suppression. `python scripts/check_specs.py` passed. Optimizer dev-checks `retrieval_score_shape_gating_20260603 / run_20260603_104949_pmw6sy` and `retrieval_score_shape_gating_v2_20260603 / run_20260603_134126_pufw3u` completed and scored. |
| Scope and models | Genome editing dev-check; one replicate per branch; `google/gemma-4-e4b`; default prompt bundle; retrieval `hybrid_experimental`, top-k 12; recall rescue and whole-document mode disabled. |
| Result | V1 scored 0.56 in 9.71 min, but applied 0 prompt gates among 52 proposals with text-prompt diagnostics, so it was effectively a no-op. V2 scored 0.52 in 10.35 min after applying prompt-context gating to 20 proposals. It increased anchor-invalid evidence to 5, missing evidence to 5, and provider structured-output retries/errors to 3 with 18.68 sec failed structured elapsed time. |
| Decision | Do not merge either branch as default behavior. Threshold-only score-shape prompt gating is not a reliable improvement: the conservative version did not exercise the idea, and the exercised version hurt score/reliability. Keep broader retrieval work focused on typed/table-aware context, semantic reranking, or targeted recovery rather than normalized lexical-score thresholds alone. |
| Retest boundary | Do not retest these exact threshold policies unchanged. A future retrieval gating test must first prove that removed chunks are non-answering by evidence diagnostics or a reranker, report gating-applied counts and prompt-token savings, and compare against a matched current-main dev-check or full three-benchmark run. |

### Schema-Semantic Candidate Selection Guardrails

| Field | Details |
| --- | --- |
| Status | Rejected as a default prompt/selector guardrail implementation. |
| Tested idea | Add schema-derived semantic checks to extraction and candidate-selection prompts, and require the selector to finalize only supplied candidate values. |
| What was tested | Branch `codex/candidate-selection-normalization`, commit `c6fc475`, with generic checks added to first-pass extraction and candidate-selection prompts plus a no-invention selector guard. Follow-up branch `codex/candidate-selection-normalization-v2`, commit `c9d59ba`, removed the first-pass prompt expansion and preserved the pre-selector proposal when selector output named a non-candidate value. |
| Why tested | The hypothesis was that hard-column failures often come from choosing a plausible but wrong value type rather than total evidence absence. |
| Evidence | Focused backend tests passed on both branches: selector choice/no-invention tests, prompt semantic-check tests, and `test_proposal_semantics.py` (27 tests total). `python scripts/check_specs.py` passed on both branches. Optimizer dev-checks `dev_check_20260603-115610 / run_20260603_095630_79vtoe` and `dev_check_20260603-122747` completed and scored. |
| Scope and models | Genome editing dev-check; one replicate per branch; `google/gemma-4-e4b`; default prompt bundle; retrieval `hybrid_experimental`, top-k 12; recall rescue and whole-document mode disabled. |
| Result | V1 scored 0.40 in 8.69 min, with 14 candidate-selection attempts and 8 value changes. V2 scored 0.46 in 11.80 min, with 16 candidate-selection attempts and 12 value changes. V2 recovered one DNA extraction/genotyping method cell and improved max editing efficiency and best/selected variant relative to v1, but it remained below prior genome-editing dev-check baselines such as 0.56 and 0.62. V2 also had 5 structured-output errors/retries and 42.57 sec failed structured elapsed time. |
| Decision | Do not merge either branch as a default behavior change. The tested prompt/selector guardrails lowered the dev-check signal or added runtime/reliability cost. The broader candidate-selection idea remains open only for a materially different, more evidence-grounded selector/normalizer. |
| Retest boundary | Do not retest either exact prompt block plus no-invention guard unchanged. A future candidate-selection test should isolate deterministic normalization or selector adjudication, report per-cell value changes, and include a matched current-main dev-check or full three-benchmark comparison. |

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
| `main` | `6efabd7` | [Per-Cell Baseline Architecture](#kept-or-partially-kept-ideas) | Historical baseline before grouped and batched extraction experiments. |
| `experiment-field-group-deterministic` | `ce960c2` | [Field-Group Deterministic](#field-group-deterministic) | Deterministic column grouping with per-cell fallback. |
| `experiment-paper-batch` | `361f4f4` | [Paper-Batch](#paper-batch) | Paper/row batch extraction without deterministic planning, with grouped structured calls and per-cell fallback. |
| `codex/candidate-selection-normalization` | `c6fc475` | [Schema-Semantic Candidate Selection Guardrails](#schema-semantic-candidate-selection-guardrails) | Prompt-heavy schema-semantic guardrail implementation. |
| `codex/candidate-selection-normalization-v2` | `c9d59ba` | [Schema-Semantic Candidate Selection Guardrails](#schema-semantic-candidate-selection-guardrails) | Narrower selector-only guardrail implementation. |
| `codex/retrieval-score-shape-gating` | `0142947` | [Retrieval Score-Shape Prompt Gating](#retrieval-score-shape-prompt-gating) | Conservative score-shape prompt gating that did not apply on the dev-check. |
| `codex/retrieval-score-shape-gating-v2` | `9f5838e` | [Retrieval Score-Shape Prompt Gating](#retrieval-score-shape-prompt-gating) | Wider score-shape prompt gating that applied but reduced score. |
| `exp-20260616-a1-evidence-index` | `baf66cd` | [Persistent Evidence Index](#kept-or-partially-kept-ideas) | Prepared retrieval index artifacts and retrieval-equivalence diagnostics. |
| `exp-20260616-a2-typed-retrieval-context` | `6a1348b` | [Typed Retrieval Context (A2)](#typed-retrieval-context-a2) | Typed retrieval text and prompt passage metadata experiment. |
| `exp-20260616-c1-uncertainty-recovery` | `aa64a77` | [Recall Rescue With Current Retrieval (C1)](#recall-rescue-with-current-retrieval-c1) | Dev-check recall-rescue override for current retrieval. |
| `exp-20260616-d2-vision-gate-diagnostics` | `2215246` | [Targeted Vision Gate Diagnostics](#kept-or-partially-kept-ideas) | Figure-review planner, no-hit, dropped-result, and accepted-hit diagnostics. |
