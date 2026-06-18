# Extraction Workflow

## Purpose

This kit is for agent-native extraction from research publications, scientific PDFs, and technical documents into a table with evidence-backed provenance. The agent reads documents and proposes values; the kit validates, normalizes, exports a filled CSV, and optionally prepares a human review UI.

## Default Flow

1. Create one `RUN_DIR`.
2. Create `RUN_DIR/extraction/review_input.json` before extracting values.
3. Reference input PDFs, source table, and schema by path; do not copy them into `RUN_DIR`.
4. Add one proposal per supported target cell with evidence and proposal-level `rationale`.
5. Run `build_review_package.py --run RUN_DIR --json`.
6. Return the root `<requested_or_dataset>_filled.csv` plus `extraction/` provenance, clearly labeled as agent-extracted and not human-reviewed.
7. Ask: `Do you want to review the results in the browser interface?`

Default output:

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

## Optional Human Review

Only build or serve review after the user opts in.

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR --host 127.0.0.1 --port PORT --no-open --quiet
```

Review output:

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

PDF rendering and quote highlighting are localhost-served review features. Static `human_review/index.html` can still show proposal and evidence text but cannot reliably render referenced source PDFs.

## Benchmark/Table Workflow

For benchmark folders, literature-review matrices, or table-completion tasks:

```bash
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --run RUN_DIR
```

The scaffold writes `extraction/review_input.json` with:

- `output_table_name`, usually `<dataset>_filled.csv`
- absolute PDF paths in `pdfs`
- `source_table_path` when a table template exists
- `schema_path` when a schema exists
- rows and columns inferred from the template/schema
- empty `proposals`

After scaffold, append evidence-backed proposals. Do not copy input PDFs, source tables, or schemas into the run directory.

## Evidence Authoring

Every non-empty `proposed_value` needs structured evidence. Use `rationale` on the proposal for extraction judgment, and evidence fields for source support.

Preferred direct evidence:

```json
{
  "pdf_id": "paper_a",
  "source_type": "direct_quote",
  "page_number": 3,
  "quote_text": "Exact supporting sentence from the PDF."
}
```

Weak but reviewable evidence:

```json
{
  "pdf_id": "paper_a",
  "page_number": 7,
  "source_location": "Results",
  "reasoning": "The page context implies the value, but no exact quote was captured."
}
```

For the proposal containing weak evidence, add a short rationale such as: `"rationale": "The value is inferred from the Results page context; no exact source quote was captured."`

## Final Handoff

Report:

- `RUN_DIR`
- validation status
- root filled CSV path
- `extraction/` provenance path
- that the filled table is agent-extracted and not human-reviewed
- the question: `Do you want to review the results in the browser interface?`

If review is requested, report the verified localhost URL and later the root `_reviewed.csv` path.
