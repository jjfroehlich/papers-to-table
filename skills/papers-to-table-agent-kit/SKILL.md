---
name: papers-to-table-agent-kit
description: Portable papers-to-table review handoff for capable agents. Use when an agent already extracted structured values from scientific PDFs and needs a rich local review bundle with PDF evidence inspection, decisions, and accepted-only exports without running the main app, FastAPI backend, LM Studio, or extraction pipeline.
---

# Papers-To-Table Agent Kit

Use this skill when a capable external agent performs extraction and needs a standardized handoff to human review.

Core product boundary: this kit does not try to improve the agent's extraction intelligence. It standardizes the handoff from agent extraction to human review.

External agents author only:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # optional
  schema.json       # optional
```

The kit scripts derive all normalized artifacts, review-package JSON, indexes, summaries, decisions, and exports. Agents should not hand-author `normalized/`, `summaries/`, `exports/`, `main_compat/`, or generated review files.

## Product Scope

The rich kit promises:

- proposal queue/table review
- PDF.js page and quote evidence inspection
- bundled PDF.js runtime assets so copying `skills/papers-to-table-agent-kit/` keeps quote highlighting working
- visible weak-evidence labels
- accept, accept-with-edit, reject, and confirmed-no-data decisions
- decision download or localhost writeback
- accepted-only `exports/final_table.csv`
- optional future XLSX export

The kit does not promise full main-app parity. It has no full backend API, provider diagnostics, run lifecycle, eval mode, mandatory page image generation, mandatory figure extraction, mandatory bbox anchoring, or complex diagnostics beyond generated validation/export summaries.

## Authoring Contract

`review_input.json` must use:

```json
{
  "schema_version": "papers_to_table.review_input.v1",
  "run_id": "agent_review_001",
  "pdfs": [
    {"pdf_id": "paper_a", "path": "pdfs/paper_a.pdf", "label": "Paper A"}
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

`templates/review_input.schema.json` is the local schema and `templates/review_input.example.json` is the compact example.

Optional fields in `review_input.json`:

- `proposal_id`
- `evidence_id`
- `cell_id`
- `created_at`

If IDs are absent, `build_review_package.py` generates stable deterministic IDs. If IDs are present, validation checks uniqueness and references.

## Evidence Requirements

Every non-empty `proposed_value` must have at least one structured evidence record. Prefer `pdf_id`, `page_number`, and text evidence.

Evidence source-type inference:

- If `source_type` is absent and `quote_text`, `table_text`, `evidence_text`, or `caption_text` is present, direct evidence is inferred.
- If `source_type` is absent and only `page_number` plus `reasoning` and/or `source_location` is present, `inferred_reasoning` is inferred.
- Generated evidence keeps `source_type` main-compatible and preserves the authored evidence kind separately in `authored_evidence_kind` when the input used kit-specific text kinds.

Evidence tiers:

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text -> `direct_strong`
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions -> `direct_strong` or `direct_weak`
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` -> `inferred_weak`, visible attention label
- Tier D: no structured evidence -> invalid for non-empty `proposed_value`

Strong evidence requires `pdf_id`, `page_number`, and at least one of `quote_text`, `table_text`, `evidence_text`, exact/approximate bbox regions, or `figure_ref` plus `caption_text`.

Highlight regions and bboxes must use finite numeric coordinates, a positive page reference, and nonzero area. Validation also checks normalized coordinates and warns about ambiguous coordinate conventions.

## Script Workflow

Validate author-authored inputs:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring
```

Build the rich review bundle:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR
```

Serve the review UI with localhost decision writeback and export:

```bash
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR
```

For download-only review, open `RUN_DIR/review/index.html` directly when browser security allows it. Localhost serving is the default path because it permits decision writeback and export.

Apply downloaded or server-written decisions:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/review/downloaded_decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

## Generated Artifacts

MVP build artifacts:

```text
review/
  index.html
  assets/*
  review_package.json
normalized/
  proposals.jsonl
  evidence.jsonl
summaries/
  validation_report.json
```

Generated only after review/export:

```text
review/decisions.jsonl
exports/final_table.csv
exports/audit_log_*.json
summaries/reviewer_summary.json
```

Optional future artifacts:

```text
exports/final_table.xlsx
normalized/proposal_index.json
normalized/review_lookup.json
main_compat/
assets/pages/
assets/figures/
```

Main-app-compatible artifacts are optional generated outputs, never required agent-authored inputs.

## Report Handoff

You may use extracted values internally for a literature review or research report. If values were not human-reviewed, do not imply that they were. Label information as human-reviewed, auto-accepted, agent-extracted, or draft/unreviewed where relevant.

## References

- `references/extraction_workflow.md`: agent extraction and review-input workflow.
- `references/review_export_normalization.md`: generated review/export artifact and decision semantics.
