# Extraction Workflow

## Purpose

This kit is for agent-native extraction from research publications, scientific PDFs, and technical documents into a table with evidence-backed provenance. The agent reads documents and proposes values; the kit validates, normalizes, exports a filled CSV, and optionally prepares a human review UI.

## Default Flow

1. Create one `OUTPUT_DIR` for the task and one run folder under `OUTPUT_DIR/runs/RUN_ID`.
2. Create `RUN_DIR/extraction/review_input.json` before extracting values.
3. Reference input PDFs, source table, and schema by path; do not copy them into `RUN_DIR`.
4. Add one proposal per supported target cell with evidence and proposal-level `rationale`.
5. Run `build_review_package.py --run RUN_DIR --json`.
6. After successful build/validation, run `cleanup_scratch.py --output-dir OUTPUT_DIR --json` to delete only marked scratch folders under `scratch_delete_after_success/`.
7. Run `finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json` and fix any reported error before the final answer.
8. Return `OUTPUT_DIR/<requested_or_dataset>_filled.csv` plus `RUN_DIR/extraction/` provenance, clearly labeled as agent-extracted and not human-reviewed.
9. End the final answer with: `Do you want to review the results in the browser interface?`

Default output:

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

Final CSVs belong at the `OUTPUT_DIR` root. Provenance and review artifacts belong under `OUTPUT_DIR/runs/RUN_ID`. Temporary extracted text, rendered page images, page crops, and helper scripts belong only under `OUTPUT_DIR/scratch_delete_after_success/RUN_ID`, then should be deleted after successful validation/build. Do not create ad hoc root folders such as `.git`, `.agents`, `tools`, `pdf_text_cache`, `rendered_pages`, or `completed_tables`.

## Optional Human Review

Only build or serve review after the user opts in.

```bash
python skills/papers-to-table-agent-kit/scripts/launch_review_servers.py --run RUN_DIR --build --start-port 8761 --quiet --json
```

Review output:

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

PDF rendering and quote highlighting are localhost-served review features. Static `human_review/index.html` can still show proposal and evidence text but cannot reliably render referenced source PDFs.

After the user opts in, the review setup is not complete until the user has a usable browser entrypoint. Use `launch_review_servers.py` for this handoff, passing one `--run` per independent run. It starts detached servers, probes each URL, prints the exact URLs, and exits so the agent can answer immediately. Always include the exact clickable URL in the chat as well. The URL should end in `/human_review/index.html`; do not shorten it to `/review`. Do not hand-write PowerShell `Start-Process` loops or run `serve_review.py` as the foreground command for this handoff.

## Benchmark/Table Workflow

For benchmark folders, literature-review matrices, or table-completion tasks:

First resolve the authoritative table. Recursively inspect compatible CSV/XLSX files in the dataset, even under archive/complete/original-like folders, and compare schema target columns plus overlapping row identities. A file named `table_template.csv` is not automatically authoritative, blanks are not automatically intentional, and protected benchmark `table_gold.csv` must never be used as an extraction baseline. Then count blank and populated schema-target cells, distinguish metadata from target columns, inventory the PDFs, and choose `fill_blanks` unless the user explicitly requested verification of existing values. Match each PDF to a row using DOI first, then normalized title, authors, and year from the PDF front matter. Resolve preprint/publication title variants and abbreviated filenames explicitly. Write the matched PDF stem to that row's `pdf_id` field.

Every supplied PDF must map to exactly one row. It is valid for a larger table to retain rows without a supplied PDF and a blank `pdf_id`. It is not valid to infer identity merely from filename resemblance or sorted row order. Stop on ambiguous, unknown, duplicate, or unused PDF matches. The positional fallback is only for a dataset with no explicit mappings, equal row/PDF counts, and independently verified one-to-one order.

```bash
python skills/papers-to-table-agent-kit/scripts/prepare_output_workspace.py --output-dir OUTPUT_DIR --run-id RUN_ID --json
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --output-root OUTPUT_DIR --extraction-mode fill_blanks --json
```

If a companion table contains values missing from the template, the scaffold fails before creating the run. Select the approved source explicitly:

```bash
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --output-root OUTPUT_DIR --authoritative-table PATH_TO_APPROVED.csv --json
```

For XLSX, add `--authoritative-sheet SHEET_NAME` when needed. `--allow-template-only` is a deliberate override for cases where the user has confirmed that companion values must be disregarded. The scaffold writes `extraction/baseline_manifest.json`; retain it with the run and verify its hashes during validation.

If—and only if—the positional conditions above are satisfied, add `--allow-positional-pdf-fallback`. The default scaffold fails closed if any supplied PDF lacks an explicit row mapping. It also rejects unknown and duplicate mappings before creating run artifacts.

The scaffold writes `extraction/review_input.json` with:

- `output_table_name`, usually `<dataset>_filled.csv`
- `output_table_path`, usually `OUTPUT_DIR/<dataset>_filled.csv`
- absolute PDF paths in `pdfs`
- `source_table_path` when a table template exists
- `schema_path` when a schema exists
- rows and columns inferred from the template/schema
- empty `proposals`

Its command result also reports the mapping mode, mapped and table-only row counts, and total, blank, populated, and eligible target-cell counts for PDF-mapped rows. Separate source-table and table-only target-cell totals make a larger preserved table explicit without treating its unmatched rows as extraction work. CSV schemas accept `allowed_values` as either JSON arrays (for example `["yes", "no"]`) or pipe-delimited text (`yes|no`); both become arrays in `review_input.json`.

After scaffold, append evidence-backed proposals. Keep every non-empty effective-baseline target value in `rows[].values` so the review table shows it. Do not copy input PDFs or schemas into the run directory; an explicit authoritative source is merged into the run-local `extraction/authoritative_baseline.csv` with its original path and hash recorded in the manifest.

The optional top-level `extraction_mode` defaults to `fill_blanks`. In this mode, populated cells are preserved exactly and are ineligible for proposals. Existing table values are neither source evidence nor semantic examples to copy into blank cells. Set the mode to `fill_and_verify` only after an explicit request to audit already-populated cells, and verify each existing value independently from the matched paper and schema. Verify-mode proposals are review candidates, not edits to the unreviewed filled CSV; an accepted review decision is required before the reviewed CSV changes. Metadata and manually curated columns remain context unless the schema explicitly includes them as extraction targets.

## Evidence Authoring

Every non-empty `proposed_value` needs structured evidence. Use `rationale` on the proposal for extraction judgment, and evidence fields for source support.

Keep evidence column-specific. Do not paste the same evidence list into every target cell for a paper; reviewers need the passage, table row, caption, or page context that supports that specific value. Shared evidence is acceptable only when the same source passage directly contains or proves each value.

Write value-specific rationale summaries. Avoid template text like `Extracted from the provided PDF evidence for <column>`; explain the exact extraction judgment and any schema normalization. The rationale should state the source fact, the value or no-data inference, and why that fits the column/schema without exposing private step-by-step chain-of-thought.

Author each proposal in a cell-by-cell loop:

1. Verify the proposal's `row_id`, `column_name`, and `pdf_id`.
2. Verify that the passage describes the present study rather than background, prior work, a comparison assay, or a future option.
3. Identify the claim the cell needs to make, then find the narrowest source support for that claim.
4. Add evidence objects that support that claim only. Use separate evidence for separate claims unless one table row/caption directly contains all of them.
5. Write the rationale in this shape: `The source [quote/table/caption/page context] supports [proposed value] for [column] because [specific reason or normalization].`
6. If the value is unavailable, leave the CSV cell blank unless the paper explicitly supports a `no_data` proposal; cite that absence or scope and explain it in the rationale.

Choose and record a derivation path in `reason_codes`: `direct`, `calculation`, `figure_estimate`, `protocol_inference`, or `absence_inference`. Calculations require a `calculation` string and evidence for compatible operands. Figure estimates require page-specific `figure_ref` plus caption or rendered-panel region evidence and `numeric_value_form="approximate"`. Absence inference requires a documented field-specific search scope and reviewer-facing rationale; it is normalized to an attention item with an `absence_inference` diagnostic. Use `numeric_value_form` (`exact`, `range`, or `approximate`) when numeric provenance matters.

Apply field definitions as contracts: JSON numbers for `number` fields and exact allowed labels for categorical fields. Before finishing a paper, reconcile design, delivery/integration, readout, barcode role, UMI role, scale, and construct-count claims so related cells describe the same current-study assay, population, stage, and QC unit.

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

Before building, run:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring --json
```

generic-rationale and reused-evidence warnings mean the reviewer will probably see unhelpful provenance. Fix the proposals and rerun validation before building, unless the reuse is genuinely supported and each rationale explains its column-specific support.

## Handoff Gate

A final answer that only lists completed CSVs is incomplete. Before responding, run:

```bash
python skills/papers-to-table-agent-kit/scripts/finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json
```

For multiple datasets, repeat `--run` in the same command. Do not send the final answer while this checker reports missing generated artifacts, failed validation, generic-rationale warnings, or reused-evidence warnings.

## Final Handoff

Report:

- `OUTPUT_DIR`
- `RUN_DIR`
- validation status
- filled CSV path
- `extraction/` provenance path
- that the filled table is agent-extracted and not human-reviewed
- the question: `Do you want to review the results in the browser interface?`

End the final answer with the exact review question unless the user has already declined review. If review is requested, either open the verified localhost URL in the browser or provide it as a clickable link in chat; do both when possible. Later, report the root `_reviewed.csv` path.
