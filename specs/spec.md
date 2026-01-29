# Spec: Paper Table Agent (current)

## Product summary

Paper Table Agent is a local-first PDF→table pipeline. It matches PDFs to table rows, proposes values for missing cells with evidence, and lets you review decisions in a minimal Run/Review UI before exporting updates.

## Golden path

1. Load a table (CSV/XLSX) + schema and normalize column keys for matching.
2. Parse PDFs into text + tokens; collect parsing sanity metrics.
3. Extract header metadata (title/authors/year) with strict grounding and repair/fallback.
4. Match PDFs to table rows (deterministic pass, then LLM adjudication in fallback window).
5. Build retrieval index + retrieve evidence chunks with stable chunk IDs + indices.
6. Extract proposals with ID-based references (col_id + chunk_idx + chunk_pk); validate evidence without suppressing values.
7. Run evidence finder for weak/none evidence to attach quotes, pages, and highlights.
8. Persist proposals + evidence + diagnostics to SQLite.
9. Review decisions (Accept / Accept-with-edit / Reject) with highlighted PDF evidence.
10. Export updated table + audit log.

## Inputs

- **Table**: CSV or XLSX.
- **Schema**: `schema_sheet_name` within the table or a separate CSV/XLSX when `schema_mode=separate`.
- **PDF folder**: directory of PDFs.
- **Config**: `run_config.json` (single source of truth).

## Outputs (per run)

Always written:

```
run_config.json
proposals.sqlite
run_report.json
logs/run.log
checkpoints.sqlite
exports/updated_table.xlsx
exports/audit_log.csv
```

Artifacts for parsing/retrieval (written as the pipeline runs):

```
artifacts/parsed/*
artifacts/retrieval_indexes/*
artifacts/ocr/*
artifacts/thumbnails/*
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
- **Evidence discipline**: proposals keep proposed values; evidence validation only annotates flags and `needs_more_evidence`.
- **Evidence finder**: weak/none evidence triggers a locator pass to search full chunks, page text, and tokens for supporting quotes.
- **Unicode/ID normalization**: column and chunk identifiers are normalized to prevent drift.

## Matching behavior

- **Pass 1 (deterministic)**: title similarity + author overlap + year tolerance + DOI bonus when available.
- **Pass 2 (LLM adjudication)**: JSON output with `matched | ambiguous | unmatched`, `row_id`, confidence, and evidence.
- **Fallback window**: if the top candidate is plausible (score ≥ 0.50, or ≥ 0.45 with strong margin), LLM adjudication is attempted before marking unmatched.
- **Duplicates**: keep highest-confidence match, flag others as duplicates.

## Extraction behavior

- Columns are grouped by schema and extracted with prompts that include row context, examples, and column IDs.
- Each requested column yields a proposal record (including `unclear` or `error` records).
- Value-first extraction: propose a value whenever plausible; evidence quality is metadata.
- Evidence validation annotates:
  - `chunk_pk`/`chunk_id`/`chunk_idx` map to a known chunk in the full chunk table.
  - quote must be a substring of the chunk text (exact or normalized).
  - if validation fails: mark `needs_more_evidence` and capture `evidence_validation_errors` without clearing values.
- Evidence finder runs for weak/none evidence using full chunk tables, page text, and tokens to attach quotes, pages, and highlights.

## Retrieval behavior

- Query expansion and HyDE are used when enabled (always on in max success mode).
- Retrieval uses sparse + optional dense embeddings and reranking.
- Query construction drops NaN/empty examples and omits the examples section when none remain.
- If dense or reranker backends fail, the pipeline falls back to TF-IDF and disables reranking with a logged warning.
- Low-quality retrieval triggers a retry with broader query variants and example anchors.
- Deterministic hash embedding/reranker backends are available for offline tests.

## Review UX

- **Run tab**: table + PDF folder inputs, Start Run button, run status.

- **Review tab**: select completed run; step through matched rows/columns with proposals or evidence.
- Decisions: **Accept / Accept-with-edit / Reject** with auto-advance.
- Evidence highlights are shown on the PDF page when available; re-locate is available if missing.
- Prev/Next proposal navigation supports skim mode.

## Operational defaults

- UI has no tuning knobs; configuration is driven by `run_config.json`.
- Health checks validate model endpoint reachability and embedding/reranker backends; failures are logged in `run_report.json`.
- Parsing sanity metrics (text length, tokens, whitespace ratio, sparse pages, OCR trigger) are recorded per PDF.
- CLI entrypoint `paper-table-agent` must install via console scripts and is verified in tests.
- `paper-table-agent ui --smoke` provides a headless import/layout check for CI and non-interactive environments.
- Stub run fixture produces multiple proposed values, evidence, and at least one highlightable bbox.
- Optional LLM record mode stores raw prompt/response pairs under `logs/llm_records.jsonl` for replay debugging.
- Optional LLM payload logging writes exact request JSON under `logs/llm_payloads.jsonl` for provider debugging.
- Prompt budgets trim retrieved chunks before LLM requests to stay within model context limits.

## Failure semantics

- If matched PDFs > 0 and proposals == 0, the run report is marked **completed_with_warnings** with “why_no_values” diagnostics.
- Health check failures are surfaced in `run_report.json` and logs; the run is marked failed if they occur.
