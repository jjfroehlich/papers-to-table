# Papers-To-Table Agent Kit

`skills/papers-to-table-agent-kit/` is a portable review handoff kit for regular agents (Codex, Claude, Hermes) that extract structured values from PDFs without running the local app. Based on insights from building the local app.

The kit does not improve the agent's extraction intelligence. It standardizes the handoff from agent extraction to human review: agents provide `review_input.json`, PDFs, and optional table/schema inputs; kit scripts generate the rich local review UI, normalized artifacts, decisions, audit logs, and accepted-only exports.

## Input Layout

External agents author only:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # optional
  schema.json       # optional
```

The generated directories are script-owned. Do not hand-author `normalized/`, `summaries/`, `exports/`, or main-app-compatible artifacts.

## Review Input

`review_input.json` uses schema version `papers_to_table.review_input.v1`.

Minimal example:

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

`proposal_id`, `evidence_id`, `cell_id`, and `created_at` are optional. The builder generates deterministic IDs when they are absent and validates uniqueness when they are supplied.

Every non-empty proposed value needs at least one structured evidence record. Quote, table, caption, evidence text, bbox regions, or figure-caption evidence produce stronger labels; page-plus-reasoning evidence is allowed but is visibly marked weak/attention in the review UI.

Generated evidence keeps `evidence_schema_version="main_evidence"` and normalizes `source_type` to main-compatible values. If the authored evidence used kit-specific text kinds such as `table_text`, `caption_text`, or `evidence_text`, the original kind is preserved in `authored_evidence_kind`.

Highlight regions must use finite numeric coordinates, a positive page reference, and nonzero area. Normalized coordinates must stay within `[0, 1]`; validation also warns when coordinate conventions look ambiguous.

## Build And Review

Validate the agent-authored inputs:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring
```

Build the static review bundle:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR
```

Serve the review bundle on localhost:

```bash
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR
```

The server prints and opens a `http://127.0.0.1:.../review/index.html` URL. Localhost mode supports decision writeback and accepted-only export. The review header visibly distinguishes browser-only saves, confirmed server writeback, and server writeback failures. Opening `RUN_DIR/review/index.html` directly can work as download-only mode when the browser allows local PDF access.

## Generated Artifacts

`build_review_package.py` writes:

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

After review/export, the kit writes:

```text
review/decisions.jsonl
exports/final_table.csv
exports/audit_log_*.json
summaries/reviewer_summary.json
```

`exports/final_table.csv` includes only accepted and accepted-with-edit values. Rejected, pending, and confirmed-no-data proposals are preserved in audit artifacts but are not exported as filled values.

## Applying Decisions

If decisions were downloaded from the browser, apply them with:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/review/downloaded_decisions.json
```

If `serve_review.py` wrote `review/decisions.jsonl`, export with:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
```

For trusted automation, the kit can explicitly auto-accept all proposals:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

Auto-accepted decisions are recorded with `decision_source="automation_accept_all"`.

## Installation

Install by telling your agent to use `https://github.com/jjfroehlich/papers-to-table/tree/main/skills/papers-to-table-agent-kit/`, or copy `skills/papers-to-table-agent-kit/` into the agent system's skill directory. Keep `assets/`, `references/`, `scripts/`, and `templates/` with it so the bundled PDF.js viewer remains portable and quote highlighting works in the default workflow.
