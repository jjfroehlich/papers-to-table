# Improvement Ideas

This file is the prioritized backlog of untested or not-yet-resolved improvement ideas. Its current contents focus on extraction quality and runtime. Completed experiments, benchmark outcomes, dev-checks that decide a direction, and rejected ideas belong in `specs/experiment-results.md`.

## Outline

- [Purpose And Rules](#purpose-and-rules)
- [Current Priorities](#current-priorities)
- [Experiment Bundles And Dependencies](#experiment-bundles-and-dependencies)
- [Priority 1: Next Best Bets](#priority-1-next-best-bets)
- [Priority 2: Promising But Needs More Evidence](#priority-2-promising-but-needs-more-evidence)
- [Priority 3: Longer-Term Or Riskier Ideas](#priority-3-longer-term-or-riskier-ideas)
- [Parking Lot](#parking-lot)
- [Idea Entry Format](#idea-entry-format)

## Purpose And Rules

- Ideas are ordered by priority, not chronology.
- New ideas start here. Once an idea is implemented, benchmarked, dev-checked, rejected, or conceptually ruled out, move the evidence to `specs/experiment-results.md`.
- If a result partly informs an idea but does not decide it, keep the idea here with an `Evidence so far:` line.
- If an idea is rejected, remove it from this file and record the rejection in the results file.
- Do not duplicate completed result tables here.

Entry length guidance:

- Normal idea entries: one compact table with eight rows; keep each detail cell to one or two sentences.
- Very small tactical ideas may use shorter detail cells, but should keep the same row labels.
- Each idea must include the problem, direction, why it might work, evidence so far, generality risk, runtime/cost risk, test, and decision criterion.

## Idea Entry Format

Use the same eight-row table for every active idea. Fold implementation notes, guardrails, metrics, and candidate subtypes into `Direction`, `Why it might work`, or `Test` instead of adding ad hoc rows.

```markdown
### Idea Name

| Field | Details |
|---|---|
| **Problem** |  |
| **Direction** |  |
| **Why it might work** |  |
| **Evidence so far** |  |
| **Generality risk** |  |
| **Runtime/cost risk** |  |
| **Test** |  |
| **Decision criterion** |  |
```

## Current Priorities

1. Use `google/gemma-4-e4b` as the development default model for upcoming local improvement experiments so new results stay comparable with earlier e4b work; keep regular 12B and QAT rows as model-sensitivity or occasional ceiling references, not the default.
2. Prioritize workflow, prompt, retrieval, evidence handling, uncertainty-gated recovery, and figure/table handling over broad model shopping.
3. Reduce hard-column errors on figure/panel fields, exact architecture strings, numeric maxima, sequence/barcode lengths, barcode presence/location, model-system fields, physical methods parameters, and table-derived values.
4. Keep runtime stable by measuring score-per-minute, structured-output reliability, targeted recovery acceptance rates, accepted figure-derived evidence, and retrieval/indexing overhead.
5. Preserve generality across research fields and unknown schemas; avoid benchmark-specific production logic.

## Experiment Bundles And Dependencies

The priority sections below remain the active improvement backlog. This section explains how to test related ideas so conclusions are interpretable: some ideas are standalone experiments, while others are infrastructure or dependent layers that should be tested as an ablation ladder. The goal is to avoid falsely rejecting infrastructure because it does not improve score alone, and to avoid uninterpretable wins from bundles that change too many variables at once.

| Bundle | Includes | Suggested ablation ladder | Interpretation |
|---|---|---|---|
| **A. Retrieval Quality** | Current prepared retrieval index baseline, [Per-Cell Retrieval Improvements](#per-cell-retrieval-improvements), [Table-Aware Retrieval Units](#table-aware-retrieval-units), and optional lexical/hybrid/embedding retrieval backends. | A0: current baseline with prepared indexes and prompt-header orientation. A3: add table-aware retrieval units. A4: optional hybrid/embedding reranking. Optional A2b: only retest retrieval-scoring typed markers as a narrower ablation. | Prepared indexes and safer prompt-header orientation are current main behavior. Next A-bundle tests should change one quality layer at a time and use index source counts plus retrieval artifact diffs to check equivalence and overhead. |
| **B. Paper-Level Candidate Memory** | [Schema-Conditioned Paper Context](#schema-conditioned-paper-context), [Candidate Selection And Normalization](#candidate-selection-and-normalization), and later [Batch-Then-Verify Hybrid](#batch-then-verify-hybrid). | B0: best per-cell retrieval baseline. B1: schema-conditioned candidate census, advisory only. B2: selector/normalizer using those candidates. B3: batch-then-verify only if B1/B2 show promise. | Per-cell extraction remains authoritative; track candidate hit rate, verified-use rate, rejection rate, score, tokens, and runtime. |
| **C. Recovery** | [Uncertainty-Gated Recovery](#uncertainty-gated-recovery). | C0: current baseline. C1: rejected broad current-retrieval rescue. C2: narrower recovery using prepared-index evidence. C3: recovery using schema-conditioned candidate census. | Recovery should be capped and judged by net score gain per added runtime plus recovered-correct versus recovered-wrong cells. |
| **D. Vision** | [Targeted Vision Fallback](#targeted-vision-fallback). | D0: no vision. D1: current/default figure-review behavior with D2 diagnostics. D3: targeted acceptance/gate change or shared page/figure batching. | Broad vision triggering is not the same idea as targeted vision fallback; use matched controls and accepted-correct-per-added-call metrics. |
| **E. Prompt And Selection** | [Candidate Selection And Normalization](#candidate-selection-and-normalization) and [Failure-Driven Prompt Repair](#failure-driven-prompt-repair). | E1: selector/normalizer. E2: one narrow prompt-repair class at a time. E3: selector plus successful prompt-repair classes. | Separate selector changes from prompt changes first because one changes candidate choice and the other changes candidate generation. |
| **F. Evaluation And Runtime Reliability** | [Judge Calibration And Adjudication](#judge-calibration-and-adjudication), [Improve Structured Output For Local Models](#improve-structured-output-for-local-models), and [Lazy Page Rendering](#lazy-page-rendering). | Test independently unless an experiment needs measurement cleanup before quality comparisons. | These are mostly measurement, reliability, or runtime experiments, not direct extraction-quality interventions. |

## Priority 1: Next Best Bets

### Schema-Conditioned Paper Context

| Field | Details |
|---|---|
| **Problem** | Per-cell extraction often missed values that require aggregating scattered information across a paper, while whole-paper batching as the authoritative answer path was previously less accurate. |
| **Direction** | Build a schema-derived candidate census, not a benchmark-derived census, using the prepared retrieval index as its auditable substrate. First infer generic column needs from the input schema, such as quantity, identifier, presence/absence, location, figure/table reference, method parameter, named entity, URL/citation, list/set, or best/max/min value; then mine compact paper candidates for only those needs with evidence anchors. Per-cell extraction remains authoritative and may only cite, verify, or reject these candidates. |
| **Why it might work** | External Codex-style outputs were much stronger and faster on synthesis-heavy fields, suggesting that paper-level context helps, but rejected paper-batch results show that final answers still need cell-level verification. A compressed context or census can supply global candidates without giving every cell a long full-paper prompt. |
| **Evidence so far** | The 2026-06-15 compare run kept a large external-agent gap after broad local model shopping: external baselines scored 0.8019-0.8259 while the best local pipeline score was 0.6784 and the regular 12B reference scored 0.6467. The 2026-06-17 development-default reversion keeps near-term experiments on `google/gemma-4-e4b` for comparability; together these results support paper/context workflow changes over routine model sweeps. See `experiment-results.md#2026-06-15-compare-models-default` and `experiment-results.md#2026-06-17-development-default-reversion`. |
| **Generality risk** | High if candidate categories are hard-coded from benchmarks. Production logic must derive needs from schema text, allowed values, examples, field type, and reusable document structures rather than branch on domain-specific terms; benchmark-specific categories belong only in tests and analysis notes. |
| **Runtime/cost risk** | Low to moderate if the context is deterministic or one compact per-paper/per-schema call that replaces repeated failed recovery calls. High if every cell receives full-paper text. Cache per paper/schema and inject only a small filtered subset per cell. |
| **Test** | Use `google/gemma-4-e4b` and follow Bundle B: compare the best per-cell retrieval baseline against advisory-only schema-conditioned candidate census before adding selector or batch-verify layers. |
| **Decision criterion** | Improve candidate hit rate, verified-use rate, synthesis-heavy hard columns, and score-per-minute without lowering unrelated fields or accepting unverified paper-level candidates. |

### Uncertainty-Gated Recovery

| Field | Details |
|---|---|
| **Problem** | Proposals marked `unclear`, blocked, missing evidence, anchor invalid, or low-confidence inferred can still become final scored outputs. |
| **Direction** | Treat these states as targeted recovery signals. Recovery should use the prepared retrieval index or schema-conditioned candidate census rather than repeating the rejected broad current-retrieval rescue. Add special handling for absent-feature fields so `unresolved` can be accepted when the schema asks for presence/location and the evidence supports no feature. |
| **Why it might work** | Uncertainty flags already identify cells where the pipeline suspects weak support, so recovery can focus extra work on high-risk outputs instead of all cells. |
| **Evidence so far** | The 2026-06-15 compare run repeatedly found recall rescue eligibility but no use because recall rescue was disabled: regular Gemma 12B had 57 eligible/0 used, QAT had 62/0, Qwen had 59/0, and other internal candidates had 60-66 eligible/0 used. The 2026-06-17 C1 e4b dev-check then enabled broad current-retrieval rescue; it used 48/48 eligible cells but scored 0.46 versus the matched current-main e4b baseline at 0.50 and added runtime. The 12B sensitivity run also regressed at 0.50 versus 0.56. Future recovery work should be narrower than the tested C1 gate. |
| **Generality risk** | Excessive retries on genuinely absent values; require a schema-relevant candidate or explicit absent-feature evidence before spending another model call. |
| **Runtime/cost risk** | Moderate unless capped per row/paper and measured against score-per-minute. |
| **Test** | Continue Bundle C after the rejected C1 current-retrieval gate: next tests should use a narrower recovery trigger with prepared-index or schema-conditioned candidate-census inputs. Measure recovered-correct cells, recovered-wrong cells, added calls, runtime, missing evidence, anchor validity, and score. |
| **Decision criterion** | Net score gain per added minute beats simply switching to the slower QAT model. |

### Per-Cell Retrieval Improvements

| Field | Details |
|---|---|
| **Problem** | Hard failures often involve missing or weak evidence for methods parameters, exact identifiers, figure/panel fields, and numeric values. |
| **Direction** | Improve retrieval/context assembly for individual cells instead of batching cells together. Current main already uses prepared indexes and exposes section/table/figure orientation in prompt passage headers while keeping display text source-preserving. Next retrieval changes should focus on table-aware retrieval units, evidence-aware reranking, or a narrow ablation of typed retrieval-scoring markers without page-number tokens. Do not rely on threshold-only score-shape prompt trimming as the next step; the tested branches did not show a reliable gain. |
| **Why it might work** | Schema descriptions, field types, allowed values, row context, paper metadata, and schema-aware query expansions can target maxima, figure/panel citations, methods parameters, physical dimensions, sequence/barcode lengths, and exact system names. Better chunk semantics and evidence-aware reranking may avoid feeding topical but non-answering context into the extraction prompt. |
| **Evidence so far** | The 2026-06-15 compare run showed that changing local models did not close the external-agent gap, while top candidates still had missing evidence and modest anchor-valid rates. Earlier score-shape prompt-gating branches were rejected. The 2026-06-17 A2 typed-context e4b dev-check scored 0.60 versus matched current-main e4b at 0.50, but the 12B sensitivity run regressed at 0.50 versus 0.56. Main kept only the lower-risk prompt-header orientation and did not merge page/element marker expansion into retrieval scoring text. Treat broader typed scoring as model-sensitive and test it only as a narrow ablation. |
| **Generality risk** | Hard filters could hide unusual evidence; prefer additive context and reranking. |
| **Runtime/cost risk** | Moderate if retrieval expands too broadly; low for lexical score gating, higher if a local cross-encoder reranker is added. |
| **Test** | Use `google/gemma-4-e4b` and continue Bundle A from the current prepared-index baseline: test A3 table-aware units or A4 evidence-aware reranking separately. Only retest typed retrieval-scoring markers if the ablation excludes page-number tokens and reports retrieval artifact diffs plus score/runtime. |
| **Decision criterion** | Improve retrieval answerability, hard-column accuracy, or aggregate score without broad regressions or unstable runtime. |

### Table-Aware Retrieval Units

| Field | Details |
|---|---|
| **Problem** | Numeric and matrix-like fields can be wrong even when the relevant value is present because flattened table text loses header, row, column, and unit relationships. |
| **Direction** | Create additive table-aware retrieval units from parsed table regions, preserving row labels, column headers, units, captions, page, and nearby callouts. These units should supplement normal paragraph/caption chunks rather than replace them. |
| **Why it might work** | Many scientific values are meaningful only in table structure: the same number can refer to different rows, columns, units, or conditions. Preserving those relationships should reduce wrong-value selection. |
| **Evidence so far** | The 2026-06-15 model comparison did not make table/numeric failures disappear: regular 12B remained below the external baselines by about 0.155-0.179 score, and the stronger local variants were slower rather than qualitatively different. Earlier failure analysis still points to max editing efficiency, MPRA sequence length, barcode length, section thickness, and methods parameters as fields where table or structured local context may matter. |
| **Generality risk** | Table parsing varies across papers and fields, so table units must degrade gracefully to raw text. |
| **Runtime/cost risk** | Low to moderate depending on parser cost and table count. |
| **Test** | Test as Bundle A3 on the current prepared-index baseline; compare matched `google/gemma-4-e4b` runs with and without table-aware chunks. |
| **Decision criterion** | Improve table/numeric hard columns without reducing aggregate score or adding large runtime. |

### Targeted Vision Fallback

| Field | Details |
|---|---|
| **Problem** | Vision can help figure-derived fields, but broad figure review adds runtime and has not yet proven a stable score win. |
| **Direction** | Keep text extraction first, but audit and tune the planner, shortlist, image-selection, schema-repair, no-hit, and acceptance path before increasing vision volume. Trigger vision only when text evidence is weak/missing and the schema requires visual inspection or exact figure/panel selection; batch visual questions by page or figure when multiple cells need the same image. |
| **Why it might work** | The latest hard columns include figure/panel fields, but the current bottleneck is not just the number of vision calls. The path often triggers, gets planner-skipped, succeeds without a usable proposed value, or produces evidence that is not accepted into the final answer. |
| **Evidence so far** | The 2026-06-15 compare run showed planner/acceptance problems: regular Gemma 12B had 34 triggers, 34 planner skips, and 0 vision calls; QAT had 38 triggers, 28 skips, 13 calls, 12 no-hit outcomes, and 1 figure-derived evidence item; Qwen had 31 triggers, 27 skips, 6 calls, 3 failed attempts, and 2 figure-derived evidence items. The 2026-06-17 D2 e4b diagnostics branch scored 0.54 versus matched current-main e4b at 0.50 and exposed a more useful funnel: 22 triggered cells, 16 reviewed cells, 16 accepted hits, 14 useful cells, and 4 missing-value/no-hit outcomes. Main now keeps those diagnostics, so the next vision step can focus on accepted-correct-per-call behavior, not broader uncapped vision. |
| **Generality risk** | Visual heuristics may miss nonstandard figures. |
| **Runtime/cost risk** | High without budgets, moderate if calls are capped and shared across cells that target the same page or figure. |
| **Test** | With `google/gemma-4-e4b`, continue Bundle D from current D2 diagnostics: test a narrower acceptance/gate change or shared page/figure batching against current/default figure review. Report trigger, skip, call, failure, no-hit, dropped reason, accepted figure-evidence, accepted-correct-per-added-call, score, and runtime counts. |
| **Decision criterion** | Accepted vision value changes must improve score enough to justify added runtime; increased call count alone is not success. |

### Failure-Driven Prompt Repair

| Field | Details |
|---|---|
| **Problem** | Broad prompt changes are hard to attribute and can hurt unrelated fields. |
| **Direction** | Classify incorrect per-cell proposals by generic failure class before changing prompts, then add narrowly scoped schema-driven guidance for classes such as wrong metadata, missed methods value, missed maximum/best value, confused comparator/control, sequence/barcode/motif/spacer confusion, wrong figure/panel selection, exact identifier shortening, unsupported blank handling, and wrong normalization. |
| **Why it might work** | Targeted prompt changes can address recurring generic mistakes while avoiding large prompt rewrites that alter unrelated behavior. |
| **Evidence so far** | The 2026-06-15 compare run showed that model choice changes did not eliminate the same hard-column families, so failure-class prompt repair remains relevant but should follow evidence and retrieval audits. Earlier failure analysis identified wrong figure panel granularity, wrong numeric scope, count-vs-length confusion, absent-feature handling, model-system-vs-species/genome confusion, exact architecture shortening, methods-parameter misses, and maximum/best-value selection errors. |
| **Generality risk** | Prompt examples must not leak benchmark answers or encode field-specific shortcuts. |
| **Runtime/cost risk** | Low if prompt length stays controlled. |
| **Test** | Use `google/gemma-4-e4b` and follow Bundle E: test one prompt-repair class at a time before combining it with selector changes. Compare column difficulty, aggregate score, structured-output reliability, and runtime. |
| **Decision criterion** | Improve targeted weak failure classes without lowering aggregate score on other datasets. |

## Priority 2: Promising But Needs More Evidence

### Candidate Selection And Normalization

| Field | Details |
|---|---|
| **Problem** | Wrong proposals often had plausible evidence but selected the wrong value type, such as a generic figure instead of a panel, a shorthand system name instead of a full architecture, or a spacer length instead of a barcode length. |
| **Direction** | Add a small post-extraction selector that compares candidate values against generic schema semantics before finalizing. Normalize numeric units, figure/panel citations, exact identifiers, count-vs-length distinctions, insert-vs-spacer/barcode lengths, barcode presence/location, absent-feature answers, and model-system-vs-species/genome wording. |
| **Why it might work** | The failure mode is often choosing among plausible candidate values, not complete absence of information. A generic selector can enforce schema semantics without changing the base extraction architecture. |
| **Evidence so far** | The 2026-06-02 comparison confirmed wrong-value selection on representative/source figures, architecture, max efficiency, sequence length, barcode length/location, model system, and section thickness. Two 2026-06-03 schema-semantic guardrail branches scored only 0.40 and 0.46 on genome editing and were rejected as default implementations; this broader idea remains open only after better evidence candidates or recovery create a stronger candidate set. |
| **Generality risk** | Overfitting if keyed to benchmark column names; keep rules driven by field type, units, and schema wording. |
| **Runtime/cost risk** | Low if selector reuses existing candidates, but previous selector branches added reliability and runtime cost. |
| **Test** | Revisit through Bundle B or Bundle E only after retrieval, recovery, or candidate-census changes produce explicit competing candidates; compare hard-column accuracy, value-change correctness, aggregate score, and runtime. |
| **Decision criterion** | Improve hard columns without lowering aggregate score or adding meaningful runtime. |

### Judge Calibration And Adjudication

| Field | Details |
|---|---|
| **Problem** | Benchmark interpretation is limited when judge disagreement is high or one judge is systematically harsher. |
| **Direction** | Treat internal and external proposals with the same scoring path, keeping text exact-match fast paths opt-in for calibration rather than default scoring. Compare judge models on a small hand-reviewed calibration set, and add adjudication or tie-break options for dual-judge disagreements. |
| **Why it might work** | Calibration separates true extraction differences from judge noise and makes small score differences more interpretable. |
| **Evidence so far** | The 2026-06-15 compare run still showed high dual-judge disagreement: regular Gemma 12B was 31.0%, QAT was 20.5%, Qwen was 31.6%, and several other internal candidates were near or above 29%. This does not overturn the model ranking, but it makes small margins and per-column conclusions less stable. |
| **Generality risk** | Adjudication can hide judge weakness if not reported transparently. |
| **Runtime/cost risk** | Extra judge calls can be expensive. |
| **Test** | Treat as Bundle F measurement work: record primary score, disagreement rate, adjudicated score, and judge model IDs. |
| **Decision criterion** | Benchmark outcomes become more auditable without obscuring raw judge behavior. |

### Improve Structured Output For Local Models

| Field | Details |
|---|---|
| **Problem** | Some local-model runs produce malformed JSON or structured-output errors, which increases runtime and can drop proposals. |
| **Direction** | Treat backend-native `json_schema` / `json_object` support as an optional capability, not the reliability baseline. Prefer prompt-only JSON plus client-side validation, bounded repair, raw-output logging, and clear metadata for whether guided output, retry, or repair was used; consider `json_repair` only if current bounded repair cannot handle captured failures. Gate model candidates on structured-output reliability before expensive full sweeps. |
| **Why it might work** | Local backends often fail at constrained output even when they can answer in plain chat. Moving reliability to client-side validation and bounded repair keeps proposals from disappearing because of transport or formatting quirks. |
| **Evidence so far** | The 2026-06-15 compare run showed reliability cost across more than one model family: regular Gemma 12B had 11 provider retries and 14 structured errors, QAT had 2 structured errors plus 13 structured repairs, and Qwen had 3 structured errors with about 165 sec failed structured elapsed time. This is worth improving, but the model-comparison decision makes it secondary to retrieval/recovery quality. |
| **Generality risk** | Overly permissive repair may accept corrupted semantic content. |
| **Runtime/cost risk** | Low for local repair, but retries add latency. |
| **Test** | Treat as Bundle F reliability work: replay captured malformed outputs and measure retry, repair, invalid-schema acceptance, and runtime effects. |
| **Decision criterion** | Reduce structured-output errors without accepting invalid schema content or hiding provider instability. |

## Priority 3: Longer-Term Or Riskier Ideas

### Advisory Schema Planning

| Field | Details |
|---|---|
| **Problem** | Schema planning could help extraction choose evidence sources, but authoritative planners previously reduced generality and accuracy. |
| **Direction** | Revisit schema planning only as advisory metadata, not routing or batching authority. A possible config is `extraction.column_planning.mode = disabled / advisory_deterministic / advisory_llm`, with artifacts such as `planning/column_plan.json`; planner output may annotate likely evidence sources, visual need, blank policy, confidence, and rationale. |
| **Why it might work** | Advisory metadata could improve retrieval and diagnostics while avoiding the accuracy loss seen when planners controlled routing or validation. |
| **Evidence so far** | Deterministic and LLM-primary planning did not beat the per-cell baseline when used too aggressively. |
| **Generality risk** | High if planner assumptions become hard filters. |
| **Runtime/cost risk** | Low to moderate depending on LLM use. |
| **Test** | Compare on benchmark and synthetic non-benchmark schemas. |
| **Decision criterion** | Advisory planning improves diagnostics or retrieval without lowering score. |

### Lazy Page Rendering

| Field | Details |
|---|---|
| **Problem** | Eager page rendering may spend time creating images that are never inspected. |
| **Direction** | Preserve a parser policy such as `parser.page_render_policy = eager / lazy`; in lazy mode, parse text/tables/metadata first and render page images only for vision, review UI, or exports that need them. Cache rendered pages by PDF, page, and render settings. |
| **Why it might work** | Many runs can answer from text and metadata without inspecting page images, so delayed rendering can avoid unnecessary work while keeping images available when needed. |
| **Evidence so far** | Earlier grouped-extraction work touched lazy rendering, but the decisive comparisons did not prove a runtime win. |
| **Generality risk** | Review/export artifacts must remain available when operators need them. |
| **Runtime/cost risk** | Low if cache invalidation is correct. |
| **Test** | Treat as Bundle F runtime work: measure rendered page count, render time, review/export behavior, and end-to-end runtime. |
| **Decision criterion** | Reduce runtime or disk work without breaking review/export artifacts. |

### Batch-Then-Verify Hybrid

| Field | Details |
|---|---|
| **Problem** | Direct batching reduced call count but hurt correctness. |
| **Direction** | Try batching only as a candidate-value generator, then verify or correct at the per-cell level. This is Bundle B3 and should come after advisory schema-conditioned candidate memory and candidate selection show promise; per-cell extraction remains authoritative. |
| **Why it might work** | Batch prompts may cheaply surface candidate values, while per-cell verification can prevent the cross-cell contamination that hurt direct batching. |
| **Evidence so far** | Field-group and paper-batch architectures lost accuracy and did not improve end-to-end runtime, but they were not limited to candidate generation. The 2026-06-02 external-result gap suggests paper-level candidate gathering is valuable; test [Schema-Conditioned Paper Context](#schema-conditioned-paper-context) first because it is a narrower advisory version of this idea. |
| **Generality risk** | Batch prompts can still bias values across columns or rows. |
| **Runtime/cost risk** | High if verification plus fallback doubles work. |
| **Test** | Measure acceptance rate, verifier rejection rate, fallback rate, score, and runtime only after B1/B2 establish useful candidate memory. |
| **Decision criterion** | Beat per-cell score-per-minute on the broader benchmark suite. |

## Parking Lot

No parked ideas currently. Add only low-priority or underspecified ideas here, and promote them into a priority section once they have a clear test path.
