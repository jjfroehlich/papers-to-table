---
name: papers-to-table-agent-kit
description: Standalone skill for extracting structured information from research publications, scientific PDFs, and technical documents into evidence-backed tables. Use when an agent needs to fill benchmark tables, create structured literature-review tables, preserve source evidence, inspect proposed values in a local review UI, or export accepted results as CSV/report-ready tables.
---

# Papers-To-Table Agent Kit

Use this skill when an agent extracts structured information from research publications, scientific PDFs, or other technical documents into an evidence-backed table.

The default output is lean and extraction-first: a usable root-level filled CSV plus one provenance folder. Human review is optional and should be offered after extraction.

## Default Contract

Do not stop at an unsupported CSV-only answer unless the user explicitly says "CSV only", "skip evidence", or equivalent. A request for `_filled.csv`, `completed_table.csv`, or `Return one completed CSV` still needs evidence-backed extraction records.

Before extracting values, create:

```text
RUN_DIR/
  extraction/
    review_input.json
```

`extraction/review_input.json` stores references to source inputs instead of copied files. Prefer absolute paths for PDFs, source tables, and schemas. Do not copy source PDFs, source tables, or schema files into `RUN_DIR`.

After extraction and build, the canonical output is:

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

The filled CSV is agent-extracted and not human-reviewed unless a human review decision/export step has occurred.

## Human Review

After producing the filled CSV and `extraction/` artifacts, ask the user:

```text
Do you want to review the results in the browser interface?
```

Only build or start the browser interface if the user says yes. Human review artifacts live in:

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

The reviewed table is written at the run root by appending `_reviewed.csv` to the filled-table stem. Example: `genome_editing_tools_filled.csv` becomes `genome_editing_tools_reviewed.csv`.

PDF rendering and quote highlighting require serving `human_review/` over localhost. Static `human_review/index.html` remains useful for proposal/evidence text and downloaded decisions, but source PDF rendering is a served-mode feature because inputs are referenced rather than copied.

## Authoring Contract

`extraction/review_input.json` must use:

```json
{
  "schema_version": "papers_to_table.review_input.v1",
  "run_id": "agent_review_001",
  "output_table_name": "agent_review_001_filled.csv",
  "source_table_path": "C:/path/to/source_table.csv",
  "schema_path": "C:/path/to/schema.csv",
  "pdfs": [
    {"pdf_id": "paper_a", "path": "C:/path/to/paper_a.pdf", "label": "Paper A"}
  ],
  "columns": [
    {"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}
  ],
  "rows": [
    {"row_id": "row_1", "pdf_id": "paper_a", "values": {"Title": "Paper A"}}
  ],
  "proposals": [
    {
      "row_id": "row_1",
      "column_name": "Finding",
      "proposed_value": "Example value",
      "rationale": "The quoted sentence directly supports the proposed value.",
      "evidence": [
        {
          "pdf_id": "paper_a",
          "source_type": "direct_quote",
          "page_number": 3,
          "quote_text": "Exact supporting sentence from the PDF."
        }
      ]
    }
  ]
}
```

Every non-empty `proposed_value` must include structured evidence at authoring time. Every value-bearing proposal should include a concise proposal-level `rationale`. The rationale explains why the proposed value follows from the evidence, especially for interpretation, normalization to schema labels, calculation, weak/inferred evidence, or no-data conclusions.

Optional identity fields:

- `proposal_id`
- `evidence_id`
- `cell_id`
- `calculation`
- `created_at`

If IDs are absent, `build_review_package.py` generates stable deterministic IDs.

## Evidence Requirements

Strong evidence requires `pdf_id`, `page_number`, and at least one of `quote_text`, `table_text`, `evidence_text`, `caption_text`, exact/approximate highlight regions, or figure reference plus caption text.

Evidence tiers:

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text -> `direct_strong`
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions -> `direct_strong` or `direct_weak`
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` -> `inferred_weak`
- Tier D: no structured evidence -> invalid for non-empty proposed values

Keep `rationale` separate from evidence text: evidence fields preserve source-grounded support, while `rationale` summarizes the extraction judgment.

## Script Workflow

For benchmark folders:

```bash
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --run RUN_DIR
```

Build the lean extraction outputs:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR --json
```

If the user wants browser review, build and serve the optional review UI:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR --host 127.0.0.1 --port PORT --no-open --quiet
```

Apply downloaded or server-written decisions:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/human_review/downloaded_decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

`apply_review_decisions.py` writes the root `<stem>_reviewed.csv` and `human_review/` audit files.

## Final Handoff

Before reporting completion, verify:

- `RUN_DIR/<requested_or_dataset>_filled.csv`
- `RUN_DIR/extraction/review_input.json`
- `RUN_DIR/extraction/proposals.jsonl`
- `RUN_DIR/extraction/evidence.jsonl`
- `RUN_DIR/extraction/validation_report.json`
- `RUN_DIR/extraction/extraction_summary.json`

Report the run directory, validation status, the filled CSV path, and whether the values are unreviewed agent-extracted values. Then ask whether the user wants browser review.

If review is requested, report the verified `human_review` localhost URL and, after export, the root `<stem>_reviewed.csv`.

## References

- `references/extraction_workflow.md`: agent extraction and optional review workflow.
- `references/review_export_normalization.md`: generated artifact and decision semantics.
- `templates/extraction_to_review_prompt.md`: reusable external-agent prompt for evidence-first extraction.
