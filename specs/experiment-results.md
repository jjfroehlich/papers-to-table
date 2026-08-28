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
| 2026-06-16 | `exp_a1_evidence_index_branchpy_20260617 / run_20260616_223105_7my7n6` | [Persistent Evidence Index](#kept-or-partially-kept-ideas) | `google/gemma-4-12b` | Genome editing | 0.54 | 13.01 min | 12B sensitivity run; prepared retrieval index artifacts proved viable, but this is no longer the primary comparison model. |
| 2026-06-16 | `exp_a2_typed_retrieval_context_20260617 / run_20260616_225354_i8d16k` | [Typed Retrieval Context (A2)](#kept-or-partially-kept-ideas) | `google/gemma-4-12b` | Genome editing | 0.50 | 19.29 min | 12B sensitivity run regressed; superseded by the matched e4b run for current development decisions. |
| 2026-06-16 | `exp_c1_uncertainty_recovery_20260617 / run_20260616_235459_xvhsrp` | [Recall Rescue With Current Retrieval (C1)](#recall-rescue-with-current-retrieval-c1) | `google/gemma-4-12b` | Genome editing | 0.50 | 22.69 min | 12B sensitivity run; broad current-retrieval rescue remained worse than its matched baseline. |
| 2026-06-17 | `exp_d2_vision_gate_diagnostics_20260617 / run_20260617_063031_f0p0j2` | [Targeted Vision Gate Diagnostics](#kept-or-partially-kept-ideas) | `google/gemma-4-12b` | Genome editing | 0.50 | 21.84 min | 12B sensitivity run; diagnostic value remains, but e4b is the primary development comparison. |
| 2026-06-16 | `main_gemma4_12b_baseline_20260616 / run_20260616_214652_a2cozj` | Current main reference | `google/gemma-4-12b` | Genome editing | 0.56 | 14.07 min | 12B reference at `main` commit `0b96027`; preserved as model-sensitivity evidence, not the current development default. |
| 2026-06-17 | `exp_a1_evidence_index_e4b_20260617 / run_20260617_073346_rd1q20` | [Persistent Evidence Index](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.54 | 12.98 min | Primary e4b comparison: partially kept as infrastructure; five prepared index artifacts, no repeated retrieval work. |
| 2026-06-17 | `exp_a2_typed_retrieval_context_e4b_20260617 / run_20260617_074742_ggdsv5` | [Typed Retrieval Context (A2)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.60 | 13.36 min | Primary e4b comparison: promising single-replicate gain over current main; needs replication/full benchmark. |
| 2026-06-17 | `exp_c1_uncertainty_recovery_e4b_20260617 / run_20260617_080207_gcpqb9` | [Recall Rescue With Current Retrieval (C1)](#recall-rescue-with-current-retrieval-c1) | `google/gemma-4-e4b` | Genome editing | 0.46 | 16.12 min | Primary e4b comparison: broad current-retrieval rescue used 48/48 eligible cells and regressed; rejected as tested. |
| 2026-06-17 | `exp_d2_vision_gate_diagnostics_e4b_20260617 / run_20260617_081904_53l6nq` | [Targeted Vision Gate Diagnostics](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.54 | 11.54 min | Primary e4b comparison: partially kept for diagnostics; score delta is not treated as causal. |
| 2026-06-17 | `main_gemma4_e4b_baseline_20260617 / run_20260617_072009_e6g1tc` | Current main reference | `google/gemma-4-e4b` | Genome editing | 0.50 | 12.62 min | Current-main development baseline after reverting default model truth to e4b. |
| 2026-06-17 | `exp_a3_table_units_e4b_20260617 / run_20260617_121742_7b5b5l` | [Table-Aware Retrieval Units (A3)](#table-aware-retrieval-units-a3) | `google/gemma-4-e4b` | Genome editing | 0.58 | 15.10 min | Neutral score with 129 added `table_unit` chunks and a large runtime increase; do not merge exact line-based implementation. |
| 2026-06-17 | `exp_a4_evidence_rerank_e4b_20260617_rerun / run_20260617_135352_wowqdc` | [Evidence-Aware Reranking (A4)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.58 | 13.08 min | Neutral score, evidence quality improved to 0.82; later ported as canonical support-layer retrieval ordering after A2b recheck. |
| 2026-06-17 | `exp_a2b_typed_scoring_e4b_20260617 / run_20260617_140741_s16g3m` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.62 | 14.00 min | Merged to main as canonical typed retrieval scoring after user decision; still single-replicate evidence. |
| 2026-06-17 | `exp_b1_schema_candidate_census_e4b_20260617 / run_20260617_142227_sx2a7g` | [Schema Candidate Census Prompt Injection (B1)](#schema-candidate-census-prompt-injection-b1) | `google/gemma-4-e4b` | Genome editing | 0.48 | 13.39 min | Regression; 75 census cells and 120 advisory candidates lowered score and evidence quality. |
| 2026-06-17 | `main_wave2_baseline_e4b_20260617 / run_20260617_114230_wd7zwd` | Current main reference | `google/gemma-4-e4b` | Genome editing | 0.58 | 9.98 min | Current-main wave-2 baseline after A1 infrastructure, safer A2 prompt-header orientation, D2 diagnostics, and e4b development default. |
| 2026-06-17 | `exp_c2_targeted_prepared_index_recovery_e4b_20260617_srcpath / run_20260617_183858_qkhe0d` | [Targeted Prepared-Index Recovery (C2)](#targeted-prepared-index-recovery-c2) | `google/gemma-4-e4b` | Genome editing | 0.54 | 20.15 min | Nominal score lift over the fresh baseline, but evidence quality collapsed to 0.00 and runtime/calls rose sharply; reject exact implementation. |
| 2026-06-17 | `exp_d3_vision_acceptance_gate_e4b_20260617_srcpath / run_20260617_185951_qux0ks` | [Vision Value Acceptance Gate (D3)](#vision-value-acceptance-gate-d3) | `google/gemma-4-e4b` | Genome editing | 0.60 | 14.54 min | Nominal score lift and gate diagnostics exercised, but evidence quality collapsed to 0.00; reject exact app behavior pending artifact analysis. |
| 2026-06-17 | `exp_e2_max_best_scope_prompt_e4b_20260617_srcpath / run_20260617_191458_tjool2` | [Scoped Max/Best Prompt Guidance (E2)](#scoped-maxbest-prompt-guidance-e2) | `google/gemma-4-e4b` | Genome editing | 0.52 | 13.93 min | Small score lift, but evidence quality fell to 0.16 versus 0.84 baseline; reject exact prompt change for now. |
| 2026-06-17 | `exp_f_excluded_join_diagnostics_e4b_20260617 / run_20260617_182008_hxoxzz` | [Excluded-Column Join Diagnostics (F)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.52 | 15.22 min | Eval-only measurement branch split 25 intentionally excluded metadata proposals from true join failures; later ported to current main. |
| 2026-06-17 | `main_next_batch_baseline_e4b_20260617 / run_20260617_163916_12thwa` | Current main reference | `google/gemma-4-e4b` | Genome editing | 0.48 | 11.78 min | Fresh current-main baseline at `da2ead2` before C2/D3/E2/F decisions; evidence quality 0.84, join failures 25, all from metadata proposal diagnostics before the F split. |
| 2026-06-17 | `main_a2b_canonical_e4b_recheck_20260617_r1 / run_20260617_200445_gxlbfm` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.54 | 14.15 min | A2b regression check on current main; evidence quality 0.80 and balanced per-cell flips versus pre-A2b control. |
| 2026-06-17 | `main_a2b_canonical_e4b_recheck_20260617_r2 / run_20260617_201942_s3ndfw` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.50 | 11.96 min | Second A2b regression check on current main; evidence quality 0.88 and no consistent >0.05 drop versus pre-A2b control. |
| 2026-06-17 | `pre_a2b_control_e4b_recheck_20260617_r1 / run_20260617_203415_simq5r` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.56 | 16.00 min | Detached pre-A2b control at `5dc2b63`; evidence-quality comparison invalid because persisted-text checks reported `no_persisted_text_available`. |
| 2026-06-17 | `pre_a2b_control_e4b_recheck_20260617_r2 / run_20260617_205106_o3xhdg` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.52 | 12.60 min | Second detached pre-A2b control at `5dc2b63`; score gap stayed within noise band and evidence-quality checks were artifact-invalid. |
| 2026-06-17 | `main_a4_canonical_rerank_e4b_20260617 / run_20260617_211549_pr23bo` | [Evidence-Aware Reranking (A4)](#kept-or-partially-kept-ideas) | `google/gemma-4-e4b` | Genome editing | 0.56 | 10.16 min | Post-port main run with A4 canonical reranking and F eval split active; evidence quality 0.82, `rerank_changed_count=201`, `excluded_proposal_count=25`, and true join failures 0. |

The initial C2, D3, and E2 dev-checks without branch `app/backend/src` on `PYTHONPATH` are superseded by the `*_srcpath` rows above; those earlier runs did not prove branch backend code was imported by the main-app subprocess. The F branch is eval-only and its non-srcpath run is valid because eval executes from the branch `tools/eval` path.

The suspicious `main_next_batch_baseline_e4b_20260617` score of 0.48 is not treated as proof that A2b regressed current main. Two current-main A2b rechecks scored 0.54 and 0.50, while two detached pre-A2b controls scored 0.56 and 0.52. Per-cell flips were balanced: r1 had 41 unchanged cells, 4 current-main wins, and 5 pre-A2b wins; r2 had 39 unchanged cells, 5 current-main wins, and 6 pre-A2b wins. The pre-A2b evidence-quality values are not comparable because detached-control eval artifacts lacked persisted text for evidence validation, which also explains why C2/D3/E2 branch evidence-quality rows should be interpreted as guardrail failures pending artifact-path analysis rather than quote-content proof.

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
| Scope and models | Three benchmark datasets in the dev suite. Best local score: `google/gemma-4-12b-qat` at 0.6784 in 2.93 h. Best practical 12B candidate: `google/gemma-4-12b` at 0.6467 in 1.87 h. Best non-Gemma quality reference: `qwen/qwen3.6-27b` at 0.6562 in 3.25 h. |
| Runtime weights | Main GGUF weights were `Q4_K_M` for Gemma E4B, Gemma 12B, Gemma 26B A4B, Nemotron 3 Nano Omni, NuExtract3, Ministral 3 14B Reasoning, GLM 4.6V Flash, and Qwen 3.6 27B; `MXFP4` for GPT-OSS 20B; `Q4_0` for Gemma 12B QAT; and `Q4_K_S` for Qwen 3.6 27B MTP. The exact filenames are documented in `docs/tools/optimizer.md`. |
| Result | QAT won locally but was much slower than regular Gemma 12B for a modest score gain. `qwen3.6-27b-mtp` scored lower than regular Qwen with only modest runtime improvement. `nuextract3` scored but was not competitive. External agent-style baselines remained substantially higher at 0.8019-0.8259. |
| Decision | Use `google/gemma-4-12b` as a quality/runtime reference from this model sweep, but the 2026-06-17 development-default reversion below supersedes it for near-term improvement experiments that need comparability with earlier e4b work. Keep `qwen/qwen3.6-27b` as the non-Gemma quality reference and `google/gemma-4-12b-qat` only as an occasional slow ceiling, not the default. |
| Retest boundary | Do not run another broad model sweep until the extraction workflow changes materially or a new local model is expected to change the quality/runtime frontier. Near-term experiments should test retrieval, context, recovery, figure/table handling, and evidence behavior with e4b unless the explicit goal is model sensitivity. |

### 2026-07-10 Negative-Control Calibration

| Field | Details |
| --- | --- |
| Status | Kept as calibration evidence for interpreting canonical model comparisons. |
| Tested idea | Score the deterministic gold-derived word-shuffle and cross-field negative controls through the same dual-judge Eval path as model and external-result candidates. |
| What was tested | The existing `tools/optimizer/runs/20260615_004637_compare_models` experiment was resumed in place for only `ext_gold_word_shuffle` and `ext_gold_cross_field`; its 15 existing candidates and 135 replicate payloads were reused unchanged. |
| Evidence | Evaluation completed 2026-07-10. See `compare/experiment/results/results.csv`, `compare/experiment/results/benchmark_summary.csv`, `compare/experiment/report.html`, and run-root `negative_control_augmentation.json` under the run path above. |
| Scope and judges | Three benchmark datasets with three independently generated control replicates each: 9 scored replicates per control and 18 total. Eval used `google/gemma-4-26b-a4b` and `openai/gpt-oss-20b`; all 18 summaries report completed dual judging, with no failed or degraded replicate. |
| Result | Positive gold remained 1.0000. Word shuffle scored 0.5589 overall: MPRA 0.7500, genome editing 0.4067, and spatial transcriptomics 0.5200. Cross-field scored 0.0000 overall and on every benchmark. Mean replicate judge-disagreement rate was 7.61% for word shuffle and 0.00% for cross-field; mean absolute judge-correctness gaps were 5.41 and 0.59 percentage points. Eval also recorded explicit judge-request failures (word shuffle: 221 judge A, 29 judge B, 29 unscored text cells; cross-field: 301 judge A, 1 judge B, 1 unscored text cell), so the word-shuffle baseline remains judge-instability-caveated despite every replicate being scored. |
| Decision | The expected ordering—positive gold above word shuffle above cross-field—was observed, so both negatives are useful report baselines. Keep them visible in comparison reports and replicate plots but excluded from winner and recommendation logic. Interpret the weak control by benchmark and with its judge caveat rather than as one universal chance score. |
| Retest boundary | Re-score the controls when judge models, judge prompting, structured-output handling, or headline correctness semantics change materially; otherwise reuse this calibration with the augmented run. |

### 2026-06-17 Development Default Reversion

| Field | Details |
| --- | --- |
| Status | Supersedes the near-term default-model part of the 2026-06-15 comparison decision. |
| Tested idea | Re-evaluate the first improvement-loop branches with the former `google/gemma-4-e4b` model so results remain comparable with earlier experiments. |
| What was tested | Current main plus A1/A2/C1/D2 branches were rerun on genome editing dev-check with explicit `--model google/gemma-4-e4b`. Main default config, wrapper default, docs, and specs were also reverted to e4b for development. |
| Why tested | The first loop used 12B after a default-model change, which made it hard to compare against the older e4b experiment ledger and changed A2's interpretation. |
| Evidence | Dev-check rows dated 2026-06-17 in this file: main `main_gemma4_e4b_baseline_20260617`, A1 `exp_a1_evidence_index_e4b_20260617`, A2 `exp_a2_typed_retrieval_context_e4b_20260617`, C1 `exp_c1_uncertainty_recovery_e4b_20260617`, and D2 `exp_d2_vision_gate_diagnostics_e4b_20260617`. |
| Scope and models | Genome editing dev-check; one replicate per branch; `google/gemma-4-e4b`; default prompt bundle; retrieval `hybrid_experimental`, top-k 12. C1 alone enabled recall rescue. |
| Result | Main scored 0.50 in 12.62 min. A1 scored 0.54 in 12.98 min. A2 scored 0.60 in 13.36 min. C1 scored 0.46 in 16.12 min. D2 scored 0.54 in 11.54 min. A2 is the only quality experiment with a clear positive single-replicate signal under the comparable model. |
| Decision | Keep `google/gemma-4-e4b` as the development default for now. Treat 12B rows as model-sensitivity evidence, not the primary basis for accepting or rejecting improvement ideas. |
| Retest boundary | Reconsider 12B as the default only after a matched full-benchmark or after the next improvement branch proves robust across both e4b and 12B. |

### 2026-06-15 Compare Models Diagnostics Note

The constant internal `join_failure_count=16` in the report is an eval/reporting diagnostic artifact, not a PDF or row-matching failure. The current eval schema excludes default metadata columns through `DEFAULT_EXCLUDED_SCORE_COLUMNS`, but proposal diagnostics for unmatched proposal keys still include metadata proposals and `aggregate.py` counts `unmatched_proposal` records as join problems. In inspected `cand_0002` scored-cell rollups, all unmatched proposal rows were default-excluded metadata fields: `Title`, `Authors`, `Publication Year`, `Journal`, and `DOI` where the benchmark template included DOI. Content cells were matched, and the run diagnostics reported `matched_pdf_count=5`.

The F excluded-column diagnostics branch tested this targeted fix. It emitted `excluded_proposal` diagnostics for intentionally unscored metadata proposals, preserved those counts separately, and kept true unmatched non-excluded proposals in the join-failure path. In the genome-editing dev-check, the previous 25 metadata `unmatched_proposal` records moved to `excluded_proposal_count=25`, while `join_failure_count` and true `unmatched_proposal_count` became 0.

Figure-review counters show that the dominant issue is not simply "use more vision." The current behavior is mostly planner gating and acceptance behavior: regular Gemma 12B had 34 triggers, 34 planner skips, and 0 vision calls; QAT had 38 triggers, 28 skips, 13 calls, 12 no-hit outcomes, and 1 figure-derived evidence item; regular Qwen had 31 triggers, 27 skips, 6 calls, 3 failed attempts, and 2 figure-derived evidence items. Figure evidence currently mostly rescues empty or weak proposals and is not a broad override path for non-empty text answers. This supports a targeted vision/planner audit rather than broader uncapped vision use.

## Kept Or Partially Kept Ideas

| Date | Commit | Idea | Details |
| --- | --- | --- | --- |
| 2026-05 | `6efabd7` | Per-Cell Baseline Architecture | Kept as the historical comparison baseline after `manual_baseline_per_cell_3bench_3rep_retry` scored 0.6517 over the three benchmark datasets in triplicate with `google/gemma-4-e4b`. Retest current main when architecture, retrieval, prompt, model default, or scoring defaults change materially. |
| 2026-06 | `baf66cd` | Persistent Evidence Index (A1) | Kept as enabling infrastructure, not as a standalone quality lift. The e4b dev-check scored 0.54 versus current-main e4b at 0.50, while the 12B sensitivity run scored 0.54 versus 0.56. Current main now persists guarded prepared indexes under `retrieval/_indexes/`, verifies document fingerprints before disk reuse, and reports `built`/`disk`/`memory` source counts. Continue with index-backed retrieval, recovery, table-aware units, or paper-census tests. |
| 2026-06 | `6a1348b` | Typed Retrieval Context (A2) | Partially kept as safer prompt orientation, not the exact branch implementation. The e4b dev-check scored 0.60 versus current-main e4b at 0.50, but the 12B sensitivity run regressed at 0.50 versus 0.56. Current main exposes section, table, and figure metadata in extraction prompt passage headers while keeping page/element markers out of retrieval scoring text. Retest broader typed retrieval scoring only through a narrower ablation or full benchmark. |
| 2026-06 | `2215246` | Targeted Vision Gate Diagnostics (D2) | Kept as diagnostic instrumentation, not as a default extraction-routing change. The e4b dev-check scored 0.54 in 11.54 min with zero provider retries, but the branch is diagnostic-only, so score deltas are not causal. Current main now rolls up triggered/reviewed/hit/useful/rescue counts, accepted hits, dropped/no-hit reasons, image source/fallback, planner skip/confidence counts, and planner target/rejected figure counts. Use these diagnostics to guide future vision acceptance tests. |
| 2026-06 | `82fcd28`, main current | Evidence-Aware Reranking (A4) | Kept as canonical retrieval ordering support, not as a new config flag. The standalone branch was neutral at 0.58 versus the matched wave-2 baseline 0.58, with evidence quality 0.82 versus 0.78. After the A2b recheck passed, main ported only the deterministic reranking layer: numeric queries boost answer-like numbers and table chunks, visual queries boost captions/figures, identifier queries boost acronym/hyphen/digit identifiers, and abstract/section chunks receive a small demotion. Post-port run `main_a4_canonical_rerank_e4b_20260617 / run_20260617_211549_pr23bo` scored 0.56 in 10.16 min with evidence quality 0.82 and `rerank_changed_count=201`. Treat this as useful canonical retrieval hygiene, but still single-replicate evidence rather than a proven broad quality win. |
| 2026-06 | `681e998`, main `4ef46b1` | Typed Retrieval Scoring (A2b) | Kept as canonical retrieval scoring behavior after user decision. This narrow ablation excludes page-number tokens, keeps reviewer-visible display text unchanged, and adds only chunk-type/section/figure/table markers to retrieval scoring text. The original e4b dev-check scored 0.62 versus matched current-main wave-2 baseline 0.58. The later suspicious 0.48 baseline was investigated with two current-main rechecks at 0.54 and 0.50 versus two detached pre-A2b controls at 0.56 and 0.52; balanced per-cell flips and invalid detached-control evidence artifacts do not prove an A2b regression. Main applies this behavior directly; it is not an operator config flag. |
| 2026-06 | `a94d9de`, main current | Excluded-Column Join Diagnostics (F) | Kept as eval/reporting cleanup, not an extraction-quality change. Eval now splits intentionally unscored metadata proposals into `excluded_proposal_count` and `excluded_proposal_diagnostics`, while preserving true non-excluded unmatched proposals as join failures. Dev-check `exp_f_excluded_join_diagnostics_e4b_20260617 / run_20260617_182008_hxoxzz` moved 25 metadata proposal diagnostics out of `join_failure_count`; post-port run `main_a4_canonical_rerank_e4b_20260617 / run_20260617_211549_pr23bo` kept `excluded_proposal_count=25`, `unmatched_proposal_count=0`, and `join_failure_count=0`. |

## Rejected Or Superseded Ideas

### Table-Aware Retrieval Units (A3)

| Field | Details |
| --- | --- |
| Status | Rejected as a standalone default implementation. |
| Tested idea | Bundle A3: add line-based `table_unit` chunks from parsed table-region text as additive retrieval units. |
| What was tested | Branch `exp/20260617-a3-table-aware-retrieval-units`, commit `cbcda65`; opt-in `retrieval.table_aware_units_enabled`, prepared-index cache separation, optimizer knob alias, and focused retrieval/cache tests. |
| Why tested | The hypothesis was that preserving table-row/header context would improve numeric or table-derived cells without replacing normal paragraph, caption, or figure chunks. |
| Evidence | Focused tests passed on the branch (`29 passed` with branch-local `PYTHONPATH`), `python scripts/check_specs.py` passed, and dev-check `exp_a3_table_units_e4b_20260617 / run_20260617_121742_7b5b5l` completed. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-e4b`; compared with matched current-main wave-2 baseline `main_wave2_baseline_e4b_20260617 / run_20260617_114230_wd7zwd`. |
| Result | Score stayed flat at 0.58 and evidence quality stayed flat at 0.78, while runtime increased from 9.98 to 15.10 min. The branch added 129 `table_unit` chunks, raised total chunks from 1409 to 1538, and produced no aggregate quality gain. |
| Decision | Do not merge the exact line-based table-unit implementation. The broader table-aware retrieval idea remains open only for a materially better table representation, such as parser-structured cells/headers or a targeted table-field path with retrieval diffs proving answer-bearing promotion. |
| Retest boundary | Do not retest this same line-splitting implementation unchanged. A future A3 variant should first show table-answer retrieval improvements on per-cell artifact diffs and avoid a broad runtime penalty before another model-heavy dev-check. |

### Schema Candidate Census Prompt Injection (B1)

| Field | Details |
| --- | --- |
| Status | Rejected as a default advisory-census implementation. |
| Tested idea | Bundle B1: mine generic schema-conditioned candidates from retrieved chunks and inject a small advisory candidate block into each per-cell extraction prompt. |
| What was tested | Branch `exp/20260617-b1-schema-candidate-census`, commit `fa94cfc`; opt-in `extraction.schema_candidate_census_enabled`, artifact persistence under `context/schema_candidate_census/`, prompt advisory block, optimizer knob aliases, run counters, and focused tests for candidate mining/prompt/artifact behavior. |
| Why tested | The hypothesis was that a compact paper/schema candidate memory could supply global candidate values while keeping per-cell extraction authoritative. |
| Evidence | Focused tests passed on the branch (`30 passed` with branch-local `PYTHONPATH`), `python scripts/check_specs.py` passed, and dev-check `exp_b1_schema_candidate_census_e4b_20260617 / run_20260617_142227_sx2a7g` completed. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-e4b`; compared with matched current-main wave-2 baseline `main_wave2_baseline_e4b_20260617 / run_20260617_114230_wd7zwd`. |
| Result | Score regressed to 0.48 versus baseline 0.58 and evidence quality fell to 0.58 versus 0.78. The branch generated census candidates for all 75 cells and 120 advisory candidates total, increased text structured calls to 120, and did not produce a useful score-per-minute tradeoff. |
| Decision | Do not merge the prompt-injected advisory census. The broader schema-conditioned paper-context idea remains open only after the candidate source is evaluated offline for hit rate and then used through verification or selector logic rather than simply adding mined values to every extraction prompt. |
| Retest boundary | Do not retest this exact advisory prompt block unchanged. A future B experiment should report candidate hit rate, verified-use rate, rejection rate, and recovered-correct versus recovered-wrong cells before candidate memory affects final prompts. |

### Recall Rescue With Current Retrieval (C1)

| Field | Details |
| --- | --- |
| Status | Rejected as a default recovery strategy. |
| Tested idea | Bundle C1: enable uncertainty-gated recall rescue against current retrieval, without whole-document mode, through a run-local dev-check override. |
| What was tested | Branch `exp-20260616-c1-uncertainty-recovery`, commit `aa64a77`; added `optimizer dev-check --recall-rescue` and materialized only the run-local candidate config with `recall_rescue_enabled=true`, `whole_document_mode=false`. |
| Why tested | The 2026-06-15 model comparison showed many recall-rescue-eligible cells but rescue disabled, making current-retrieval rescue a low-scope lever to test. |
| Evidence | Focused CLI/config tests passed (`3 passed`) and `python scripts/check_specs.py` passed. Dev-checks completed and scored for both `exp_c1_uncertainty_recovery_20260617 / run_20260616_235459_xvhsrp` on 12B and `exp_c1_uncertainty_recovery_e4b_20260617 / run_20260617_080207_gcpqb9` on e4b. |
| Scope and models | Genome editing dev-check; one replicate per model; `google/gemma-4-e4b` primary development comparison plus 12B sensitivity run; default prompt bundle; retrieval `hybrid_experimental`, top-k 12; recall rescue enabled; whole-document mode disabled. |
| Result | e4b scored 0.46 versus current-main e4b baseline 0.50 and runtime rose to 16.12 min versus 12.62 min. Rescue ran on 48/48 eligible cells, increasing text-model calls to 162 and candidate selection to 30 attempts with 14 value changes. The 12B sensitivity run also regressed: 0.50 versus 0.56 and 22.69 min versus 14.07 min. |
| Decision | Do not use broad current-retrieval recall rescue as default. The tested gate spends substantial runtime and reliability budget without net quality gain. |
| Retest boundary | Future recovery should be narrower: require schema-specific absent-feature handling, stronger evidence candidates, prepared-index or candidate-census inputs, and recovered-correct versus recovered-wrong accounting before another model-heavy run. |

### Targeted Prepared-Index Recovery (C2)

| Field | Details |
| --- | --- |
| Status | Rejected as tested. |
| Tested idea | Bundle C2: keep recall rescue disabled by default, but when explicitly enabled for dev-check, restrict rescue to uncertain or weak cells with a schema-relevant prepared-index candidate or explicit absent-feature evidence. |
| What was tested | Branch `exp/20260617-c2-targeted-prepared-index-recovery`, commit `a871bf1`; added prepared-index eligibility helpers, skip reason `no_prepared_index_candidate`, and branch-local `optimizer dev-check --recall-rescue` behavior without whole-document mode or B1 candidate census. |
| Why tested | C1 showed broad current-retrieval rescue spent many calls and regressed, but prior model comparisons still showed many rescue-eligible cells. The hypothesis was that a prepared-index gate would spend recovery only where the index already contained schema-relevant evidence. |
| Evidence | Focused backend and CLI tests passed on the branch, `git diff --check` passed, and dev-check `exp_c2_targeted_prepared_index_recovery_e4b_20260617_srcpath / run_20260617_183858_qkhe0d` completed with branch backend source on `PYTHONPATH`. Earlier non-srcpath C2 output is superseded. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-e4b`; compared with fresh current-main baseline `main_next_batch_baseline_e4b_20260617 / run_20260617_163916_12thwa` at main `da2ead2`. |
| Result | Score rose to 0.54 versus baseline 0.48, but evidence quality fell from 0.84 to 0.00 and runtime rose from 11.78 to 20.15 min. Rescue ran on 39/47 eligible cells, skipped 8, and recorded `no_prepared_index_candidate`; text calls rose from 97 to 147. |
| Decision | Do not merge this recovery gate. The nominal score lift is not acceptable with zero evidence-quality guardrail and the added runtime. The branch is useful evidence that recovery needs recovered-correct versus recovered-wrong and evidence-anchor diagnostics before another model-heavy run. |
| Retest boundary | Do not retest this exact prepared-index rescue gate unchanged. Future C work should first inspect artifact-level evidence-anchor failures and only then test a capped recovery variant with per-cell recovered-correct/recovered-wrong accounting. |

### Vision Value Acceptance Gate (D3)

| Field | Details |
| --- | --- |
| Status | Rejected as tested. |
| Tested idea | Bundle D3: allow figure-derived values to override weak or missing text only for explicitly visual, figure, or panel fields, while preserving strong direct text and non-visual fields. |
| What was tested | Branch `exp/20260617-d3-vision-acceptance-gate`, commit `d4c9ede`; added figure value acceptance decisions, blocked-reason diagnostics, per-run value-change counters, and focused tests for weak-text rescue, strong-text no-override, and non-visual no-override. |
| Why tested | D2 diagnostics showed that the current bottleneck is acceptance/gating rather than raw vision volume. The hypothesis was that a narrow value-change gate could convert useful figure hits into final values without broad visual overreach. |
| Evidence | Focused backend and runner tests passed, `git diff --check` passed, and dev-check `exp_d3_vision_acceptance_gate_e4b_20260617_srcpath / run_20260617_185951_qux0ks` completed with branch backend source on `PYTHONPATH`. Earlier non-srcpath D3 output is superseded. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-e4b`; compared with fresh current-main baseline `main_next_batch_baseline_e4b_20260617 / run_20260617_163916_12thwa`. |
| Result | Score rose to 0.60 versus baseline 0.48, and the gate exercised 9 attempted figure value changes, 7 allowed/adopted and 2 blocked. Evidence quality nevertheless fell from 0.84 to 0.00, runtime rose to 14.54 min, and figure-derived evidence rose to 26 items. |
| Decision | Do not merge the D3 app behavior as-is. The branch proves the diagnostics and gating path can be exercised, but the evidence guardrail failure is too severe for a default behavior change. |
| Retest boundary | Do not retest this exact value-override policy unchanged. Future D work should first compare per-cell artifacts and evidence anchors, or test shared page/figure batching as a runtime experiment that does not change value acceptance semantics. |

### Scoped Max/Best Prompt Guidance (E2)

| Field | Details |
| --- | --- |
| Status | Rejected as tested. |
| Tested idea | Bundle E2: add narrow dynamic prompt guidance only when schema language asks for maximum, best, highest, peak, top, selected, or representative values. |
| What was tested | Branch `exp/20260617-e2-max-best-scope-prompt`, commit `850f6ff`; appended generic selector guidance to the existing field contract only for matching schema language, with no benchmark examples, no new config flag, and no broad selector rewrite. |
| Why tested | Prior failure analysis identified maximum/best-value scope mistakes, and the guidance could be isolated to schema wording instead of a broad prompt rewrite. |
| Evidence | Focused prompt rendering tests passed, `git diff --check` passed, and dev-check `exp_e2_max_best_scope_prompt_e4b_20260617_srcpath / run_20260617_191458_tjool2` completed with branch backend source on `PYTHONPATH`. Earlier non-srcpath E2 output is superseded. |
| Scope and models | Genome editing dev-check; one replicate; `google/gemma-4-e4b`; compared with fresh current-main baseline `main_next_batch_baseline_e4b_20260617 / run_20260617_163916_12thwa`. |
| Result | Score rose slightly to 0.52 versus baseline 0.48, but evidence quality fell from 0.84 to 0.16 and runtime rose from 11.78 to 13.93 min. Candidate-selection value changes rose from 5 to 7 while structured-output repair stayed high at 20. |
| Decision | Do not merge the exact scoped prompt guidance. The implementation is narrow, but the dev-check indicates meaningful evidence-anchor risk that outweighs the small score lift. |
| Retest boundary | Do not retest this exact prompt block unchanged. Future E2 work should start with artifact-level hard-cell comparisons and evidence-anchor integrity checks before changing prompt text again. |

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
| `exp-20260616-a2-typed-retrieval-context` | `6a1348b` | [Typed Retrieval Context (A2)](#kept-or-partially-kept-ideas) | Typed retrieval text and prompt passage metadata experiment. |
| `exp-20260616-c1-uncertainty-recovery` | `aa64a77` | [Recall Rescue With Current Retrieval (C1)](#recall-rescue-with-current-retrieval-c1) | Dev-check recall-rescue override for current retrieval. |
| `exp-20260616-d2-vision-gate-diagnostics` | `2215246` | [Targeted Vision Gate Diagnostics](#kept-or-partially-kept-ideas) | Figure-review planner, no-hit, dropped-result, and accepted-hit diagnostics. |
| `exp/20260617-a3-table-aware-retrieval-units` | `cbcda65` | [Table-Aware Retrieval Units (A3)](#table-aware-retrieval-units-a3) | Line-based additive table-unit retrieval chunks; rejected as standalone default after neutral score and slower runtime. |
| `exp/20260617-a4-evidence-aware-reranking` | `82fcd28` | [Evidence-Aware Reranking (A4)](#kept-or-partially-kept-ideas) | Deterministic evidence-aware retrieval reranker; later ported as canonical current-main retrieval ordering support without a config flag. |
| `exp/20260617-a2b-typed-retrieval-scoring` | `681e998`, main `4ef46b1` | [Typed Retrieval Scoring (A2b)](#kept-or-partially-kept-ideas) | Narrow typed scoring-text ablation without page-number tokens; merged to main as canonical typed retrieval scoring. |
| `exp/20260617-b1-schema-candidate-census` | `fa94cfc` | [Schema Candidate Census Prompt Injection (B1)](#schema-candidate-census-prompt-injection-b1) | Advisory schema-candidate census prompt injection; rejected as default after score/evidence regression. |
| `exp/20260617-c2-targeted-prepared-index-recovery` | `a871bf1` | [Targeted Prepared-Index Recovery (C2)](#targeted-prepared-index-recovery-c2) | Prepared-index-gated recall rescue; rejected as exact default after evidence-quality collapse and high runtime despite a nominal score lift. |
| `exp/20260617-d3-vision-acceptance-gate` | `d4c9ede` | [Vision Value Acceptance Gate (D3)](#vision-value-acceptance-gate-d3) | Targeted figure-derived value acceptance gate and diagnostics; rejected as exact app behavior after evidence-quality collapse. |
| `exp/20260617-e2-max-best-scope-prompt` | `850f6ff` | [Scoped Max/Best Prompt Guidance (E2)](#scoped-maxbest-prompt-guidance-e2) | Narrow max/best schema-language prompt guidance; rejected as exact prompt change after evidence-quality regression. |
| `exp/20260617-f-excluded-join-diagnostics` | `a94d9de` | [Excluded-Column Join Diagnostics (F)](#kept-or-partially-kept-ideas) | Eval-only split of intentionally excluded metadata proposals from true join failures; ported to current main. |
