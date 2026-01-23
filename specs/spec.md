# Spec: Paper Table Agent (current)

## Product summary

Paper Table Agent is a local-first PDF→table pipeline. It matches PDFs to table rows, proposes values for missing cells with evidence, and lets you review decisions in a minimal Run/Review UI before exporting updates.

## Golden path

1. Load a table (CSV/XLSX) + schema.
2. Parse PDFs and extract header metadata (title/authors/year).
3. Match PDFs to table rows (deterministic pass, then LLM adjudication if needed).
4. Build retrieval index + retrieve evidence chunks.
5. Extract proposals for missing cells and validate evidence.
6. Persist proposals + evidence + diagnostics to SQLite.
7. Review decisions (Accept / Accept-with-edit / Reject).
8. Export updated table + audit log.

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

## Guardrails

- **Locked cells**: non-empty cells are never overwritten.
- **Treat single-space as empty**: configurable via `treat_single_space_as_empty`.
- **Verify mode** (optional): create verify-only items for locked cells instead of overwriting them.
- **Evidence discipline**: proposals without valid evidence are downgraded to `unclear` and marked `needs_more_evidence`.

## Matching behavior

- **Pass 1 (deterministic)**: title similarity + author overlap + year tolerance.
- **Pass 2 (LLM adjudication)**: JSON output with `matched | ambiguous | unmatched`, `row_id`, confidence, and evidence.
- **Duplicates**: keep highest-confidence match, flag others as duplicates.

## Extraction behavior

- Columns are grouped by schema and extracted with prompts that include row context and examples.
- Each requested column yields a proposal record (including `no_evidence` or `error` records).
- Evidence validation enforces:
  - `chunk_id` is present and known.
  - quote must be a substring of the chunk text (exact or normalized).
  - if validation fails: mark `needs_more_evidence` and capture `evidence_validation_errors`.

## Retrieval behavior

- Query expansion and HyDE are used when enabled.
- Retrieval uses sparse + optional dense embeddings and reranking.
- If dense or reranker backends fail, the pipeline falls back to TF-IDF and disables reranking with a logged warning.

## Review UX

- **Run tab**: table + PDF folder inputs, Start Run button, run status.
- **Review tab**: select completed run; step through matched rows/columns with proposals needing decisions.
- Decisions: **Accept / Accept-with-edit / Reject**.

## Operational defaults

- UI has no tuning knobs; configuration is driven by `run_config.json`.
- Health checks validate model endpoint reachability and embedding/reranker backends; failures are logged in `run_report.json`.

## Failure semantics

- If matched PDFs > 0 and proposals == 0, the run report is marked **failed** with diagnostics.
- Health check failures are surfaced in `run_report.json` and logs; the run is marked failed if they occur.
