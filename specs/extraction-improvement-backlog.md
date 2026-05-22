# Extraction Improvement Backlog

This file is for extraction ideas that have not been tested yet. It is guidance and memory, not a full implementation plan.

Use `specs/extraction-experiment-results.md` for completed experiments, benchmark outcomes, and rejected ideas. Once an idea here is implemented, benchmarked, dev-checked, or ruled out conceptually, move it to the results file with the evidence and decision.

## How To Use This File

- Keep ideas short and implementation-oriented.
- Avoid benchmark-specific production logic.
- Let the implementing assistant make the detailed plan before coding.
- Record success criteria only when they matter for deciding whether to keep the idea.

## Current Baseline

Use `main` at `6efabd7` as the current default architecture unless a later results entry supersedes it. The grouped extraction branches are preserved for reference but are not recommended defaults.

## Untested Or Not-Yet-Resolved Ideas

### Stronger Model And Parameter Sweep

- Keep the per-cell architecture and compare more capable models first.
- Start with model-only candidates so model effects are interpretable.
- Then vary retrieval/top-k/prompt settings one factor at a time.
- Record score, runtime, provider request counts, text/vision calls, and score per minute.
- Success criterion: materially improve the three-benchmark aggregate score without unacceptable runtime or cost.

### Per-Cell Retrieval Improvements

- Improve retrieval/context assembly for individual cells instead of batching cells together.
- Use schema descriptions, field types, allowed values, row context, and paper metadata as general retrieval signals.
- Prefer additive reranking over hard filters so unusual publications still have fallback evidence.
- Add diagnostics showing which evidence source was selected for each proposal.
- Success criterion: improve or preserve per-cell baseline score on the broader benchmark comparison.

### Advisory Schema Planning

- Revisit schema planning as advisory metadata, not as authoritative routing or batching.
- Possible config: `extraction.column_planning.mode = disabled | advisory_deterministic | advisory_llm`.
- Store planner output as an artifact such as `planning/column_plan.json`.
- Planner may annotate likely evidence sources, visual need, blank policy, confidence, and rationale.
- Guardrail: extraction must not discard evidence only because the plan says it is less relevant.

### Targeted Vision Fallback

- Keep text extraction as the first pass.
- Trigger vision only when text evidence is weak/missing, the field is likely visual, or validation indicates figure evidence is needed.
- Do not trigger vision merely because retrieval found a caption.
- Batch visual questions by page or figure when multiple cells need the same image.
- Record why vision was triggered and whether it helped.

### Lazy Page Rendering

- Preserve `parser.page_render_policy = eager | lazy`.
- In lazy mode, parse text/tables/metadata first and render page images only for vision, review UI, or exports that need them.
- Cache rendered pages by PDF/page/render settings.
- Track rendered page count and render time.
- Guardrail: do not break existing review/export artifact behavior.

### Batch-Then-Verify Hybrid

- Try batching only as a candidate-value generator, then verify or correct at the per-cell level.
- Possible mode: `extraction.mode = batch_then_verify`.
- Accept only high-confidence verified batch outputs.
- Fall back to full per-cell extraction for missing, invalid, or low-confidence cells.
- Record batch acceptance rate, verifier rejection rate, fallback rate, score, and runtime.

### Failure-Driven Prompt Repair

- Analyze incorrect per-cell proposals by generic failure class before changing prompts.
- Candidate classes: wrong metadata, missed methods value, missed result number, confused comparator/control, unsupported blank handling, wrong normalization.
- Add only generic schema-driven prompt guidance, not benchmark-answer examples.
- Keep changes small enough that benchmark effects can be attributed.
- Success criterion: improve weak failure classes without hurting other benchmark datasets.

## Idea Entry Template

```markdown
### Idea Name

- Short implementation direction:
- Generality risk:
- How to test:
- Decision criterion:
```
