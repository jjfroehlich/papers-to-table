# Extraction Workflow

## Purpose

This kit is for agent-native extraction from research publications, scientific PDFs, and technical documents followed by standardized review handoff. The agent decides how to read documents and propose values. The kit scripts validate and normalize the handoff for human review, decisions, and export.

The kit gives light extraction discipline, not a complete extraction engine. It helps agents keep the work schema-first, row-aware, evidence-backed, and inspectable.

## Hard Gate For CSV Requests

CSV filenames, `_filled.csv`, `completed_table.csv`, or instructions such as `Return one completed CSV` do not mean CSV-only. A request for CSV outputs is not a CSV-only request. Treat CSV outputs as draft convenience artifacts unless the user explicitly says "CSV only", "skip review", "do not build the review UI", or equivalent.

Before extracting any value, scaffold a run directory and create `review_input.json`. Every non-empty proposal must be written with structured evidence at authoring time, not reconstructed after filling a CSV. The task is incomplete until `build_and_serve_review.py` has produced the required review artifacts and either started the localhost review UI or returned an exact `serve_review.py` command.

## Default Flow

1. Treat the formal review package as the default deliverable.
2. If a schema exists, follow it. If not, draft a lightweight column plan before extraction.
3. Extract values row-by-row and cell-by-cell, preserving structured evidence as each non-empty value is authored.
4. Write only `review_input.json`, `pdfs/`, and optional `source_table.csv` or `schema.json`.
5. Run `build_and_serve_review.py --run RUN_DIR` to validate, build, validate generated artifacts, and start localhost review.
6. If the review server cannot be kept running, run `build_and_serve_review.py --run RUN_DIR --build-only --json` and report the exact serve command.

Do not stop at `_filled.csv` or `completed_table.csv` outputs unless the user explicitly requested CSV-only extraction. A request for CSV outputs is not a CSV-only request. Treat the task as CSV-only only when the user says "CSV only", "skip review", "do not build the review UI", or equivalent. A filled CSV is a secondary draft; formal review and accepted-only export start from `review_input.json`.

## Benchmark/Table Workflow

For benchmark folders, literature-review matrices, or table-completion tasks:

Evidence-first loop:

1. Scaffold each dataset run.
2. Append each target-cell proposal directly into `review_input.json` with evidence.
3. Optionally maintain a draft `_filled.csv`.
4. Run validation and build with `build_and_serve_review.py`.
5. Start the review UI or return the exact `serve_review.py` command.

1. Create one `RUN_DIR` for the extraction handoff.
2. Copy source PDFs into `RUN_DIR/pdfs/`.
3. Copy the empty table/template to `RUN_DIR/source_table.csv`.
4. Copy the task schema to `RUN_DIR/schema.json` or `RUN_DIR/schema.csv` when available.
5. Map schema target columns into `review_input.json.columns`.
6. Map template rows into `review_input.json.rows`, preserving `row_id`, `row_index`, `pdf_id`, paper title, and any existing metadata.
7. Author one proposal per supported target cell in `review_input.json.proposals`.
8. Optionally write a draft `_filled.csv` with the same headers as the template, but keep it secondary to the review package.

Every proposal should reference the relevant `row_id`, `column_name`, `proposed_value`, and structured evidence. Leave unsupported cells out of `proposals`, or use `proposal_status="no_data"` only when the paper explicitly indicates absence.

For benchmark folders with a standard template/schema/PDF layout, prefer the scaffold script before extraction:

```bash
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --run RUN_DIR
```

The scaffolded package is intentionally incomplete until proposals are added, but it prevents agents from losing row, schema, and PDF mappings.

## Extraction Guidance

Use the schema first. Respect allowed values, null policy, column descriptions, units, and formatting guidance. Do not guess.

Use row-aware extraction. Resolve the paper/document and row identity before filling target cells, and do not let evidence from one source support another row.

Use table-, caption-, and figure-aware reading. Many values are reported in tables, captions, figure labels, methods details, supplement references, or result prose. Capture the strongest available support as direct quotes, table snippets, caption text, page numbers, and source locations.

Prefer concise proposed values that match the schema. Preserve direct quotes and page numbers where possible. Use reasoning-only evidence only when exact text cannot be captured.

When the broader task benefits from synthesis, the reviewed or clearly labeled draft table can be reused in a research report. Keep report prose separate from the review package, and make the review status of table values clear.

## Authoring Workspace

External agents author this simple layout:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # optional
  schema.json       # optional
```

Generated directories such as `normalized/`, `summaries/`, `review/`, `exports/`, and compatibility outputs are script-owned. Do not create them by hand.

## Column Planning

Use only what the task needs. A compact column definition can be:

```json
{
  "column_name": "Main finding",
  "description": "One concise statement of the paper's main empirical finding.",
  "field_type": "text"
}
```

More detail such as allowed values, null policy, evidence requirements, and formatting guidance is useful when the user asks for high consistency or review/export.

## Evidence Authoring

Every non-empty `proposed_value` needs at least one structured evidence object in `review_input.json`.

Preferred direct evidence:

```json
{
  "pdf_id": "paper_a",
  "source_type": "direct_quote",
  "page_number": 3,
  "quote_text": "Exact supporting sentence from the PDF."
}
```

Table, caption, and generic evidence text are also valid:

```json
{
  "pdf_id": "paper_a",
  "page_number": 5,
  "source_type": "table_text",
  "table_text": "Reported value in Table 2."
}
```

Weak but reviewable evidence is allowed when the agent cannot provide exact text:

```json
{
  "pdf_id": "paper_a",
  "page_number": 7,
  "source_location": "Results",
  "reasoning": "The page context implies the value, but no exact quote was captured."
}
```

The UI labels weak evidence visibly. Non-empty proposed values with no structured Tier A/B/C evidence are invalid.

Do not keep evidence only in scratch notes. Convert the supporting quote, table snippet, caption text, figure reference, page number, or reasoning into the proposal evidence object while the value is authored.

## Draft CSVs and Review Status

For benchmark tasks, producing a draft CSV is useful but secondary:

- `draft_completed_table.csv`, `_filled.csv`, or `completed_table.csv`: agent-extracted draft values, not human-reviewed
- `review_input.json` plus generated review files: evidence-backed review package
- `exports/final_table.csv`: accepted-only table after human review or explicit `--accept-all`

Do not imply that a draft CSV is reviewed. Label it as draft, agent-extracted, or unreviewed unless decisions have been applied.

## Final Artifact Gate

Before final response, verify that the review package exists unless the user explicitly requested CSV-only extraction:

- `RUN_DIR/review_input.json`
- `RUN_DIR/normalized/proposals.jsonl`
- `RUN_DIR/normalized/evidence.jsonl`
- `RUN_DIR/summaries/validation_report.json`
- `RUN_DIR/review/index.html`
- `review_url` or exact `serve_review.py` command

If any required artifact is missing, do not call the task complete. Create it or report the blocker.

## Coverage

Sparse extraction is acceptable when it is explicit. Leave unproposed cells out of `proposals`, or use `proposal_status="no_data"` when the paper explicitly does not report a requested value.

Formal exports include only accepted and accepted-with-edit decisions. Draft/report values that have not been reviewed must be labeled as draft, agent-extracted, or auto-accepted as appropriate.
