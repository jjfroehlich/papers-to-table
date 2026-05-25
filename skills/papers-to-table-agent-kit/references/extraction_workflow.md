# Extraction Workflow

## Purpose

This kit is for agent-native extraction. The agent decides how to read and reason over PDFs. The kit only standardizes optional review/export boundaries.

## Practical Flow

1. Clarify the output the user actually needs: table, report, review package, export, or audit trail.
2. If a schema exists, follow it. If not, draft a lightweight column plan before extraction.
3. Extract values using whatever works in the environment.
4. Keep evidence/rationale for important values, uncertain values, and report claims.
5. If the user wants review/export/audit, normalize values with `build_review_package.py`.
6. If the user wants a report, use reviewed or clearly labeled draft/auto-accepted values.

## Lightweight Column Plan

Use only what the task needs. A compact plan can be:

```json
{
  "columns": [
    {
      "column_name": "Main finding",
      "description": "One concise statement of the paper's main empirical finding.",
      "format": "short sentence",
      "guidance": "Prefer the abstract/results conclusion and avoid speculation."
    }
  ]
}
```

More detail such as allowed values, null policy, evidence requirements, and formatting guidance is useful when the user asks for high consistency or review/export.

## Evidence Notes

For review package generation, optional `evidence/evidence_notes.json` may be a list of objects:

```json
[
  {
    "row_id": "row_1",
    "column_name": "Main finding",
    "evidence": "The treated group showed a 42% improvement...",
    "rationale": "The sentence directly reports the primary result.",
    "source_pdf": "paper1.pdf",
    "page_number": 4,
    "source_location": "Results",
    "confidence": "high",
    "caveat": ""
  }
]
```

The agent can also keep evidence inline in notes or a report for draft/report mode. Formal review UI values should have evidence or rationale.

## Coverage

Sparse extraction is normal for MVP. If a bundle is created, state the coverage policy in `summaries/run_report.md`, especially when some papers, columns, or cells were skipped.

Complete target-cell accounting is reserved for future eval/import-compatible mode.
