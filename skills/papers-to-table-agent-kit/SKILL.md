---
name: papers-to-table-agent-kit
description: Portable papers-to-table workflow for capable agents extracting structured information from scientific PDFs without the local app, LM Studio, or a fixed extraction algorithm. Use when a user wants a table, literature review, research report, optional browser review, auto-accept audit trail, or export package from PDFs plus an optional table/schema.
---

# Papers-To-Table Agent Kit

Use this skill to extract structured information from scientific PDFs using your own agent capabilities, then optionally package the result for review, audit, export, or report handoff.

Core principle: keep the extraction workspace loose and agent-owned. Normalize only when the user needs review, formal decisions, export, reproducibility, or report handoff.

## Modes

- `draft_report`: produce a table or use an internal table to write a report. No formal review bundle is required.
- `auto_accept`: the user wants formal artifacts but chooses to trust the agent. Record `decision_source="automation_accept_all"`.
- `human_review`: build a static browser review package with values, evidence/rationale, and editable decisions.
- `eval_import_compatible`: future stricter mode. Do not use it as the default MVP path.

## Extraction

Use any effective approach: PDF text, visual reading, tables, figures, file search, reasoning, or available tools. Do not force a fixed extraction sequence.

Prefer lightweight working columns while extracting:

- `value`
- `evidence`
- `rationale`
- `confidence`
- `needs_review`
- `source_location`
- `caveat`

When a schema is supplied, follow it. When no schema is supplied, create a lightweight column plan before extraction.

## Evidence

Evidence/rationale is required for values shown in the review UI and strongly recommended for claims used in reports.

For draft/report mode, evidence can be lightweight: source PDF, page/section/table/figure if known, a quote or paraphrased support when available, and a brief rationale or caveat.

## Review/Export Package

Create a lite bundle only when needed. Recommended layout:

```text
inputs/pdf_manifest.json
inputs/source_table.csv
inputs/seed_table.csv
inputs/schema.json
tables/draft_table.csv
proposals/proposals.jsonl
evidence/evidence.jsonl
review/review_data.json
review/review.html
review/decisions.jsonl
summaries/extraction_log.md
summaries/run_report.md
exports/final_table.csv
exports/audit_log_*.json
exports/diagnostics_*.json
```

For simple chat/table output, return the requested table/report plus caveats instead of creating a bundle.

## Helper Scripts

Use `scripts/build_review_package.py` when a review package is needed:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run path/to/run
```

It can normalize `tables/draft_table.csv` plus optional `evidence/evidence_notes.json` into proposals, evidence, `review_data.json`, and self-contained `review.html`.

Use `scripts/apply_review_decisions.py` after review or for auto-accept:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run path/to/run --decisions decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run path/to/run --accept-all
```

The source table is never overwritten. Formal export writes `exports/final_table.csv`; accepted-with-edit values override proposed values. Rejected and confirmed-no-data items are not exported as filled values.

## Report Handoff

You may use the extracted table internally for a literature review or research report. If values were not human-reviewed, do not imply that they were. Label information as human-reviewed, auto-accepted, agent-extracted, or draft/unreviewed where relevant.

## References

- `references/extraction_workflow.md`: practical workflow guidance.
- `references/review_export_normalization.md`: normalized review/export package shape.
