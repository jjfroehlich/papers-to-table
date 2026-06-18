# Review/Export Normalization

## Boundary

Extraction can use any working format, but formal review/export starts from one authored file: `review_input.json`.

`build_review_package.py` owns normalization. It generates deterministic proposal, evidence, and cell identifiers when the authored input omits them. It validates supplied identifiers when the authored input includes them.

## MVP Generated Artifacts

After a successful build:

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
exports/
  draft_filled_table.csv
```

`review/review_package.json` is the browser package. `normalized/proposals.jsonl` and `normalized/evidence.jsonl` are the durable generated streams used by decision application and generated validation.

`exports/draft_filled_table.csv` is generated from proposed values before review. It is an unreviewed draft convenience output, not an accepted-values export.

## Proposal Shape

Generated proposal records use a stable review/export shape:

```json
{
  "proposal_schema_version": "papers_to_table.agent_normalized_proposal.v1",
  "run_id": "agent_review_001",
  "proposal_id": "prop_...",
  "cell_id": "cell_...",
  "row_id": "row_1",
  "pdf_id": "paper_a",
  "column_name": "Finding",
  "proposed_value": "Example value",
  "proposal_status": "value_proposed",
  "evidence_status": "direct_strong",
  "review_bucket": "review",
  "evidence_ids": ["ev_..."],
  "created_at": "2026-06-01T00:00:00Z"
}
```

Supported review-facing decisions are:

- `accepted`
- `accepted_with_edit`
- `rejected`
- `confirmed_no_data`

Supported new decision sources are:

- `human_individual`
- `human_bulk_accept`
- `automation_accept_all`

## Evidence Shape

Generated evidence records currently use the canonical evidence schema tag `main_evidence`:

```json
{
  "evidence_schema_version": "main_evidence",
  "evidence_id": "ev_...",
  "proposal_id": "prop_...",
  "pdf_id": "paper_a",
  "page_number": 3,
  "source_type": "direct_quote",
  "quote_text": "Exact supporting sentence from the PDF.",
  "evidence_status": "direct_strong",
  "review_bucket": "review"
}
```

Evidence source-type inference:

- Text fields such as `quote_text`, `table_text`, `evidence_text`, or `caption_text` infer direct evidence.
- `page_number` plus `reasoning` and/or `source_location` infers `inferred_reasoning`.
- Optional exact and approximate highlight regions are normalized when supplied.

## Evidence Tiers

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text -> `direct_strong`
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions -> `direct_strong` or `direct_weak`
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` -> `inferred_weak`, attention
- Tier D: no structured evidence -> invalid for non-empty proposed values

## Export Rules

Decision/export artifacts are generated only after review or explicit automation:

```text
review/decisions.jsonl
exports/final_table.csv
exports/audit_log_*.json
exports/diagnostics_*.json
exports/reviewed_bundle/
  filled_table_reviewed.csv
  manifest.json
  review/
    decisions.jsonl
    proposals.jsonl
    evidence.jsonl
  audit/
    audit_log_*.json
    diagnostics_*.json
    reviewer_summary.json
    validation_report.json
summaries/reviewer_summary.json
```

Only accepted and accepted-with-edit values populate `exports/final_table.csv`. Rejected, confirmed-no-data, and undecided values remain in decision/audit artifacts but do not fill exported cells.

`exports/reviewed_bundle/` is the cleaned shareable folder and intentionally excludes copied source PDFs, the source table, schema files, review HTML, and PDF.js assets.

The source table is never modified in place.

## Optional Later Outputs

These are optional generated outputs, not authored inputs:

```text
exports/final_table.xlsx
normalized/proposal_index.json
normalized/review_lookup.json
assets/pages/
assets/figures/
```
