# Review/Export Normalization

## Boundary

Extraction starts from `RUN_DIR/extraction/review_input.json`. The file references inputs by path and is the only agent-authored control file.

`build_review_package.py` owns normalization. It generates deterministic proposal, evidence, and cell identifiers when authored input omits them.

## Default Generated Artifacts

After a successful default build:

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

`<requested_or_dataset>_filled.csv` is generated from proposed values before review. It is a usable agent-extracted table, but it is not human-reviewed.

`extraction/proposals.jsonl` and `extraction/evidence.jsonl` are the durable generated streams used by optional review and decision application.

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
  "rationale": "The quoted sentence directly supports the proposed value.",
  "proposal_status": "value_proposed",
  "evidence_status": "direct_strong",
  "review_bucket": "review",
  "evidence_ids": ["ev_..."],
  "created_at": "2026-06-01T00:00:00Z"
}
```

Supported review-facing decisions:

- `accepted`
- `accepted_with_edit`
- `rejected`
- `confirmed_no_data`

Supported decision sources:

- `human_individual`
- `human_bulk_accept`
- `human_bulk_selection`
- `automation_accept_all`

## Evidence Shape

Generated evidence records use the canonical evidence schema tag `main_evidence`:

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

- `quote_text`, `table_text`, `evidence_text`, or `caption_text` infer direct evidence.
- `page_number` plus `reasoning` and/or `source_location` infers `inferred_reasoning`.
- Optional exact and approximate highlight regions are normalized when supplied.

## Optional Human Review Artifacts

Generated only when review is explicitly requested:

```text
RUN_DIR/
  human_review/
    index.html
    assets/
    review_package.json
    decisions.jsonl
```

Generated after decisions are applied:

```text
RUN_DIR/
  <requested_or_dataset>_reviewed.csv
  human_review/
    reviewer_summary.json
    audit_log_*.json
    diagnostics_*.json
```

Only accepted and accepted-with-edit values populate the reviewed CSV. Rejected, confirmed-no-data, and undecided values remain in human review and audit artifacts.

The source table is never modified in place. Source PDFs, source table, and schema are never copied into the run output; they are referenced by path.

## Optional Later Outputs

Optional generated outputs, not authored inputs:

```text
extraction/proposal_index.json
extraction/review_lookup.json
```
