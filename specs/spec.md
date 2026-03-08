# Spec: Paper Table Agent (current)

## Product summary

Paper Table Agent is a local-first PDF→table pipeline. It matches PDFs to table rows, proposes values for missing cells with evidence, and lets you review decisions in a minimal Run/Review UI before exporting updates. The pipeline is increasingly structure-aware: it should preserve more document structure upstream, retrieve over contextualized typed chunks, and treat table-like content as first-class input when possible.

## Proposal model behavior (inference-first)

- The extraction model is a proposal model, not a quote-extractor: it can infer values when appropriate.
- Evidence is an anchored rationale: multiple snippets may support a proposal (statement + number + context).
- Evidence strength is graded (strong/weak/none) and is not a hard gate on proposing values.
- When inference is used, the model must return a concise rationale (not chain-of-thought) plus at least one anchored snippet when feasible.
- When proposed_value is non-empty, the model must return at least one evidence_item (strong or weak); missing evidence triggers deterministic backfill.

## Golden path

1. Load a table (CSV/XLSX) + schema and normalize column keys for matching.
2. Parse PDFs into normalized parsed-document artifacts (typed elements + page/token provenance when available) and collect parsing sanity metrics.
3. Extract header metadata (title/authors/year) with strict grounding and repair/fallback.
4. Match PDFs to table rows (deterministic pass, then LLM adjudication in fallback window).
5. Build retrieval indexes from contextualized, typed chunks with stable chunk IDs + indices, including table-aware units when available.
6. Assemble context (whole-text when possible, otherwise memory + retrieval) using schema-aware and chunk-type-aware preferences when available, then extract proposals with ID-based references; validate evidence without suppressing values.
7. Run evidence finder for weak/none evidence to attach quotes, pages, and highlights.
8. Persist proposals + evidence + diagnostics to SQLite.
9. Review decisions (Accept / Accept-with-edit / Reject) with highlighted PDF evidence and deterministic risk cues when proposals need extra scrutiny.
10. Export updated table + audit log.

## Inputs

- **Table**: CSV or XLSX.
- **Schema**: `schema_sheet_name` within the table or a separate CSV/XLSX when `schema_mode=separate`.
- **PDF folder**: directory of PDFs.
- **Config**: `run_config.json` (single source of truth).
- **Audit config**: `audit.use_filled_cells_as_gold` (default on) enables diagnostic extraction of already-filled cells for evaluation.
- **Audit sampling**: `audit.max_cells` defaults to 500 with deterministic sampling (stable hash) when the table is larger.

## Outputs (per run)

Always written (run pipeline):

```
run_config.json
proposals.sqlite
run_report.json
logs/run.log
checkpoints.sqlite
```

Artifacts for parsing/retrieval (written as the pipeline runs):

```
artifacts/parsed/*
artifacts/retrieval_indexes/*
artifacts/ocr/*
artifacts/thumbnails/*
```

Exports (after `paper-table-agent export`):

```
exports/updated_table.xlsx
exports/audit_log.csv
```

Evaluation artifacts (always written at end of run and by `paper-table-agent eval`; includes a status note when no audit cells are available):

```
exports/proposal_eval.json
exports/proposal_eval.md
```

Debug-only outputs (when `output.debug_reports=true`):

```
exports/pdf_row_matches.csv
exports/mapping_report.html
exports/proposals.jsonl
```

Optional when `provider.record_requests=true`:

```
logs/llm_records.jsonl
```

Optional when `provider.record_payloads=true`:

```
logs/llm_payloads.jsonl
```

## Guardrails

- **Locked cells**: non-empty cells are never overwritten.
- **Treat single-space as empty**: configurable via `treat_single_space_as_empty`.
- **Verify mode** (optional): create verify-only items for locked cells instead of overwriting them.
- **Audit mode** (default on, optional to disable): extract already-filled cells as diagnostic proposals with `proposal_kind=audit`, never exported to tables unless explicitly accepted.
- **Evidence discipline**: proposals keep proposed values; evidence validation only annotates flags and `needs_more_evidence`.
- **Evidence finder**: weak/none evidence or invalid highlights trigger a locator pass to search full chunks, page text, and tokens for supporting quotes.
- **Highlight guardrails**: reject too-short/low-signal quotes, overly large page-spanning rectangles, and low-confidence matches; mark highlights failed with reasons instead of showing garbage.
- **Highlight anchoring**: use page+quote spans (start/end) as primary anchors; prefer normalized spans or token-based salvage, and clip quotes to a single-page window before highlight attempts.
- **Evidence quality floor**: quotes that look like headers/footers (e.g., quote_start=0 with header-like patterns or high newline density) or are too short/low-signal are marked weak and retried via evidence finder; proposed values are preserved.
- **Header/footer stripping**: repeated page headers/footers (e.g., DOI/journal/page counters) are removed from page_text and chunk text before retrieval.
- **Retrieval/display text split**: retrieval may use contextualized `retrieval_text`, but quote validation, evidence display, and highlighting must continue using raw or space-preserving text fields.
- **Evidence schema invariants**: every evidence item carries `pdf_id` matching the proposal, has `quote_text`, and includes `anchor_id`/`chunk_id` or a `page`.
- **Unicode/ID normalization**: column and chunk identifiers are normalized to prevent drift.

## Document representation behavior

- PDFs normalize into a common parsed-document contract before retrieval whenever possible, preserving typed elements, reading order, and page provenance.
- Parser backends may vary (current parser path, GROBID-enhanced path, or stronger layout-aware backends), but downstream retrieval/extraction consume one normalized representation.
- Parsed elements should distinguish at least when detectable: title, abstract, section headers, paragraphs, figure captions, table-like regions, and reference-like blocks.
- Retrieval chunks are derived from parsed elements when available and may retain both source text and contextualized retrieval text.
- Table-like regions are first-class parse artifacts when detected; fallback behavior remains page/paragraph-based when structured detection is unavailable.

## Matching behavior

- **Pass 1 (deterministic)**: title similarity + author overlap + year tolerance + DOI bonus when available.
- **Pass 2 (LLM adjudication)**: JSON output with `matched | ambiguous | unmatched`, `row_id`, confidence, and evidence.
- **Fallback window**: if the top candidate is plausible (score ≥ 0.50, or ≥ 0.45 with strong margin), LLM adjudication is attempted before marking unmatched.
- **Duplicates**: keep highest-confidence match, flag others as duplicates.

## Extraction behavior

- Context planner selects a per-PDF mode: **fulltext**, **memory**, or **retrieval**.
- Columns are extracted column-first (or in small related batches) with prompts that include row context, the column definition, and the ContextPlan payload. Default extraction starts with single-column batches and may grow beyond the default when the prompt budget allows.
- Schema hints may bias extraction toward preferred evidence sources or context strategies such as table-first, caption-aware, section-aware, fulltext-favored, or memory-favored behavior.
- Prompt budgeting is structured: prompts always include row context, column definitions, and the ContextPlan payload. If trimming is needed in retrieval mode, trim (a) number of chunks, (b) chunk text length per chunk, (c) number of examples per column, then (d) number of columns by batching so every missing column is still attempted exactly once.
- Each requested column yields a proposal record (including `unclear` or `error` records).
- Value-first extraction: propose a value whenever plausible; evidence quality is metadata.
- Evidence validation annotates:
  - `chunk_pk`/`chunk_id`/`chunk_idx` map to a known chunk in the full chunk table.
  - quote must be a substring of the chunk text (exact or normalized), and quote_text must come from space-preserving text (`text` or `text_raw`), not `text_norm`.
  - status=`found` requires at least one evidence quote containing the proposed value (or normalized equivalent); otherwise downgrade to `inferred` and mark `needs_more_evidence=true`.
  - evidence that fails quality floor checks is downgraded to weak and triggers evidence-finder retries; `found` proposals with weak evidence are downgraded to `inferred`.
- if validation fails: mark `needs_more_evidence` and capture `evidence_validation_errors` without clearing values.
- Proposal evidence uses multi-snippet `evidence_items` (quote_text + source_ref + anchor_id + optional why_it_matters/numeric_value) to support argumentation.
- Models can flag `needs_more_context` to trigger a retry with expanded context chunks.
- Verifier uses only stored `quote_text` fields: for `status=found`, it requires minimal overlap between key terms and quotes (and digit/unit overlap for numeric values); failures downgrade to `inferred` with `needs_more_evidence=true`.
- Final `needs_more_evidence` is derived from the latest validation + verification outputs (supports + strong evidence clears sticky flags unless a hard validation rule applies).
- Evidence finder runs for weak/none evidence or highlight failures using full chunk tables, page text, and tokens to attach quotes, pages, and highlights.
- Evidence backfill: when proposed_value is present but evidence_items empty after extraction/repair, attach a deterministic weak snippet from top retrieval chunks.
- Evidence records store `pdf_id` + `chunk_id`/`chunk_idx` to keep chunk identity unambiguous across PDFs.
- **Audit extraction**: enabled by default; already-filled cells are re-extracted for comparison and tagged `proposal_kind=audit` (never exported).

### Whole-text + paper memory mode (feature-flagged, enabled by default)

- If the document fits the model context budget (~85% of ctx window), pass page-marked full text to the proposal model after applying the trimming ladder (drop References, drop Acknowledgements, trim captions, drop appendix blocks) while preserving element boundaries when available.
- If not, run a map-reduce style “paper memory” step that summarizes anchored notes by page/section with 1–2 verbatim quotes each, then propose values using the memory + targeted retrieval.
- The extraction payload for memory mode includes only anchored notes (quote_text + page), while the summary is stored in artifacts for review and is not quoteable.
- Whole-text and memory payloads may incorporate typed elements such as captions or table summaries when they are relevant to the requested columns.
- Evidence anchors must include an anchor_id or page + quote to enable deterministic highlight mapping.

## Retrieval behavior

- Query expansion and HyDE are used when enabled (always on in max success mode).
- Retrieval may contextualize chunks before indexing by prepending deterministic document context such as title, section, page marker, or chunk type.
- Retrieval caches per (pdf_id, column_batch) and reuses results across column batches.
- Query expansion/HyDE caches are scoped per (pdf_id, column) or (pdf_id, column_batch) and record hit/miss stats.
- Columns flagged metadata-only or not-in-paper (e.g., `metadata_only=true` or `in_paper=false` in the schema) skip HyDE/query expansion.
- Retrieval uses sparse + optional dense embeddings and reranking over contextualized chunk text while keeping raw text for evidence operations.
- Retrieval chunks may be typed (e.g., abstract, section_header, paragraph, figure_caption, table_region, table_cell_summary, reference_block) when parsed structure is available.
- Table-aware retrieval units coexist with paragraph chunks and can be preferred for likely table-derived columns.
- Context assembly expands retrieval with neighbor windows and optional section chunks, then trims by token budgets.
- Query construction drops NaN/empty examples and omits the examples section when none remain.
- If dense or reranker backends fail, the pipeline falls back to TF-IDF and disables reranking with a logged warning.
- Low-quality retrieval triggers a retry with broader query variants and example anchors.
- Deterministic hash embedding/reranker backends are available for offline tests.
- Chunk identity uses `chunk_pk=hash(pdf_id::chunk_id)` so evidence never collides across PDFs.

## Review UX

- **Run tab**: table + PDF folder inputs, Start Run button, run status.

- **Review tab**: select completed run; step through matched rows/columns with proposals or evidence.
- Decisions: **Accept / Accept-with-edit / Reject** with auto-advance.
- Review can prioritize or filter risky proposals using deterministic triage cues derived from evidence quality, retrieval behavior, and highlight status.
- Evidence highlights are shown per evidence item on the PDF page when available; re-locate is available if missing.
- Prev/Next proposal navigation supports skim mode.

## Operational defaults

- UI has no tuning knobs; configuration is driven by `run_config.json`.
- The shipped defaults are quality-first rather than speed-first: guided JSON stays in `auto`, extraction starts with single-column batches, retrieval uses a wider context window, and extraction reserves headroom above baseline retrieval size so retry-on-unclear can actually expand context.
- Quality-first behavior may be exposed through explicit presets or a resolved `max_success_mode` alias, but the effective config written to the run directory remains the source of truth for what actually ran.
- Health checks validate model endpoint reachability and embedding/reranker backends; failures are logged in `run_report.json`.
- LLM capability probes cache structured-output support per model and route between guided JSON and prompt-only JSON.
- Context window sizing prefers model capability probes (cached per base_url/model), with explicit overrides from `provider.max_prompt_tokens` or `provider.ctx_window_tokens_override`.
- Run reports include a summary of per-model capability probe results.
- Compatibility probes validate backend/model support and classify regex/grammar errors as backend incompatibilities with recommended next actions.
- Backends that do not support constrained decoding (e.g., LM Studio + gpt-oss) must run in constraints-off mode with prompt-only JSON (no response_format/json_schema/grammar/regex/pattern fields) across all pipeline stages.
- Optional fallback models can be configured per role (header/match/extract/helper) and are swapped in when probes fail.
- Parsing sanity metrics (text length, tokens, whitespace ratio, sparse pages, OCR trigger) are recorded per PDF.
- CLI entrypoint `paper-table-agent` must install via console scripts and is verified in tests.
- `paper-table-agent ui --smoke` provides a headless import/layout check for CI and non-interactive environments.
- Stub run fixture produces multiple proposed values, evidence, and at least one highlightable bbox.
- Optional LLM record mode stores raw prompt/response pairs under `logs/llm_records.jsonl` for replay debugging.
- Optional LLM payload logging writes exact request JSON under `logs/llm_payloads.jsonl` for provider debugging.
- Prompt budgets trim retrieved chunks before LLM requests to stay within model context limits.
- Run reports include context plan diagnostics (mode, token estimates, memory stats), extraction batch diagnostics (batch counts, columns attempted vs total missing, per-batch chunk presence, prompt trim counts), evidence coverage %, highlight success %, counts of found-but-unanchored downgrades, prompt caps, and per-stage LLM call counts.
- Run reports embed evaluation summaries (audited cell counts, fill-missing counts, overall score, per-column summary, and evidence metrics) after each run.
- Run reports include retrieval cache stats for batch/query/HyDE caching.
- Run reports capture audit/evaluation summaries and LLM metadata (model identifiers + live usage flag) when available.

## Testing & evaluation

- Hermetic tests use stub/mock LLM clients with no network calls.
- Live integration tests are opt-in via `pytest -m live_llm` and only run when `PTA_LIVE_LLM=1` is set.
- Live tests rely on synthetic fixture PDFs generated in-repo for deterministic evidence anchoring.
- Evaluation runs automatically at the end of `paper-table-agent run` and via `paper-table-agent eval`, writing `exports/proposal_eval.json`/`exports/proposal_eval.md` and updating `run_report.json` with metrics. If no audit cells are available, the eval report records a status + note instead of silent all-zero metrics.

## Failure semantics

- If matched PDFs > 0 and proposals == 0, the run report is marked **completed_with_warnings** with “why_no_values” diagnostics.
- Health check failures are surfaced in `run_report.json` and logs; the run is marked failed if they occur.
