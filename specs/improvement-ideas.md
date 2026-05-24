# Improvement Ideas

This file is the prioritized backlog of untested or not-yet-resolved improvement ideas. Its current contents focus on extraction quality and runtime. Completed experiments, benchmark outcomes, dev-checks that decide a direction, and rejected ideas belong in `specs/experiment-results.md`.

## Outline

- [Purpose And Rules](#purpose-and-rules)
- [Current Priorities](#current-priorities)
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

- Normal idea entries: 100-180 words.
- Very small tactical ideas: 50-90 words.
- Each idea should include the problem, proposed direction, why it might work, generality risk, runtime/cost risk, how to test, and decision criterion.

## Current Priorities

1. Improve per-cell value semantics before adding broader batching or routing changes.
2. Reduce hard-column errors on figure/panel fields, exact architecture strings, numeric maxima, sequence/barcode lengths, and physical methods parameters.
3. Keep runtime stable by measuring score-per-minute, structured-output reliability, and targeted recovery acceptance rates.
4. Preserve generality across research fields and unknown schemas; avoid benchmark-specific production logic.

## Priority 1: Next Best Bets

### Candidate Selection And Normalization

Problem: the latest analysis shows many wrong proposals had plausible evidence but selected the wrong value type, such as a generic figure instead of a panel, a shorthand system name instead of a full architecture, or a spacer length instead of a barcode length. Proposed direction: add a small post-extraction selector that compares candidate values against generic schema semantics before finalizing. It should normalize numeric units, figure/panel citations, and exact identifiers. Evidence so far: the 2026-05-24 model comparison found very low app accuracy for representative/source figure, architecture, max-efficiency, sequence-length, and barcode-length columns. Generality risk: overfitting if keyed to benchmark column names; keep rules driven by field type, units, and schema wording. Runtime/cost risk: low if selector reuses existing candidates. Test by comparing hard-column accuracy and aggregate score. Decision criterion: improve hard columns without lowering aggregate score or adding meaningful runtime.

### Per-Cell Retrieval Improvements

Problem: hard failures often involve missing or weak evidence for methods parameters, exact identifiers, and numeric values. Proposed direction: improve retrieval/context assembly for individual cells instead of batching cells together. Use schema descriptions, field types, allowed values, row context, paper metadata, and schema-aware query expansions for maxima, figure/panel citations, methods parameters, physical dimensions, sequence/barcode lengths, and exact system names. Evidence so far: retrieval misses and wrong evidence selection appeared in the 2026-05-24 proposal review, especially for section thickness and numeric/identifier fields. Generality risk: hard filters could hide unusual evidence; prefer additive reranking. Runtime/cost risk: moderate if retrieval expands too broadly. Test on the three-benchmark suite with proposal-table diagnostics. Decision criterion: improve or preserve per-cell baseline score while keeping runtime stable.

### Failure-Driven Prompt Repair

Problem: broad prompt changes are hard to attribute and can hurt unrelated fields. Proposed direction: classify incorrect per-cell proposals by generic failure class before changing prompts, then add narrowly scoped schema-driven guidance. Candidate classes include wrong metadata, missed methods value, missed maximum/best value, confused comparator/control, confused sequence length versus barcode/motif/spacer length, wrong figure/panel selection, exact identifier shortening, unsupported blank handling, and wrong normalization. Evidence so far: the 2026-05-24 failure analysis identified several recurring classes across benchmarks. Generality risk: prompt examples must not leak benchmark answers or encode field-specific shortcuts. Runtime/cost risk: low if prompt length stays controlled. Test with one small prompt patch at a time and compare column difficulty. Decision criterion: improve targeted weak failure classes without lowering aggregate score on other datasets.

### Stronger Model And Parameter Sweep

Problem: model choice materially changed score, but the highest-scoring app model was much slower. Proposed direction: keep the per-cell architecture and run interpretable model-only comparisons first, then vary retrieval, top-k, prompt settings, and structured-output modes one factor at a time. Record score, runtime, provider request counts, text/vision calls, score per minute, structured errors, failed structured elapsed time, retries, parse repairs, and failures per 100 cells. Evidence so far: `cand_0005 / qwen/qwen3.6-27b` scored best in the 2026-05-24 app comparison but had the worst runtime among viable app candidates. Generality risk: optimizing for one benchmark suite could hide field-specific weakness. Runtime/cost risk: high for larger models. Decision criterion: materially improve aggregate score without unacceptable runtime, structured-output fragility, or cost.

## Priority 2: Promising But Needs More Evidence

### Uncertainty-Gated Recovery

Problem: proposals marked `unclear`, blocked, missing evidence, anchor invalid, or low-confidence inferred can still become final scored outputs. Proposed direction: treat these states as targeted recovery signals. Recovery should rerun retrieval with schema-specific query expansion, inspect methods/supplement/table/figure-caption chunks, or ask a stricter value-selection prompt. Evidence so far: app-only incorrect cells in the latest analysis were often selected from `unclear` or `found` states, which means uncertainty is not being used strongly enough. Generality risk: excessive retries on genuinely absent values; require a schema-relevant candidate before spending another model call. Runtime/cost risk: moderate unless capped per row/paper. Test recovered-correct cells, recovered-wrong cells, added calls, and runtime. Decision criterion: net score gain per added minute beats simply switching to the slower best model.

### Targeted Vision Fallback

Problem: vision can help figure-derived fields but broad figure review adds runtime and has not yet proven a stable score win. Proposed direction: keep text extraction first and trigger vision only when text evidence is weak/missing, the field is likely visual, or validation indicates figure evidence is needed. Do not trigger vision merely because retrieval found a caption. Batch visual questions by page or figure when multiple cells need the same image. Evidence so far: in the 2026-05-24 run, figure-review planning triggered many cells but few attempts were useful; there was no matched no-vision candidate for the same model. Generality risk: visual heuristics may miss nonstandard figures. Runtime/cost risk: high without budgets. Test matched vision/no-vision candidates. Decision criterion: accepted vision value changes must improve score enough to justify added runtime.

### Judge Calibration And Adjudication

Problem: benchmark interpretation is limited when judge disagreement is high or one judge is systematically harsher. Proposed direction: treat internal and external proposals with the same scoring path, including deterministic exact-match fast paths; compare judge models on a small hand-reviewed calibration set; add adjudication or tie-break options for dual-judge disagreements. Evidence so far: all non-gold candidates in the 2026-05-24 model comparison carried `judge_instability_observed`, and judge disagreement affected fine-grained interpretation. Generality risk: adjudication can hide judge weakness if not reported transparently. Runtime/cost risk: extra judge calls can be expensive. Test primary score, disagreement rate, adjudicated score, and judge model IDs. Decision criterion: benchmark outcomes become more auditable without obscuring raw judge behavior.

### Improve Structured Output For Qwen Models

Problem: some Qwen-family runs produced malformed JSON or structured-output errors, which increases runtime and can drop proposals. Proposed direction: audit the existing JSON repair and structured-output fallback path before adding dependencies; consider a library such as `json_repair` only if it covers observed failures that current bounded repair cannot handle. Evidence so far: the 2026-05-24 run recorded structured-output failures for `cand_0005 / qwen/qwen3.6-27b`, and an LM Studio issue reports Qwen structured-output problems. Generality risk: overly permissive repair may accept corrupted semantic content. Runtime/cost risk: low for local repair, but retries add latency. Test on captured malformed outputs. Decision criterion: reduce structured-output errors without accepting invalid schema content or hiding provider instability.

## Priority 3: Longer-Term Or Riskier Ideas

### Advisory Schema Planning

Problem: schema planning could help extraction choose evidence sources, but authoritative planners previously reduced generality and accuracy. Proposed direction: revisit schema planning only as advisory metadata, not routing or batching authority. A possible config is `extraction.column_planning.mode = disabled | advisory_deterministic | advisory_llm`, with artifacts such as `planning/column_plan.json`. Planner output may annotate likely evidence sources, visual need, blank policy, confidence, and rationale. Evidence so far: deterministic and LLM-primary planning did not beat the per-cell baseline when used too aggressively. Generality risk: high if planner assumptions become hard filters. Runtime/cost risk: low to moderate depending on LLM use. Test on benchmark and synthetic non-benchmark schemas. Decision criterion: advisory planning improves diagnostics or retrieval without lowering score.

### Lazy Page Rendering

Problem: eager page rendering may spend time creating images that are never inspected. Proposed direction: preserve a parser policy such as `parser.page_render_policy = eager | lazy`; in lazy mode, parse text/tables/metadata first and render page images only for vision, review UI, or exports that need them. Cache rendered pages by PDF, page, and render settings. Evidence so far: earlier grouped-extraction work touched lazy rendering, but the decisive comparisons did not prove a runtime win. Generality risk: review/export artifacts must remain available when operators need them. Runtime/cost risk: low if cache invalidation is correct. Test rendered page count, render time, review/export behavior, and end-to-end runtime. Decision criterion: reduce runtime or disk work without breaking review/export artifacts.

### Batch-Then-Verify Hybrid

Problem: direct batching reduced call count but hurt correctness. Proposed direction: try batching only as a candidate-value generator, then verify or correct at the per-cell level. A possible mode is `extraction.mode = batch_then_verify`, accepting only high-confidence verified batch outputs and falling back to full per-cell extraction for missing, invalid, or low-confidence cells. Evidence so far: field-group and paper-batch architectures lost accuracy and did not improve end-to-end runtime, but they were not limited to candidate generation. Generality risk: batch prompts can still bias values across columns or rows. Runtime/cost risk: high if verification plus fallback doubles work. Test acceptance rate, verifier rejection rate, fallback rate, score, and runtime. Decision criterion: beat per-cell score-per-minute on the broader benchmark suite.

## Parking Lot

No parked ideas currently. Add only low-priority or underspecified ideas here, and promote them into a priority section once they have a clear test path.

## Idea Entry Format

```markdown
### Idea Name

Problem:
Proposed direction:
Why it might work:
Evidence so far:
Generality risk:
Runtime/cost risk:
How to test:
Decision criterion:
```
