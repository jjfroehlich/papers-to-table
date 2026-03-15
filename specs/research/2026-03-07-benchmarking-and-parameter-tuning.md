# Paper Table Agent: capability review, improvement levers, and benchmarking plan

## Purpose

This report summarizes what the project currently builds, what capabilities are already implemented, what parts are most likely to improve reliability, and how to use a human-verified XLSX table as a benchmark dataset for parameter selection.

The focus here is reliability of extraction from publications, including hard-to-infer fields where evidence can be incomplete and the model may need to infer from context.

## What this project is building

Paper Table Agent is a local-first pipeline for structured extraction from research papers into a tabular dataset.

At a high level the pipeline is:

1. Load a table and schema.
2. Parse PDFs into page text and retrieval chunks.
3. Extract PDF header metadata and match PDFs to table rows.
4. Retrieve relevant context per field or field batch.
5. Ask an LLM to propose values, rationales, and evidence.
6. Validate and repair evidence anchors.
7. Store proposals in SQLite.
8. Review proposals in a minimal UI.
9. Export accepted results back to XLSX.
10. Evaluate audit proposals against filled cells.

This is not just a quote extractor. The intended behavior is proposal-first extraction: the model is allowed to infer a value when the paper supports it, while evidence quality is tracked separately.

## Current implemented capabilities

### Core product behavior

- Local-first CLI and Streamlit UI.
- XLSX/CSV input with schema support.
- PDF to row matching with deterministic scoring and LLM adjudication fallback.
- Extraction into per-cell proposals with evidence metadata.
- Review workflow with accept, accept-with-edit, reject.
- Export to updated table and audit log.
- Automatic audit/eval artifacts at the end of a run.

### Matching capabilities

- Header extraction from PDF front matter with repair prompts.
- Deterministic candidate shortlist using title similarity, author overlap, year tolerance, and DOI bonus.
- LLM adjudication when deterministic matching is not decisive.
- Duplicate handling and mapping diagnostics.

Key implemented knobs:

- `matching.top_k`
- `matching.confidence_threshold`
- `matching.confidence_margin`
- `matching.fallback_min`
- `matching.fallback_threshold`
- `matching.fallback_margin`
- `matching.year_tolerance`
- `matching.header_max_chars`

### Retrieval capabilities

- Sparse retrieval with optional dense retrieval.
- Optional reranking.
- Query expansion and HyDE.
- Reciprocal rank fusion.
- Neighbor-window expansion.
- Optional section chunk injection.
- Token-based trimming of final context.
- Fallback to TF-IDF/BM25 style behavior when dense or reranking backends fail.
- Query and HyDE caches with stats recorded in the run report.

Key implemented knobs:

- `retrieval.top_k`
- `retrieval.rerank_k`
- `retrieval.max_context_chunks`
- `retrieval.max_context_tokens`
- `retrieval.context_window`
- `retrieval.include_section_chunks`
- `retrieval.section_chunk_limit`
- `retrieval.summary_enabled`
- `retrieval.summary_max_chunks`
- `retrieval.summary_max_tokens`
- `retrieval.query_variants`
- `retrieval.use_query_expansion`
- `retrieval.use_hyde`
- `retrieval.rrf_k`
- `retrieval.use_dense`
- `retrieval.embedding_backend`
- `retrieval.embedding_model`
- `retrieval.use_reranker`
- `retrieval.reranker_backend`
- `retrieval.reranker_model`
- `retrieval.query_cache_max_entries`
- `retrieval.hyde_cache_max_entries`

### Extraction and context-planning capabilities

- Column-first extraction with batching.
- Prompt budget trimming that removes chunks first, then chunk text length, then examples, then splits columns into more batches.
- Context planning with three modes:
  - `fulltext`
  - `memory`
  - `retrieval`
- Whole-text mode if prompt budget and model type allow it.
- Paper-memory mode for larger documents on supported model types.
- Retrieval mode as the fallback.
- Evidence validation without discarding the proposed value.
- Evidence finder pass to recover pages, quotes, and highlights when evidence is weak or missing.

Key implemented knobs:

- `extraction.examples_per_col`
- `extraction.column_batch_size`
- `extraction.max_chunks`
- `extraction.retry_on_unclear`
- `extraction.retry_extra_chunks`
- `extraction.whole_text_enabled`
- `extraction.whole_text_max_tokens`
- `extraction.fulltext_target_ratio`
- `extraction.fulltext_caption_max_chars`
- `extraction.paper_memory_enabled`
- `extraction.paper_memory_max_tokens`
- `extraction.thinking_models`

### Provider and runtime capabilities

- Separate models per role: header, match, extract, query-helper.
- Guided JSON capability routing and compatibility probes.
- Provider-side fallback models if a backend/model is incompatible.
- Prompt char and token caps.
- Optional payload and response recording.
- Context-window probing and override.

Key implemented knobs:

- `provider.model_header`
- `provider.model_match`
- `provider.model_extract`
- `provider.model_query_helper`
- `provider.fallback_enabled`
- `provider.fallback_base_url`
- `provider.fallback_model_header`
- `provider.fallback_model_match`
- `provider.fallback_model_extract`
- `provider.fallback_model_query_helper`
- `provider.max_prompt_chars`
- `provider.max_prompt_tokens`
- `provider.ctx_window_tokens_override`
- `provider.guided_json_mode`
- `provider.timeout_s`
- `provider.read_timeout_s`
- `provider.measure_prompt_tokens`
- `provider.record_requests`
- `provider.record_payloads`

### Parsing / OCR / audit capabilities

- OCR fallback based on parsing health metrics.
- Audit mode that re-extracts already-filled cells as gold comparisons.
- Deterministic sampling of audit cells.
- Per-column numeric tolerance, categorical aliases, and text similarity threshold in evaluation.

Key implemented knobs:

- `ocr.enable_ocr`
- `ocr.ocr_trigger_min_chars_per_page`
- `ocr.whitespace_ratio_min`
- `ocr.avg_token_length_max`
- `audit.use_filled_cells_as_gold`
- `audit.sample_rate`
- `audit.max_cells`
- `audit.columns_allowlist`
- `audit.columns_denylist`
- `audit.numeric_tolerance_by_column`
- `audit.categorical_aliases_by_column`
- `audit.text_similarity_threshold`

## Current strengths

The current system already has most of the ingredients needed for serious benchmarking:

- It preserves run-time config in each run directory.
- It writes run-level diagnostics and evaluation summaries.
- It supports audit-mode extraction on filled cells.
- It supports evidence quality metrics, not just answer matching.
- It records retrieval fallbacks, capability probes, and prompt-budget behavior.
- It allows role-specific model changes rather than treating the whole pipeline as one black box.

That means the project is already beyond a prototype in one important sense: it has a usable experiment surface.

## Current limitations and risks

### 1. Benchmark leakage risk from in-table examples

The current example selection logic draws examples from filled cells in the same table.

That is useful for product performance, but it is risky for benchmark validity. If the same verified table is both:

- the source of few-shot examples, and
- the source of gold labels for evaluation,

then reported scores can be inflated.

For reliable benchmarking, evaluation rows should not contribute examples to prompts for those same rows or closely related rows.

### 2. Current `overall_score` is mostly answer match rate

The current evaluation summary sets `overall_score` equal to match rate. That is a good starting point, but it underweights important dimensions:

- evidence quality
- anchorability/highlight success
- abstention vs hallucination behavior
- per-column difficulty
- latency/cost

For tuning the best setup, a richer score is needed.

### 3. The benchmark currently focuses on audited filled cells

That is useful and practical, but it does not fully capture the product's main use case: filling missing cells. It evaluates re-extraction quality on cells with known answers, not end-to-end gain on unknown cells.

This is still the right foundation, but it should be treated as the main offline benchmark, not the only evidence.

### 4. Parameter surface is broader than the root config example shows

The checked-in `run_config.json` in the repo root does not expose every implemented parameter. The Pydantic config schema supports more options than that file currently shows.

This creates two problems:

- useful knobs may be underused
- experiment reproducibility is weaker if operators assume the root sample is exhaustive

### 5. No dedicated experiment runner yet

The repo has evaluation output, but not yet a formal harness for multi-run parameter sweeps, score aggregation, ranking, and statistical comparison.

This is the main missing piece between "we can evaluate a run" and "we can systematically choose the best setup".

## What is most worth improving

The most important improvements are not all equal. The best order is:

### Priority A: benchmark validity and experiment hygiene

1. Prevent gold leakage from prompt examples.
2. Introduce fixed dev/test splits over rows or papers.
3. Version benchmark datasets and scoring rules.
4. Save experiment manifests that connect run config, git commit, prompt versions, model IDs, and benchmark split.

Without this, parameter tuning will look more certain than it really is.

### Priority B: retrieval quality for difficult fields

For hard-to-infer scientific fields, extraction quality is often bottlenecked by retrieval and context assembly rather than the final extraction prompt.

Highest-value levers are likely:

1. `retrieval.use_query_expansion`
2. `retrieval.use_hyde`
3. `retrieval.top_k`
4. `retrieval.rerank_k`
5. `retrieval.max_context_chunks`
6. `retrieval.max_context_tokens`
7. `retrieval.context_window`
8. `retrieval.include_section_chunks`
9. embedding and reranker model choice

### Priority C: context mode selection and extraction batching

Hard fields often benefit when the model can see broader paper context. The existing `fulltext` and `memory` modes are likely high-impact for reasoning-heavy columns.

Highest-value levers are likely:

1. `extraction.whole_text_enabled`
2. `extraction.paper_memory_enabled`
3. `extraction.fulltext_target_ratio`
4. `extraction.paper_memory_max_tokens`
5. `extraction.column_batch_size`
6. `provider.max_prompt_tokens`
7. `provider.ctx_window_tokens_override`

### Priority D: role-specific model strategy

Different tasks may want different models.

- Matching wants structured and conservative behavior.
- Query expansion wants breadth and paraphrase skill.
- Extraction wants careful reasoning with grounded evidence.

The current architecture already supports separate models for these roles. This should be exploited in experiments.

### Priority E: scoring semantics by column type

The current evaluation already supports per-column numeric tolerance, categorical aliases, and text thresholding. That should be expanded into a benchmark contract per column, because different scientific fields have different acceptable equivalence rules.

## Parameter groups most likely to improve functionality

Below is the practical view: which parameters are likely to matter most, and what effect they probably have.

### 1. Matching parameters

Goal: reduce row-assignment errors, because downstream extraction cannot recover from a bad match.

Most important:

- `matching.confidence_threshold`
- `matching.confidence_margin`
- `matching.fallback_min`
- `matching.fallback_threshold`
- `matching.fallback_margin`
- `matching.year_tolerance`

Expected effect:

- Lower thresholds increase recall but risk wrong row matches.
- Higher thresholds reduce false matches but can produce more unmatched PDFs.
- DOI-aware matching is especially important if the source table includes DOI.

### 2. Retrieval breadth and ranking parameters

Goal: ensure the right evidence reaches the model.

Most important:

- `retrieval.top_k`
- `retrieval.rerank_k`
- `retrieval.max_context_chunks`
- `retrieval.max_context_tokens`
- `retrieval.query_variants`
- `retrieval.use_query_expansion`
- `retrieval.use_hyde`
- `retrieval.use_dense`
- `retrieval.use_reranker`
- embedding and reranker model choice

Expected effect:

- More retrieval breadth helps rare terminology and indirect evidence.
- Too much breadth can dilute the prompt and reduce precision.
- Better reranking often helps more than just increasing `top_k`.

### 3. Context-mode parameters

Goal: improve extraction when the answer depends on distributed evidence across the paper.

Most important:

- `extraction.whole_text_enabled`
- `extraction.whole_text_max_tokens`
- `extraction.fulltext_target_ratio`
- `extraction.paper_memory_enabled`
- `extraction.paper_memory_max_tokens`
- `provider.max_prompt_tokens`
- `provider.ctx_window_tokens_override`

Expected effect:

- Whole-text and memory modes may improve synthesis-heavy columns.
- Retrieval mode may still win for localized facts.
- Best setup may differ by column family.

### 4. Prompt composition parameters

Goal: balance grounding, few-shot support, and context size.

Most important:

- `extraction.examples_per_col`
- `extraction.column_batch_size`
- `extraction.max_chunks`
- `extraction.retry_on_unclear`
- `extraction.retry_extra_chunks`

Expected effect:

- More examples may help consistency, but can leak gold and crowd out context.
- Smaller batch size may improve per-column focus.
- Retry-on-unclear may improve recall but increases cost.

### 5. Provider compatibility and output-structure parameters

Goal: reduce formatting failures and backend incompatibility.

Most important:

- `provider.guided_json_mode`
- `provider.fallback_enabled`
- fallback model assignments by role
- `provider.timeout_s`
- `provider.read_timeout_s`

Expected effect:

- Some backends will perform better with prompt-only JSON.
- Some models will fail less often with structured-output guidance.
- A separate fallback extract model may increase reliability for long or difficult papers.

### 6. OCR and parsing parameters

Goal: rescue low-quality PDFs.

Most important:

- `ocr.enable_ocr`
- `ocr.ocr_trigger_min_chars_per_page`
- `ocr.whitespace_ratio_min`
- `ocr.avg_token_length_max`

Expected effect:

- Better OCR triggering helps scanned or badly encoded papers.
- Over-triggering OCR can slow runs and sometimes worsen clean PDFs.

## How to use a human-verified XLSX table as a benchmark dataset

The project already has the right basic concept: filled cells can act as gold labels via audit mode.

The benchmark should be based on a curated XLSX table where:

- each row corresponds to a paper
- verified values are already filled for selected columns
- schema definitions are clear
- PDFs for those rows are available

### Benchmark dataset design

The benchmark table should distinguish at least three kinds of columns:

1. Easy factual columns
   Examples: species, assay used, publication year if extracted from text, named method.

2. Moderate columns
   Examples: measured outcome, cell type, treatment, experimental setting.

3. Hard inference columns
   Examples: derived interpretation, nuanced eligibility criteria, conclusions that require synthesis across sections, values implied across text and tables.

This is important because a configuration that wins on easy fields may not be best on hard ones.

### Gold-label policy

Each benchmarked column should have a matching rule:

- exact match for stable identifiers
- numeric tolerance for quantitative outputs
- categorical alias sets for synonymous labels
- text similarity thresholds for descriptive fields

The current audit config already supports these mechanisms:

- `numeric_tolerance_by_column`
- `categorical_aliases_by_column`
- `text_similarity_threshold`

That means the existing evaluator can already cover a meaningful first version of the benchmark.

### Preventing benchmark leakage

This is essential.

For benchmark runs, do not let evaluation rows supply in-context examples for their own columns.

Recommended split policy:

1. Partition rows into `dev`, `test`, and optionally `train_examples`.
2. Use only `train_examples` rows as prompt examples.
3. Tune parameters on `dev`.
4. Freeze the best configuration.
5. Report final score once on `test`.

At minimum, if no explicit split is available, set `extraction.examples_per_col=0` during benchmark runs to avoid contamination.

### Benchmark outputs to record for every run

For each run, save:

- full config JSON
- git commit
- prompt versions
- model IDs per role
- benchmark split ID
- `proposal_eval.json`
- `run_report.json`
- runtime and LLM call counts
- evidence metrics

The repo already stores most of this. The missing part is packaging it as a formal experiment result table.

## Recommended scoring framework

The current evaluator is useful, but for parameter selection I would use a composite score with separate reporting dimensions.

### Primary metrics

1. Cell accuracy
   Fraction of audited cells judged correct under column-specific rules.

2. Column-balanced accuracy
   Mean of per-column accuracies, so common columns do not dominate.

3. Hard-column accuracy
   Mean accuracy over a predefined set of difficult columns.

### Evidence metrics

1. Evidence coverage rate
2. Anchorable quote rate
3. Highlight success rate
4. Found-unanchored downgrade count

These already align well with existing artifacts.

### Reliability metrics

1. Missing-answer rate
2. Unclear/error proposal rate
3. Match failure rate at the PDF-to-row stage
4. Run failure / warning rate

### Efficiency metrics

1. Total run time
2. LLM calls by stage
3. Prompt token usage if `provider.measure_prompt_tokens=true`

### Composite ranking score

A reasonable first composite score could be:

$$
S = 0.50 \cdot A_{cell} + 0.20 \cdot A_{hard} + 0.10 \cdot A_{colbal} + 0.10 \cdot E_{coverage} + 0.10 \cdot E_{anchor}
$$

with hard penalties if:

- row matching error rate exceeds a threshold
- run failure rate is non-trivial
- evidence quality collapses while answer accuracy rises

If a simpler rule is preferred, rank primarily by hard-column accuracy, then overall accuracy, then evidence coverage.

## How to try multiple parameter settings and choose the best setup

The practical mistake would be to run a giant unconstrained grid search. The parameter space is too large, and many parameters interact.

Use staged experiments instead.

### Stage 0: establish a stable benchmark baseline

Run one benchmark configuration with:

- fixed benchmark split
- fixed models
- fixed prompt versions
- `audit.use_filled_cells_as_gold=true`
- leakage-safe examples or `examples_per_col=0`

This gives the baseline score and baseline artifacts.

### Stage 1: sweep high-impact retrieval settings

Keep matching and models fixed. Vary retrieval first.

Example experiment block:

1. `use_query_expansion`: on vs off
2. `use_hyde`: on vs off
3. `top_k`: 10, 20, 40
4. `rerank_k`: 10, 20, 40
5. `max_context_tokens`: 1600, 2400, 4000
6. `use_reranker`: on vs off

Select the best retrieval family from benchmark scores.

### Stage 2: sweep context strategy

Using the best retrieval setup, vary:

1. `whole_text_enabled`: on vs off
2. `paper_memory_enabled`: on vs off
3. `fulltext_target_ratio`: 0.70, 0.85
4. `paper_memory_max_tokens`: 800, 1200, 2000
5. `column_batch_size`: 1, 2, 4

This isolates whether hard fields improve from broader paper context.

### Stage 3: sweep extraction prompt composition

Using the best retrieval plus context setup, vary:

1. `examples_per_col`: 0, 1, 3
2. `max_chunks`: 10, 20, 30
3. `retry_on_unclear`: true vs false
4. `retry_extra_chunks`: 5, 10, 20

This is where leakage control matters most.

### Stage 4: sweep model assignments by role

Keep all non-model settings fixed, then vary:

1. extraction model
2. query-helper model
3. match model
4. guided JSON mode
5. fallback model strategy

In practice, extraction and query-helper are likely to matter most.

### Stage 5: optional matching-only sweep

Only do this if row mismatches are materially affecting results.

Vary:

1. `confidence_threshold`
2. `confidence_margin`
3. `fallback_threshold`
4. `year_tolerance`

### Decision rule for choosing the winner

For each stage:

1. Rank by hard-column accuracy.
2. Break ties with overall cell accuracy.
3. Break further ties with evidence coverage and anchorable quote rate.
4. Reject settings that materially increase match errors, run failures, or cost for negligible gain.

Then carry only the top one or two settings into the next stage.

This is much better than a full Cartesian grid.

## Concrete benchmark workflow for this repo

### Minimum viable workflow

1. Curate a benchmark XLSX with verified cells.
2. Add audit matching rules per column.
3. Create a fixed benchmark split.
4. Disable leakage from eval rows into examples.
5. Run `paper-table-agent run --config ...` for each configuration.
6. Collect `exports/proposal_eval.json` and `run_report.json`.
7. Aggregate scores into one comparison table.
8. Select the best dev configuration.
9. Run once on held-out test.

### Strongly recommended additions

1. Add an experiment runner script that accepts a list of config overrides and writes a single summary CSV/JSON.
2. Add a benchmark manifest file with dataset ID, split ID, and scoring rules.
3. Add a benchmark mode that excludes evaluation rows from example selection.
4. Add support for repeated runs where model nondeterminism is high, then report mean and variance.

## Suggested near-term engineering improvements

These are the most useful improvements to implement next.

### High-value product and evaluation improvements

1. Add a benchmark mode with leakage-safe example handling.
   Best version: examples can only come from a named training split or a separate examples table.

2. Add an experiment harness.
   Input: benchmark dataset plus a list of config overrides.
   Output: ranked summary table across runs.

3. Expand `overall_score` into a richer benchmark summary.
   Include balanced accuracy, hard-column accuracy, evidence metrics, and failure rates.

4. Add column difficulty tags in schema.
   This enables reporting accuracy by easy, medium, hard fields.

5. Add a benchmark report artifact.
   A single markdown and CSV report comparing all experiment runs.

### Useful model and retrieval improvements

6. Evaluate stronger reranker choices before increasing prompt size further.
   Better ranking often beats longer context.

7. Treat retrieval and context-mode selection as first-class tuning targets.
   Hard scientific extraction is often constrained by evidence retrieval, not just generation.

8. Consider column-family-specific defaults.
   Some columns may work best with retrieval-only mode, while others benefit from memory or whole-text mode.

### Useful operational improvements

9. Refresh the generated/sample config so all implemented tuning parameters are visible.

10. Record benchmark split identifiers and dataset version in run artifacts.

## Recommended first experiment set

If only a limited amount of tuning time is available, start with these experiments:

### Block 1: retrieval

- Baseline
- `use_query_expansion=false`
- `use_hyde=false`
- `top_k=40, rerank_k=20`
- `max_context_tokens=4000`
- `use_reranker=false`

### Block 2: context strategy

- baseline retrieval winner
- `whole_text_enabled=false`
- `paper_memory_enabled=false`
- `column_batch_size=1`
- `column_batch_size=4`

### Block 3: prompt/examples

- `examples_per_col=0`
- `examples_per_col=1`
- `retry_on_unclear=false`

### Block 4: models

- current model for all roles
- stronger extract model only
- stronger helper model only
- prompt-only JSON vs auto guided JSON

This reduced set will already reveal where most gains are coming from.

## Bottom line

This project already has a strong base for systematic tuning. The most important missing capability is not another extraction trick; it is a leakage-safe benchmark and experiment harness.

The likely best path is:

1. Make benchmarking valid.
2. Tune retrieval and context strategy first.
3. Tune extraction prompt composition second.
4. Tune role-specific model choices third.
5. Choose the winner using hard-column accuracy plus evidence quality, not raw match rate alone.

If this is done carefully, the project should be able to move from "works end-to-end" to "has an evidence-backed best configuration for a known benchmark dataset".