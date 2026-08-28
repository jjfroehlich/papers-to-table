# Evidence-First Research Document Extraction Prompt

You are extracting structured information from research publications, scientific PDFs, or technical documents into a papers-to-table run.

Input folder:
`<INPUT_FOLDER>`

Create one run folder:
`<RUN_DIR>`

Create or use one output folder:
`<OUTPUT_DIR>`

Use the local agent kit:
`skills/papers-to-table-agent-kit/`

## Required Deliverable

Produce a lean extraction output by default:

```text
OUTPUT_DIR/
  <requested_or_dataset>_filled.csv
  runs/
    RUN_ID/
      extraction/
        review_input.json
        proposals.jsonl
        evidence.jsonl
        validation_report.json
        extraction_summary.json
  scratch_delete_after_success/
  logs/
```

Do not copy source PDFs, source tables, or schema files into `RUN_DIR`. Store absolute or explicitly resolvable paths in `extraction/review_input.json`.

Keep the workspace tidy. Final CSV deliverables belong at the `OUTPUT_DIR` root. Provenance and review artifacts belong under `OUTPUT_DIR/runs/RUN_ID`. Temporary extracted text, rendered page images, page crops, and helper scripts belong only under `OUTPUT_DIR/scratch_delete_after_success/RUN_ID`, then should be deleted after successful validation/build. Do not create ad hoc root folders such as `.git`, `.agents`, `tools`, `pdf_text_cache`, `rendered_pages`, or `completed_tables`.

CSV filenames, `_filled.csv`, `completed_table.csv`, or instructions such as `Return one completed CSV` do not mean evidence-free CSV-only extraction. The filled CSV must be backed by `extraction/review_input.json`, `proposals.jsonl`, and `evidence.jsonl` unless the user explicitly says CSV-only or skip evidence.

## Authoring

Prepare the output workspace before extracting values:

```bash
python skills/papers-to-table-agent-kit/scripts/prepare_output_workspace.py --output-dir OUTPUT_DIR --run-id RUN_ID --json
```

Before scaffolding, inventory all PDFs and audit which schema-target cells are blank or populated. Match every PDF to exactly one table row using DOI first, then normalized title, authors, and year from PDF front matter. Resolve title/preprint variants explicitly and write the canonical PDF stem into the matched row's `pdf_id`. A larger table may retain rows with no supplied PDF and blank `pdf_id`, but no supplied PDF may remain unused or map twice. Do not assign papers from filename similarity or row order. Stop on ambiguity; use the scaffold's positional fallback only when there are no explicit mappings, counts are equal, and the order was independently verified.

Before extracting any value, create `extraction/review_input.json` with:

- `schema_version`
- optional `extraction_mode` (`fill_blanks` by default; `fill_and_verify` only when explicitly requested)
- `run_id`
- `output_table_name`
- `output_table_path`
- `source_table_path` when a table template exists
- `schema_path` when a schema exists
- `pdfs` with source PDF paths
- `columns`
- `rows`
- an initially empty `proposals` array

Every non-empty proposal must be written with structured evidence at authoring time and should include concise proposal-level `rationale`.

Use a cell-by-cell evidence loop. For each target cell, verify the row's paper, identify the exact claim needed for that column, find the narrowest supporting sentence/table row/caption/page context, then write only that support into the proposal's `evidence` array.

## Extraction Rules

- Preserve original row order and row identifiers.
- Preserve all original columns in the root filled CSV.
- Fill only supported target value columns.
- Treat populated target cells as preserved data, not source evidence or examples to imitate. Keep metadata and manually curated columns as context unless the schema explicitly makes them targets.
- Confirm that evidence describes the present study; background, previous-study, comparison-only, and future-option passages cannot classify the current assay.
- Do not guess values that are not supported by the PDFs.
- Use schema allowed values when provided.
- Use finite JSON numbers for `number` fields and exact labels for categorical `allowed_values`; keep approximation in `numeric_value_form` and rationale rather than formatting a numeric value as prose.
- Leave unavailable values blank in the filled CSV unless a supported no-data proposal should be recorded.
- Use `proposal_status="no_data"` only when the paper explicitly indicates absence.
- Keep per-cell proposals row-aware: evidence from one paper must not support another row.
- Keep per-cell evidence column-specific: do not reuse the same evidence list across many columns unless the same passage directly supports each value.
- Capture table, caption, figure, methods, supplement, and result-prose evidence when relevant.
- Add proposal-level `rationale` for every value-bearing proposal; it is mandatory for interpretation, normalization to schema labels, calculation, weak/inferred evidence, or no-data conclusions. Avoid boilerplate like `Extracted from the provided PDF evidence for <column>`; explain the value-specific extraction judgment.
- A useful rationale is an evidence-grounded summary, not private step-by-step chain-of-thought. It names the source support, the proposed value, and the column: `The source [quote/table/caption/page context] supports [value] for [column] because [specific reason or schema normalization].`
- If validation warns about a generic rationale or reused evidence set, revise the affected proposals instead of handing off the warning.
- Record one derivation `reason_codes` value: `direct`, `calculation`, `figure_estimate`, `protocol_inference`, or `absence_inference`. Calculations require a reviewer-readable `calculation` and compatible evidence for every operand. Figure estimates require page-specific `figure_ref`, caption and/or rendered-panel region evidence, and `numeric_value_form="approximate"`. Absence inference requires a documented field-specific audit and is routed to reviewer attention with an `absence_inference` diagnostic.
- Before finishing each paper, reconcile design category, delivery/integration, readout, reporter-barcode role, UMI role, scale, and construct count against the same current-study assay stage, population, units, and QC state.

Under `fill_blanks`, never propose against a populated source cell and preserve its original value exactly. Under explicitly requested `fill_and_verify`, verify the populated value independently from its matched PDF and schema, then record any candidate correction with its own evidence; the builder preserves the existing value in the unreviewed filled CSV, exposes `is_verify_mode=true` and `existing_value` in review, and applies a correction only after acceptance into the reviewed CSV.

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

Keep `rationale` separate from evidence text: evidence fields preserve source support, while `rationale` briefly explains the extraction judgment for the reviewer. If a table row or caption supports several fields, reuse it only for those fields and make each rationale identify the field-specific support.

## Build

After authoring `extraction/review_input.json`, run:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring --json
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR --json
python skills/papers-to-table-agent-kit/scripts/cleanup_scratch.py --output-dir OUTPUT_DIR --json
python skills/papers-to-table-agent-kit/scripts/finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json
```

If authoring validation reports generic-rationale or reused-evidence warnings, edit `review_input.json` and rerun validation before building. Keep a shared evidence item only when the same source passage directly supports each affected column and each rationale explains the column-specific support. Run scratch cleanup only after successful build/validation and only for `OUTPUT_DIR/scratch_delete_after_success`.

Then verify:

- `OUTPUT_DIR/<requested_or_dataset>_filled.csv`
- `RUN_DIR/extraction/proposals.jsonl`
- `RUN_DIR/extraction/evidence.jsonl`
- `RUN_DIR/extraction/validation_report.json`
- `RUN_DIR/extraction/extraction_summary.json`

Also inspect `RUN_DIR/extraction/validation_report.json`; do not present the extraction as complete while generic-rationale or reused-evidence warnings remain unresolved.

A final answer that only lists CSV paths is incomplete. Run `finalize_extraction_handoff.py` before responding and fix any reported missing artifacts, failed validation, generic-rationale warnings, or reused-evidence warnings.

## Optional Human Review

After the filled CSV and extraction provenance are complete, ask exactly:

```text
Do you want to review the results in the browser interface?
```

Only if the user says yes, build and serve review:

```bash
python skills/papers-to-table-agent-kit/scripts/launch_review_servers.py --run RUN_DIR --build --start-port 8761 --quiet --json
```

For multiple independent run directories, pass one `--run` argument per directory to `launch_review_servers.py`. It starts detached localhost servers, probes each URL ending in `/human_review/index.html`, prints the verified links, and exits. Do not leave `serve_review.py` as a foreground command, and do not hand-write long-running shell or PowerShell process loops. Always include the exact clickable URL in the chat so the user can open or reload it manually.

Human review artifacts live in:

```text
OUTPUT_DIR/
  <requested_or_dataset>_reviewed.csv
  runs/
    RUN_ID/
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

- `OUTPUT_DIR`
- `RUN_DIR`
- validation status
- filled CSV path
- `extraction/` provenance path
- that the filled table is agent-extracted and not human-reviewed
- the review question above

End the final answer with the exact line `Do you want to review the results in the browser interface?` unless the user has already declined review. If review is requested, either open the verified localhost review URL in the browser or provide it as a clickable link in chat; do both when possible. If review/export happens, report the root `_reviewed.csv` path.
