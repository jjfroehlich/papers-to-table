# Evidence-First Research Document Extraction Prompt

You are extracting structured information from research publications, scientific PDFs, or technical documents and preparing a human-reviewable papers-to-table package.

Input folder:
`<INPUT_FOLDER>`

Create one run folder:
`<RUN_DIR>`

Use the local agent kit:
`skills/papers-to-table-agent-kit/`

## Required Deliverable

Do not stop after producing `_filled.csv`, `completed_table.csv`, or other draft CSV files. A filled CSV alone is incomplete for review. A request for CSV outputs is not a CSV-only request. Treat the task as CSV-only only when the user explicitly says "CSV only", "skip review", "do not build the review UI", or equivalent.

The required deliverable is a formal review package:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # when a table template exists
  schema.json       # when a JSON schema exists
  schema.csv        # when a CSV schema exists
```

Copy all source PDFs into `RUN_DIR/pdfs/`. Preserve the source table template as `RUN_DIR/source_table.csv` and the schema as `RUN_DIR/schema.json` when available.

Before extracting values, create the `review_input.json` skeleton with `pdfs`, `columns`, `rows`, and an initially empty `proposals` array. Append one evidence-backed proposal as each non-empty target cell is authored.

## Extraction Rules

- Preserve original row order and row identifiers.
- Preserve all original columns in any optional draft filled CSV.
- Fill only supported target value columns.
- Do not guess values that are not supported by the PDFs.
- Use schema allowed values when provided.
- Leave unavailable values blank in draft CSVs.
- Use `proposal_status="no_data"` only when the paper explicitly indicates absence.
- Keep per-cell proposals row-aware: evidence from one paper must not support another row.
- Capture table, caption, figure, methods, supplement, and result-prose evidence when relevant.

## Evidence Requirements

Every non-empty proposed value in `review_input.json.proposals` must include structured evidence at extraction time. Do not keep evidence only in scratch notes.

Prefer direct evidence:

```json
{
  "pdf_id": "paper_a",
  "source_type": "direct_quote",
  "page_number": 3,
  "quote_text": "Exact supporting sentence from the PDF."
}
```

Table, caption, figure-caption, and generic evidence text are also acceptable when they directly support the value. If exact text cannot be captured, include `pdf_id`, `page_number`, `source_location`, and concise reasoning so the reviewer can inspect it.

## Build And Serve

After authoring `review_input.json`, run:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR
```

For non-interactive environments:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR --no-open
```

## Optional Draft CSVs

You may also produce clearly named draft `_filled.csv` files for convenience, but these are secondary. The formal review/export workflow starts from `review_input.json`.

For benchmark tasks, use draft CSV names and review status precisely:

- `draft_completed_table.csv`, `_filled.csv`, or `completed_table.csv`: agent-extracted draft values, not human-reviewed
- `exports/final_table.csv`: accepted-only table after human review or explicit `--accept-all`

If the broader task includes a literature review, research memo, or technical report, you may also render reviewed values as a concise summarizing table. Clearly label values as human-reviewed, auto-accepted, agent-extracted, or draft/unreviewed.

## Final Response

Before final response, verify that these artifacts exist unless the user explicitly requested CSV-only extraction:

- `RUN_DIR/review_input.json`
- `RUN_DIR/normalized/proposals.jsonl`
- `RUN_DIR/normalized/evidence.jsonl`
- `RUN_DIR/summaries/validation_report.json`
- `RUN_DIR/review/index.html`
- `review_url` or exact `serve_review.py` command

Report:

- `RUN_DIR`
- validation status
- `review_url` if the UI is running
- the exact serve command if the UI could not be kept running
- paths to optional draft `_filled.csv` files
