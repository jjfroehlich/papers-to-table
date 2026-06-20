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

```bash
python skills/papers-to-table-agent-kit/scripts/prepare_output_workspace.py --output-dir OUTPUT_DIR --run-id RUN_ID --json
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --output-root OUTPUT_DIR --json
```

The scaffold writes `extraction/review_input.json` with:

- `output_table_name`, usually `<dataset>_filled.csv`
- `output_table_path`, usually `OUTPUT_DIR/<dataset>_filled.csv`
- absolute PDF paths in `pdfs`
- `source_table_path` when a table template exists
- `schema_path` when a schema exists
- rows and columns inferred from the template/schema
- empty `proposals`

After scaffold, append evidence-backed proposals. Do not copy input PDFs, source tables, or schemas into the run directory.

## Evidence Authoring

Every non-empty `proposed_value` needs structured evidence. Use `rationale` on the proposal for extraction judgment, and evidence fields for source support.

Keep evidence column-specific. Do not paste the same evidence list into every target cell for a paper; reviewers need the passage, table row, caption, or page context that supports that specific value. Shared evidence is acceptable only when the same source passage directly contains or proves each value.

Write value-specific rationale summaries. Avoid template text like `Extracted from the provided PDF evidence for <column>`; explain the exact extraction judgment and any schema normalization. The rationale should state the source fact, the value or no-data inference, and why that fits the column/schema without exposing private step-by-step chain-of-thought.

Author each proposal in a cell-by-cell loop:

1. Verify the proposal's `row_id`, `column_name`, and `pdf_id`.
2. Identify the claim the cell needs to make, then find the narrowest source support for that claim.
3. Add evidence objects that support that claim only. Use separate evidence for separate claims unless one table row/caption directly contains all of them.
4. Write the rationale in this shape: `The source [quote/table/caption/page context] supports [proposed value] for [column] because [specific reason or normalization].`
5. If the value is unavailable, leave the CSV cell blank unless the paper explicitly supports a `no_data` proposal; cite that absence or scope and explain it in the rationale.

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
