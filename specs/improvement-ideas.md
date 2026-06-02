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
2. Reduce hard-column errors on figure/panel fields, exact architecture strings, numeric maxima, sequence/barcode lengths, barcode presence/location, model-system fields, physical methods parameters, and table-derived values.
3. Keep runtime stable by measuring score-per-minute, structured-output reliability, targeted recovery acceptance rates, and retrieval/indexing overhead.
4. Preserve generality across research fields and unknown schemas; avoid benchmark-specific production logic.

## Priority 1: Next Best Bets

### Candidate Selection And Normalization

| Field | Details |
|---|---|
| **Problem** | Wrong proposals often had plausible evidence but selected the wrong value type, such as a generic figure instead of a panel, a shorthand system name instead of a full architecture, or a spacer length instead of a barcode length. |
| **Direction** | Add a small post-extraction selector that compares candidate values against generic schema semantics before finalizing. Normalize numeric units, figure/panel citations, exact identifiers, count-vs-length distinctions, insert-vs-spacer/barcode lengths, barcode presence/location, absent-feature answers, and model-system-vs-species/genome wording. |
| **Why it might work** | The failure mode is often choosing among plausible candidate values, not complete absence of information. A generic selector can enforce schema semantics without changing the base extraction architecture. |
| **Evidence so far** | The 2026-06-02 comparison confirmed low app accuracy on representative/source figures, architecture, max efficiency, MPRA sequence length, UMI, barcode length/location, model system, and section thickness. Proposal logs show wrong-value selection: spacer length chosen as sequence length, barcode count chosen as barcode length, STARR-seq reporter location chosen as barcode location when no barcode existed, and broad genome/species context chosen as model system. |
| **Generality risk** | Overfitting if keyed to benchmark column names; keep rules driven by field type, units, and schema wording. |
| **Runtime/cost risk** | Low if selector reuses existing candidates. |
| **Test** | Compare hard-column accuracy and aggregate score. |
| **Decision criterion** | Improve hard columns without lowering aggregate score or adding meaningful runtime. |

### Schema-Conditioned Paper Context

| Field | Details |
|---|---|
| **Problem** | Per-cell extraction often missed values that require aggregating scattered information across a paper, while whole-paper batching as the authoritative answer path was previously less accurate. |
| **Direction** | Build a schema-derived candidate census, not a benchmark-derived census. For each paper/schema pair, create a schema-conditioned compressed whole-paper context and/or evidence-backed candidate census. First infer generic column needs from the input schema, such as quantity, identifier, presence/absence, location, figure/table reference, method parameter, named entity, URL/citation, list/set, or best/max/min value; then mine compact paper candidates for only those needs with evidence anchors. Per-cell extraction remains authoritative and may only cite, verify, or reject these candidates. |
| **Why it might work** | External Codex-style outputs were much stronger and faster on synthesis-heavy fields, suggesting that paper-level context helps, but rejected paper-batch results show that final answers still need cell-level verification. A compressed context or census can supply global candidates without giving every cell a long full-paper prompt. |
| **Evidence so far** | In the 2026-06-02 run, external non-gold candidates scored 0.7841-0.8000 versus the best app candidate at 0.6469. The largest external gaps were MPRA sequence length, episomal/genomic status, section thickness, architecture/source figures, DNA extraction/genotyping method, barcode length/location, and links. |
| **Generality risk** | High if candidate categories are hard-coded from benchmarks. Production logic must derive needs from schema text, allowed values, examples, field type, and reusable document structures rather than branch on domain-specific terms; benchmark-specific categories belong only in tests and analysis notes. |
| **Runtime/cost risk** | Low to moderate if the context is deterministic or one compact per-paper/per-schema call that replaces repeated failed recovery calls. High if every cell receives full-paper text. Cache per paper/schema and inject only a small filtered subset per cell. |
| **Test** | Compare three variants: current retrieval-only baseline, existing `whole_document_mode` rescue, and schema-conditioned compressed context/census. Measure candidate hit rate, verified-use rate, rejection rate, hard-column accuracy, aggregate score, added calls, prompt tokens, and runtime. |
| **Decision criterion** | Improve synthesis-heavy hard columns and score-per-minute without lowering unrelated fields or accepting unverified paper-level candidates. |

### Per-Cell Retrieval Improvements

| Field | Details |
|---|---|
| **Problem** | Hard failures often involve missing or weak evidence for methods parameters, exact identifiers, figure/panel fields, and numeric values. |
| **Direction** | Improve retrieval/context assembly for individual cells instead of batching cells together. Add typed contextual chunk text for retrieval, such as page, element type, section path, caption/table markers, table row/column labels, and local heading context, while keeping display text source-preserving for review. Also test score-shape-aware context gating: persist per-chunk retrieval scores, allow empty context when candidates are weak, trim to top-1 when the lead chunk has a large confidence gap, and keep only a small coherent bundle when top scores are close. |
| **Why it might work** | Schema descriptions, field types, allowed values, row context, paper metadata, and schema-aware query expansions can target maxima, figure/panel citations, methods parameters, physical dimensions, sequence/barcode lengths, and exact system names. Score-shape gating may prevent one relevant chunk from being diluted by weak neighbors and may avoid feeding topical but non-answering context into the extraction prompt. |
| **Evidence so far** | The 2026-06-02 proposal logs show retrieval often found topical but non-answering evidence: spacer-length passages for sequence length, barcode-count passages for barcode length, broad Drosophila genome passages for model system, and figure-level evidence when panel-level answers were needed. Retrieval chunk and IDF repeated-work counters were already zero, so the next gain is better context semantics rather than simply rebuilding less. |
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
| **Evidence so far** | The 2026-06-02 run struggled with max editing efficiency, MPRA sequence length, barcode length, section thickness, and methods parameters. External outputs were much stronger on several of these fields, implying that the answer was often present but not represented or selected well by the app context. |
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
| **Evidence so far** | The 2026-06-02 failure analysis identified recurring classes across benchmarks: wrong figure panel granularity, wrong numeric scope, count-vs-length confusion, absent-feature handling, model-system-vs-species/genome confusion, exact architecture shortening, methods-parameter misses, and maximum/best-value selection errors. |
| **Generality risk** | Prompt examples must not leak benchmark answers or encode field-specific shortcuts. |
| **Runtime/cost risk** | Low if prompt length stays controlled. |
| **Test** | Apply one small prompt patch at a time and compare column difficulty. |
| **Decision criterion** | Improve targeted weak failure classes without lowering aggregate score on other datasets. |

### Stronger Model And Parameter Sweep

| Field | Details |
|---|---|
| **Problem** | Model choice materially changed score, but the highest-scoring app model was much slower and still missed core schema-semantic distinctions. |
| **Direction** | Keep the per-cell architecture and run interpretable model-only comparisons first, then vary retrieval, top-k, prompt settings, and structured-output modes one factor at a time. |
| **Why it might work** | Separating model effects from retrieval and prompt changes makes regressions easier to interpret and avoids attributing gains to the wrong factor. |
| **Evidence so far** | `cand_0005 / qwen/qwen3.6-27b` was again the best app candidate in the 2026-06-02 comparison at 0.6469, but took 11496 sec versus `cand_0001 / google/gemma-4-e4b` at 0.5718 and 8061 sec. `cand_0004 / zai-org/glm-4.6v-flash` scored 0.3965 with the most structured errors, so deprioritize it for this workflow unless reliability changes. |
| **Generality risk** | Optimizing for one benchmark suite could hide field-specific weakness. |
| **Runtime/cost risk** | High for larger models. |
| **Test** | Record score, runtime, provider request counts, text/vision calls, score per minute, structured errors, failed structured elapsed time, retries, parse repairs, and failures per 100 cells. |
| **Decision criterion** | Materially improve aggregate score without unacceptable runtime, structured-output fragility, or cost. |

### Cached RetrievalIndex

| Field | Details |
|---|---|
| **Problem** | Repeated per-cell retrieval can spend runtime rebuilding chunks, tokenization, and scoring state that are stable for a parsed PDF, but the remaining retrieval problem is now mostly semantic rather than repeated work. |
| **Direction** | Keep or introduce a per-PDF `RetrievalIndex` built once after parsing, with cached chunks, tokenization, IDF/statistics, typed contextual retrieval text, retrieval scores, score-shape diagnostics, and optional future embedding slots. Treat this as infrastructure for typed retrieval and recovery, not as a standalone score improvement. |
| **Why it might work** | Retrieval calls can query the index without changing current extraction semantics, and the same structure can support later recall-rescue, dynamic top-k, hybrid retrieval, and table-aware retrieval units. |
| **Evidence so far** | The 2026-06-02 app diagnostics reported `chunk_build_repeated_work_count = 0`, `idf_build_repeated_work_count = 0`, and `retrieval_repeated_work_count = 0` for inspected candidates, so basic repeated retrieval construction is already controlled. |
| **Generality risk** | Index artifacts must preserve parser-version and schema-independent document state, not benchmark assumptions. |
| **Runtime/cost risk** | Low if snapshot tests preserve retrieval output equivalence; do not expect a large runtime win unless additional repeated work appears in future counters. |
| **Test** | Compare retrieval artifact diffs, end-to-end runtime, and score. |
| **Decision criterion** | Preserve runtime while enabling typed retrieval, dynamic top-k, recovery, or table-aware retrieval to improve score. |

## Priority 2: Promising But Needs More Evidence

### Uncertainty-Gated Recovery

| Field | Details |
|---|---|
| **Problem** | Proposals marked `unclear`, blocked, missing evidence, anchor invalid, or low-confidence inferred can still become final scored outputs. |
| **Direction** | Treat these states as targeted recovery signals. Recovery should rerun retrieval with schema-specific query expansion, inspect methods/supplement/table/figure-caption chunks, use paper-level candidate inventories when available, or ask a stricter value-selection prompt. Add special handling for absent-feature fields so `unresolved` can be accepted when the schema asks for presence/location and the evidence supports no feature. |
| **Why it might work** | Uncertainty flags already identify cells where the pipeline suspects weak support, so recovery can focus extra work on high-risk outputs instead of all cells. |
| **Evidence so far** | In 2026-06-02 proposal logs, many wrong or unresolved MPRA cells were `recall_rescue_eligible` but skipped because recall rescue was disabled. UMI and barcode-location examples also show that unresolved/no-evidence answers can be correct for absent-feature fields, while other unresolved cells are true misses. |
| **Generality risk** | Excessive retries on genuinely absent values; require a schema-relevant candidate before spending another model call. |
| **Runtime/cost risk** | Moderate unless capped per row/paper. |
| **Test** | Measure recovered-correct cells, recovered-wrong cells, added calls, and runtime. |
| **Decision criterion** | Net score gain per added minute beats simply switching to the slower best model. |

### Targeted Vision Fallback

| Field | Details |
|---|---|
| **Problem** | Vision can help figure-derived fields, but broad figure review adds runtime and has not yet proven a stable score win. |
| **Direction** | Keep text extraction first and trigger vision only when text evidence is weak/missing and the schema requires visual inspection or exact figure/panel selection. Do not trigger vision merely because retrieval found a caption or a field is loosely figure-related; batch visual questions by page or figure when multiple cells need the same image. Require vision outputs to preserve panel-level specificity when the schema asks for a panel. |
| **Why it might work** | The latest hard columns include figure/panel fields, but broad vision use is expensive. A targeted gate can reserve vision for cases where text extraction is likely insufficient. |
| **Evidence so far** | In the 2026-06-02 app diagnostics, figure review was triggered 26-60 cells per candidate, attempted only 0-6, and found 0-2 useful cells. Proposal logs show figure review often selected figure-level answers such as `Fig. 7` when the gold required a panel such as `Fig. 7d`. There was still no matched no-vision control, so this rejects broad triggering but not targeted vision. |
| **Generality risk** | Visual heuristics may miss nonstandard figures. |
| **Runtime/cost risk** | High without budgets. |
| **Test** | Compare matched vision/no-vision candidates. |
| **Decision criterion** | Accepted vision value changes must improve score enough to justify added runtime. |

### Judge Calibration And Adjudication

| Field | Details |
|---|---|
| **Problem** | Benchmark interpretation is limited when judge disagreement is high or one judge is systematically harsher. |
| **Direction** | Treat internal and external proposals with the same scoring path, keeping text exact-match fast paths opt-in for calibration rather than default scoring. Compare judge models on a small hand-reviewed calibration set, and add adjudication or tie-break options for dual-judge disagreements. |
| **Why it might work** | Calibration separates true extraction differences from judge noise and makes small score differences more interpretable. |
| **Evidence so far** | All non-gold candidates in the 2026-06-02 comparison carried `judge_instability_observed`. External non-gold candidates had judge disagreement rates around 0.20-0.35, and app candidates around 0.25-0.37 in inspected diagnostics, so small score differences remain hard to interpret. |
| **Generality risk** | Adjudication can hide judge weakness if not reported transparently. |
| **Runtime/cost risk** | Extra judge calls can be expensive. |
| **Test** | Record primary score, disagreement rate, adjudicated score, and judge model IDs. |
| **Decision criterion** | Benchmark outcomes become more auditable without obscuring raw judge behavior. |

### Improve Structured Output For Qwen Models

| Field | Details |
|---|---|
| **Problem** | Some Qwen-family and other local-model runs produced malformed JSON or structured-output errors, which increases runtime and can drop proposals. |
| **Direction** | Treat backend-native `json_schema` / `json_object` support as an optional capability, not the reliability baseline. Prefer prompt-only JSON plus client-side validation, bounded repair, raw-output logging, and clear metadata for whether guided output, retry, or repair was used; consider `json_repair` only if current bounded repair cannot handle captured failures. Gate model candidates on structured-output reliability before expensive full sweeps. |
| **Why it might work** | Local backends often fail at constrained output even when they can answer in plain chat. Moving reliability to client-side validation and bounded repair keeps proposals from disappearing because of transport or formatting quirks. |
| **Evidence so far** | The 2026-06-02 run recorded structured-output errors for `cand_0005 / qwen/qwen3.6-27b` (1), `cand_0003 / mistralai/ministral-3-14b-reasoning` (1), `cand_0002 / openai/gpt-oss-20b` (2), and `cand_0004 / zai-org/glm-4.6v-flash` (5). GLM also spent about 131 sec in failed structured calls and scored worst, while Gemma had zero structured errors but lower correctness. |
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
| **Evidence so far** | Field-group and paper-batch architectures lost accuracy and did not improve end-to-end runtime, but they were not limited to candidate generation. The 2026-06-02 external-result gap suggests paper-level candidate gathering is valuable; test [Schema-Conditioned Paper Context](#schema-conditioned-paper-context) first because it is a narrower advisory version of this idea. |
| **Generality risk** | Batch prompts can still bias values across columns or rows. |
| **Runtime/cost risk** | High if verification plus fallback doubles work. |
| **Test** | Measure acceptance rate, verifier rejection rate, fallback rate, score, and runtime. |
| **Decision criterion** | Beat per-cell score-per-minute on the broader benchmark suite. |

## Parking Lot

No parked ideas currently. Add only low-priority or underspecified ideas here, and promote them into a priority section once they have a clear test path.
