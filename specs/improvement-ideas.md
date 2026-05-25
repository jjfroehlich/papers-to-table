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

1. Improve per-cell value semantics and typed retrieval context before adding broader batching or routing changes.
2. Reduce hard-column errors on figure/panel fields, exact architecture strings, numeric maxima, sequence/barcode lengths, physical methods parameters, and table-derived values.
3. Keep runtime stable by measuring score-per-minute, structured-output reliability, targeted recovery acceptance rates, and retrieval/indexing overhead.
4. Preserve generality across research fields and unknown schemas; avoid benchmark-specific production logic.

## Priority 1: Next Best Bets

### Candidate Selection And Normalization

| Field | Details |
|---|---|
| **Problem** | Wrong proposals often had plausible evidence but selected the wrong value type, such as a generic figure instead of a panel, a shorthand system name instead of a full architecture, or a spacer length instead of a barcode length. |
| **Direction** | Add a small post-extraction selector that compares candidate values against generic schema semantics before finalizing. Normalize numeric units, figure/panel citations, and exact identifiers. |
| **Why it might work** | The failure mode is often choosing among plausible candidate values, not complete absence of information. A generic selector can enforce schema semantics without changing the base extraction architecture. |
| **Evidence so far** | The 2026-05-24 model comparison found very low app accuracy for representative/source figure, architecture, max-efficiency, sequence-length, and barcode-length columns. |
| **Generality risk** | Overfitting if keyed to benchmark column names; keep rules driven by field type, units, and schema wording. |
| **Runtime/cost risk** | Low if selector reuses existing candidates. |
| **Test** | Compare hard-column accuracy and aggregate score. |
| **Decision criterion** | Improve hard columns without lowering aggregate score or adding meaningful runtime. |

### Per-Cell Retrieval Improvements

| Field | Details |
|---|---|
| **Problem** | Hard failures often involve missing or weak evidence for methods parameters, exact identifiers, figure/panel fields, and numeric values. |
| **Direction** | Improve retrieval/context assembly for individual cells instead of batching cells together. Add typed contextual chunk text for retrieval, such as page, element type, section path, caption/table markers, and local heading context, while keeping display text source-preserving for review. Also test score-shape-aware context gating: persist per-chunk retrieval scores, allow empty context when candidates are weak, trim to top-1 when the lead chunk has a large confidence gap, and keep only a small coherent bundle when top scores are close. |
| **Why it might work** | Schema descriptions, field types, allowed values, row context, paper metadata, and schema-aware query expansions can target maxima, figure/panel citations, methods parameters, physical dimensions, sequence/barcode lengths, and exact system names. Score-shape gating may prevent one relevant chunk from being diluted by weak neighbors and may avoid feeding topical but non-answering context into the extraction prompt. |
| **Evidence so far** | The 2026-05-24 proposal review and archived research notes both point to weak typed context for figures, methods, and numeric values. |
| **Generality risk** | Hard filters could hide unusual evidence; prefer additive context and reranking. |
| **Runtime/cost risk** | Moderate if retrieval expands too broadly; low for lexical score gating, higher if a local cross-encoder reranker is added. |
| **Test** | Run on the three-benchmark suite. Compare fixed top-k against dynamic top-k, confidence-gap trimming, normalized-score thresholds, and only then optional local cross-encoder reranking. |
| **Decision criterion** | Improve or preserve per-cell baseline score while keeping runtime stable. |

### Table-Aware Retrieval Units

| Field | Details |
|---|---|
| **Problem** | Numeric and matrix-like fields can be wrong even when the relevant value is present because flattened table text loses header, row, column, and unit relationships. |
| **Direction** | Create additive table-aware retrieval units from parsed table regions, preserving row labels, column headers, units, captions, page, and nearby callouts. These units should supplement normal paragraph/caption chunks rather than replace them. |
| **Why it might work** | Many scientific values are meaningful only in table structure: the same number can refer to different rows, columns, units, or conditions. Preserving those relationships should reduce wrong-value selection. |
| **Evidence so far** | The latest run struggled with max editing efficiency, sequence length, barcode length, and methods parameters; archived notes repeatedly argue that scientific tables need dedicated structure. |
| **Generality risk** | Table parsing varies across papers and fields, so table units must degrade gracefully to raw text. |
| **Runtime/cost risk** | Low to moderate depending on parser cost and table count. |
| **Test** | Compare matched runs with and without table-aware chunks. |
| **Decision criterion** | Improve table/numeric hard columns without reducing aggregate score or adding large runtime. |

### Failure-Driven Prompt Repair

| Field | Details |
|---|---|
| **Problem** | Broad prompt changes are hard to attribute and can hurt unrelated fields. |
| **Direction** | Classify incorrect per-cell proposals by generic failure class before changing prompts, then add narrowly scoped schema-driven guidance for classes such as wrong metadata, missed methods value, missed maximum/best value, confused comparator/control, sequence/barcode/motif/spacer confusion, wrong figure/panel selection, exact identifier shortening, unsupported blank handling, and wrong normalization. |
| **Why it might work** | Targeted prompt changes can address recurring generic mistakes while avoiding large prompt rewrites that alter unrelated behavior. |
| **Evidence so far** | The 2026-05-24 failure analysis identified several recurring classes across benchmarks. |
| **Generality risk** | Prompt examples must not leak benchmark answers or encode field-specific shortcuts. |
| **Runtime/cost risk** | Low if prompt length stays controlled. |
| **Test** | Apply one small prompt patch at a time and compare column difficulty. |
| **Decision criterion** | Improve targeted weak failure classes without lowering aggregate score on other datasets. |

### Stronger Model And Parameter Sweep

| Field | Details |
|---|---|
| **Problem** | Model choice materially changed score, but the highest-scoring app model was much slower. |
| **Direction** | Keep the per-cell architecture and run interpretable model-only comparisons first, then vary retrieval, top-k, prompt settings, and structured-output modes one factor at a time. |
| **Why it might work** | Separating model effects from retrieval and prompt changes makes regressions easier to interpret and avoids attributing gains to the wrong factor. |
| **Evidence so far** | `cand_0005 / qwen/qwen3.6-27b` scored best in the 2026-05-24 app comparison but had the worst runtime among viable app candidates. |
| **Generality risk** | Optimizing for one benchmark suite could hide field-specific weakness. |
| **Runtime/cost risk** | High for larger models. |
| **Test** | Record score, runtime, provider request counts, text/vision calls, score per minute, structured errors, failed structured elapsed time, retries, parse repairs, and failures per 100 cells. |
| **Decision criterion** | Materially improve aggregate score without unacceptable runtime, structured-output fragility, or cost. |

### Cached RetrievalIndex

| Field | Details |
|---|---|
| **Problem** | Repeated per-cell retrieval can spend runtime rebuilding chunks, tokenization, and scoring state that are stable for a parsed PDF. |
| **Direction** | Introduce a per-PDF `RetrievalIndex` built once after parsing, with cached chunks, tokenization, IDF/statistics, typed contextual retrieval text, and optional future embedding slots. |
| **Why it might work** | Retrieval calls can query the index without changing current extraction semantics, and the same structure can support later recall-rescue or hybrid retrieval. |
| **Evidence so far** | Archived architecture notes identify this as a low-risk latency improvement; the latest run reinforces the need to keep runtime stable while improving retrieval. |
| **Generality risk** | Index artifacts must preserve parser-version and schema-independent document state, not benchmark assumptions. |
| **Runtime/cost risk** | Low if snapshot tests preserve retrieval output equivalence. |
| **Test** | Compare retrieval artifact diffs, end-to-end runtime, and score. |
| **Decision criterion** | Reduce or preserve runtime without lowering score. |

## Priority 2: Promising But Needs More Evidence

### Uncertainty-Gated Recovery

| Field | Details |
|---|---|
| **Problem** | Proposals marked `unclear`, blocked, missing evidence, anchor invalid, or low-confidence inferred can still become final scored outputs. |
| **Direction** | Treat these states as targeted recovery signals. Recovery should rerun retrieval with schema-specific query expansion, inspect methods/supplement/table/figure-caption chunks, or ask a stricter value-selection prompt. |
| **Why it might work** | Uncertainty flags already identify cells where the pipeline suspects weak support, so recovery can focus extra work on high-risk outputs instead of all cells. |
| **Evidence so far** | App-only incorrect cells in the latest analysis were often selected from `unclear` or `found` states, which means uncertainty is not being used strongly enough. |
| **Generality risk** | Excessive retries on genuinely absent values; require a schema-relevant candidate before spending another model call. |
| **Runtime/cost risk** | Moderate unless capped per row/paper. |
| **Test** | Measure recovered-correct cells, recovered-wrong cells, added calls, and runtime. |
| **Decision criterion** | Net score gain per added minute beats simply switching to the slower best model. |

### Targeted Vision Fallback

| Field | Details |
|---|---|
| **Problem** | Vision can help figure-derived fields, but broad figure review adds runtime and has not yet proven a stable score win. |
| **Direction** | Keep text extraction first and trigger vision only when text evidence is weak/missing, the field is likely visual, or validation indicates figure evidence is needed. Do not trigger vision merely because retrieval found a caption; batch visual questions by page or figure when multiple cells need the same image. |
| **Why it might work** | The latest hard columns include figure/panel fields, but broad vision use is expensive. A targeted gate can reserve vision for cases where text extraction is likely insufficient. |
| **Evidence so far** | In the 2026-05-24 run, figure-review planning triggered many cells but few attempts were useful; there was no matched no-vision candidate for the same model. |
| **Generality risk** | Visual heuristics may miss nonstandard figures. |
| **Runtime/cost risk** | High without budgets. |
| **Test** | Compare matched vision/no-vision candidates. |
| **Decision criterion** | Accepted vision value changes must improve score enough to justify added runtime. |

### Judge Calibration And Adjudication

| Field | Details |
|---|---|
| **Problem** | Benchmark interpretation is limited when judge disagreement is high or one judge is systematically harsher. |
| **Direction** | Treat internal and external proposals with the same scoring path, including deterministic exact-match fast paths. Compare judge models on a small hand-reviewed calibration set, and add adjudication or tie-break options for dual-judge disagreements. |
| **Why it might work** | Calibration separates true extraction differences from judge noise and makes small score differences more interpretable. |
| **Evidence so far** | All non-gold candidates in the 2026-05-24 model comparison carried `judge_instability_observed`, and judge disagreement affected fine-grained interpretation. |
| **Generality risk** | Adjudication can hide judge weakness if not reported transparently. |
| **Runtime/cost risk** | Extra judge calls can be expensive. |
| **Test** | Record primary score, disagreement rate, adjudicated score, and judge model IDs. |
| **Decision criterion** | Benchmark outcomes become more auditable without obscuring raw judge behavior. |

### Improve Structured Output For Qwen Models

| Field | Details |
|---|---|
| **Problem** | Some Qwen-family and other local-model runs produced malformed JSON or structured-output errors, which increases runtime and can drop proposals. |
| **Direction** | Treat backend-native `json_schema` / `json_object` support as an optional capability, not the reliability baseline. Prefer prompt-only JSON plus client-side validation, bounded repair, raw-output logging, and clear metadata for whether guided output, retry, or repair was used; consider `json_repair` only if current bounded repair cannot handle captured failures. |
| **Why it might work** | Local backends often fail at constrained output even when they can answer in plain chat. Moving reliability to client-side validation and bounded repair keeps proposals from disappearing because of transport or formatting quirks. |
| **Evidence so far** | The 2026-05-24 run recorded structured-output failures for `cand_0005 / qwen/qwen3.6-27b`; archived LM Studio lessons show strict schema/regex-constrained output is brittle across local backends. |
| **Generality risk** | Overly permissive repair may accept corrupted semantic content. |
| **Runtime/cost risk** | Low for local repair, but retries add latency. |
| **Test** | Replay captured malformed outputs. |
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
| **Test** | Measure rendered page count, render time, review/export behavior, and end-to-end runtime. |
| **Decision criterion** | Reduce runtime or disk work without breaking review/export artifacts. |

### Batch-Then-Verify Hybrid

| Field | Details |
|---|---|
| **Problem** | Direct batching reduced call count but hurt correctness. |
| **Direction** | Try batching only as a candidate-value generator, then verify or correct at the per-cell level. A possible mode is `extraction.mode = batch_then_verify`, accepting only high-confidence verified batch outputs and falling back to full per-cell extraction for missing, invalid, or low-confidence cells. |
| **Why it might work** | Batch prompts may cheaply surface candidate values, while per-cell verification can prevent the cross-cell contamination that hurt direct batching. |
| **Evidence so far** | Field-group and paper-batch architectures lost accuracy and did not improve end-to-end runtime, but they were not limited to candidate generation. |
| **Generality risk** | Batch prompts can still bias values across columns or rows. |
| **Runtime/cost risk** | High if verification plus fallback doubles work. |
| **Test** | Measure acceptance rate, verifier rejection rate, fallback rate, score, and runtime. |
| **Decision criterion** | Beat per-cell score-per-minute on the broader benchmark suite. |

## Parking Lot

No parked ideas currently. Add only low-priority or underspecified ideas here, and promote them into a priority section once they have a clear test path.
