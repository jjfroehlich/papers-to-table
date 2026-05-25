# Review/Export Normalization

## Boundary

Extraction can use any working format. Review/export needs normalized review items so decisions can be applied deterministically.

Minimum review item shape:

```json
{
  "proposal_id": "prop_...",
  "row_id": "row_...",
  "row_label": "Smith et al. 2024",
  "column_name": "Main finding",
  "proposed_value": "Treatment improved spatial resolution.",
  "rationale": "Supported by the results section.",
  "evidence": [
    {
      "evidence_id": "ev_...",
      "source_pdf": "paper.pdf",
      "page_number": 5,
      "source_type": "direct_quote",
      "raw_text": "..."
    }
  ],
  "confidence": "medium",
  "needs_review": true,
  "caveat": "Value summarizes a longer result."
}
```

`review_data.json` is denormalized for the browser UI. The durable source files are `proposals/proposals.jsonl`, `evidence/evidence.jsonl`, and `review/decisions.jsonl` when decisions are formalized.

## Decisions

Decision values:

- `accepted`
- `accepted_with_edit`
- `rejected`
- `confirmed_no_data`

Decision sources:

- `human_individual`
- `automation_accept_all`

Use `automation_accept_all` only when formal decision records are requested. For simple reports or chat tables, label the result as draft/unreviewed or agent-extracted instead of creating fake review records.

## Export Rules

Only accepted and accepted-with-edit values populate formal exports. Rejected, confirmed-no-data, and undecided values remain in audit/report artifacts but do not fill `exports/final_table.csv`.

The source table is never modified in place.
