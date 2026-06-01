# Extraction Workflow

## Purpose

This kit is for agent-native extraction followed by standardized review handoff. The agent decides how to read PDFs and propose values. The kit scripts validate and normalize the handoff for human review, decisions, and export.

The kit does not try to improve the agent's extraction intelligence.

## Practical Flow

1. Clarify whether the user needs a draft table/report or a formal review/export package.
2. If a schema exists, follow it. If not, draft a lightweight column plan before extraction.
3. Extract values using whatever works in the environment.
4. Preserve structured evidence for every non-empty proposed value.
5. Write only `review_input.json`, `pdfs/`, and optional `source_table.csv` or `schema.json`.
6. Run `build_review_package.py` to derive normalized proposals/evidence and the rich review UI.
7. Run `serve_review.py` for localhost decision writeback and accepted-only export.

## Authoring Workspace

External agents author this simple layout:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # optional
  schema.json       # optional
```

Generated directories such as `normalized/`, `summaries/`, `review/`, `exports/`, and `main_compat/` are script-owned. Do not create them by hand.

## Column Planning

Use only what the task needs. A compact column definition can be:

```json
{
  "column_name": "Main finding",
  "description": "One concise statement of the paper's main empirical finding.",
  "field_type": "text"
}
```

More detail such as allowed values, null policy, evidence requirements, and formatting guidance is useful when the user asks for high consistency or review/export.

## Evidence Authoring

Every non-empty `proposed_value` needs at least one structured evidence object in `review_input.json`.

Preferred direct evidence:

```json
{
  "pdf_id": "paper_a",
  "source_type": "direct_quote",
  "page_number": 3,
  "quote_text": "Exact supporting sentence from the PDF."
}
```

Table, caption, and generic evidence text are also valid:

```json
{
  "pdf_id": "paper_a",
  "page_number": 5,
  "source_type": "table_text",
  "table_text": "Reported value in Table 2."
}
```

Weak but reviewable evidence is allowed when the agent cannot provide exact text:

```json
{
  "pdf_id": "paper_a",
  "page_number": 7,
  "source_location": "Results",
  "reasoning": "The page context implies the value, but no exact quote was captured."
}
```

The UI labels weak evidence visibly. Non-empty proposed values with no structured Tier A/B/C evidence are invalid.

## Coverage

Sparse extraction is acceptable when it is explicit. Leave unproposed cells out of `proposals`, or use `proposal_status="no_data"` when the paper explicitly does not report a requested value.

Formal exports include only accepted and accepted-with-edit decisions. Draft/report values that have not been reviewed must be labeled as draft, agent-extracted, or auto-accepted as appropriate.
