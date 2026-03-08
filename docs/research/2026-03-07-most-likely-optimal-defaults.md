# Most Likely Optimal Defaults For Paper Table Agent

## Goal

This note argues, without running new benchmarks, which settings are most likely to be best for overall extraction quality in this project, and which changes were applied to the codebase as the new shipped defaults.

The objective here is not benchmark purity. It is best expected app performance on real extraction tasks.

## Ranking of levers by strongest expected impact

This ranking is strict first by likely impact on end-to-end extraction quality, then by how confident the adjustment is without new experiments.

### 1. Give the extractor better context, not just more model calls

Most likely best adjustments:

- raise retrieval context budget
- widen neighbor context
- preserve section-level context
- leave query expansion and HyDE enabled

Why this ranks first:

- Hard scientific fields usually fail because the right evidence never reaches the model, or arrives fragmented.
- This codebase already has strong evidence repair logic, so feeding it more relevant context is likely to pay off immediately.
- The existing `max_success_mode` already assumes retrieval breadth is usually worth it.

Changes applied:

- `retrieval.top_k = 24`
- `retrieval.rerank_k = 24`
- `retrieval.max_context_tokens = 3200`
- `retrieval.context_window = 2`
- `retrieval.section_chunk_limit = 8`
- `retrieval.summary_max_chunks = 16`
- `retrieval.summary_max_tokens = 1400`

### 2. Reserve actual retry headroom instead of pretending to

Most likely best adjustments:

- raise `extraction.max_chunks`
- keep retry enabled
- make `retry_extra_chunks` large enough to matter

Why this ranks second:

- In the previous defaults, `retry_extra_chunks` had little or no practical effect in quality-first runs because `extraction.max_chunks` capped the baseline context too tightly.
- The app already has retry logic for unclear or weak-evidence proposals, so making that retry materially expand context is a direct quality win.

Changes applied:

- `extraction.max_chunks = 32`
- `extraction.retry_extra_chunks = 8`

This creates real expansion room above the baseline retrieval context.

### 3. Start extraction one column at a time

Most likely best adjustment:

- `extraction.column_batch_size = 1`

Why this ranks third:

- Cross-column batching can save time, but it also invites prompt dilution and field interference.
- The planner can already grow batching when prompt budget permits, so starting at one column is the safer quality-first default.
- The live LLM smoke test in this repo already uses this shape.

Changes applied:

- `extraction.column_batch_size = 1`

### 4. Keep whole-text and paper-memory modes enabled, and raise their useful limits

Most likely best adjustments:

- keep `whole_text_enabled = true`
- keep `paper_memory_enabled = true`
- raise fulltext and paper-memory token ceilings

Why this ranks fourth:

- Difficult extractions often depend on dispersed evidence across multiple sections.
- This repo already invested in context planning, anchored memory notes, and prompt-budget safeguards.
- The default budgets were likely conservative for best-quality operation.

Changes applied:

- `extraction.whole_text_max_tokens = 8000`
- `extraction.paper_memory_max_tokens = 2400`

### 5. Use one example per column, not several

Most likely best adjustment:

- `extraction.examples_per_col = 1`

Why this ranks fifth:

- Examples help style and disambiguation, but too many examples crowd out evidence context and can over-steer retrieval queries.
- In this repo, the extraction path already tends to cap prompt examples to one. Aligning the default with that real behavior reduces confusion and makes the retrieval query less noisy.

Changes applied:

- `extraction.examples_per_col = 1`

### 6. Keep guided JSON on auto, not forced off

Most likely best adjustment:

- `provider.guided_json_mode = auto`

Why this ranks sixth:

- Structured outputs reduce parsing failures when supported.
- This codebase already has backend probes and automatic fallback for incompatible endpoints.
- Forcing prompt-only JSON globally leaves quality on the table for compatible models.

Changes applied:

- checked-in `run_config.json` now uses `guided_json_mode = auto`

### 7. Expose the real quality-first defaults in the repo config

Most likely best adjustment:

- make the checked-in `run_config.json` reflect the actual intended best-quality setup

Why this ranks seventh:

- Operators usually start from the repo config file.
- If that file is much narrower than the real intended defaults, the app will underperform in ordinary use even if the code supports better settings.

Changes applied:

- expanded `run_config.json` to surface the relevant quality-first settings explicitly

## Settings intentionally not changed

### Matching thresholds

I did not aggressively retune `matching.confidence_threshold`, `fallback_threshold`, or `fallback_margin`.

Reason:

- Matching errors are catastrophic, and threshold tuning is high-impact but high-risk without data.
- Retrieval and context defaults are safer quality improvements to change blindly.

### OCR thresholds

I left OCR thresholds unchanged.

Reason:

- OCR triggering is data-distribution-sensitive.
- Over-triggering OCR can hurt clean PDFs.

### Audit scoring thresholds

I left benchmark-related thresholds unchanged.

Reason:

- They govern evaluation semantics more than app extraction quality.

## Files changed to implement this position

- `paper_table_agent/config.py`
- `run_config.json`
- `README.md`
- `CHANGELOG.md`
- `specs/spec.md`
- `specs/plan.md`
- `specs/tasks.md`
- `tests/test_config.py`

## Outstanding improvements still worth doing

### 1. Add a benchmark harness

The app can evaluate one run, but it still lacks a first-class multi-run comparison harness.

### 2. Add leakage-safe benchmark mode

The same verified XLSX should not supply prompt examples for the rows being evaluated.

### 3. Make `max_success_mode` govern a full quality preset

Today it mostly strengthens retrieval. If desired, it could also enforce the same quality-first extraction defaults directly.

### 4. Learn per-column or per-group defaults

The true optimum may differ by field family. Some columns may prefer retrieval-only mode, while others benefit from whole-text or memory mode.

### 5. Improve experiment reporting

The current evaluator is useful, but a stronger ranking metric should separate:

- overall accuracy
- hard-column accuracy
- evidence quality
- failure rates
- latency/cost

## Bottom line

The most likely best global default is a quality-first configuration that spends more of the prompt budget on better context, starts extraction one column at a time, and ensures retry logic can genuinely widen context when the first pass is weak.

That is what was implemented here.