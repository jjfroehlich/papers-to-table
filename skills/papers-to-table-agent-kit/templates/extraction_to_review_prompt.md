# Evidence-First Research Document Extraction Prompt

You are extracting structured information from research publications, scientific PDFs, or technical documents into a papers-to-table run.

Input folder:
`<INPUT_FOLDER>`

Create one run folder:
`<RUN_DIR>`

Use the local agent kit:
`skills/papers-to-table-agent-kit/`

## Required Deliverable

Produce a lean extraction output by default:

```text
RUN_DIR/
  <requested_or_dataset>_filled.csv
  extraction/
    review_input.json
    proposals.jsonl
    evidence.jsonl
    validation_report.json
    extraction_summary.json
```

Do not copy source PDFs, source tables, or schema files into `RUN_DIR`. Store absolute or explicitly resolvable paths in `extraction/review_input.json`.

CSV filenames, `_filled.csv`, `completed_table.csv`, or instructions such as `Return one completed CSV` do not mean evidence-free CSV-only extraction. The filled CSV must be backed by `extraction/review_input.json`, `proposals.jsonl`, and `evidence.jsonl` unless the user explicitly says CSV-only or skip evidence.

## Authoring

Before extracting any value, create `extraction/review_input.json` with:

- `schema_version`
- `run_id`
- `output_table_name`
- `source_table_path` when a table template exists
- `schema_path` when a schema exists
- `pdfs` with source PDF paths
- `columns`
- `rows`
- an initially empty `proposals` array

Every non-empty proposal must be written with structured evidence at authoring time and should include concise proposal-level `rationale`.

## Extraction Rules

- Preserve original row order and row identifiers.
- Preserve all original columns in the root filled CSV.
- Fill only supported target value columns.
- Do not guess values that are not supported by the PDFs.
- Use schema allowed values when provided.
- Leave unavailable values blank in the filled CSV unless a supported no-data proposal should be recorded.
- Use `proposal_status="no_data"` only when the paper explicitly indicates absence.
- Keep per-cell proposals row-aware: evidence from one paper must not support another row.
- Capture table, caption, figure, methods, supplement, and result-prose evidence when relevant.
- Add proposal-level `rationale` for every value-bearing proposal; it is mandatory for interpretation, normalization to schema labels, calculation, weak/inferred evidence, or no-data conclusions.

## Evidence Requirements

Every non-empty proposed value in `review_input.json.proposals` must include structured evidence at extraction time.

Preferred direct evidence:

```json
{
  "pdf_id": "paper_a",
  "source_type": "direct_quote",
  "page_number": 3,
  "quote_text": "Exact supporting sentence from the PDF."
}
```

Table, caption, figure-caption, and generic evidence text are also acceptable when they directly support the value. If exact text cannot be captured, include `pdf_id`, `page_number`, `source_location`, and concise reasoning.

Keep `rationale` separate from evidence text: evidence fields preserve source support, while `rationale` briefly explains the extraction judgment for the reviewer.

## Build

After authoring `extraction/review_input.json`, run:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR --json
```

Then verify:

- `RUN_DIR/<requested_or_dataset>_filled.csv`
- `RUN_DIR/extraction/proposals.jsonl`
- `RUN_DIR/extraction/evidence.jsonl`
- `RUN_DIR/extraction/validation_report.json`
- `RUN_DIR/extraction/extraction_summary.json`

## Optional Human Review

After the filled CSV and extraction provenance are complete, ask exactly:

```text
Do you want to review the results in the browser interface?
```

Only if the user says yes, build and serve review:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR --no-open
```

Human review artifacts live in:

```text
RUN_DIR/
  <requested_or_dataset>_reviewed.csv
  human_review/
    index.html
    assets/
    review_package.json
    decisions.jsonl
    reviewer_summary.json
    audit_log_*.json
    diagnostics_*.json
```

PDF rendering and quote highlights require localhost serving because source PDFs are referenced, not copied. Static `human_review/index.html` can still show proposal and evidence text.

## Final Response

Report:

- `RUN_DIR`
- validation status
- root filled CSV path
- `extraction/` provenance path
- that the filled table is agent-extracted and not human-reviewed
- the review question above

If review/export happens, report the root `_reviewed.csv` path.
