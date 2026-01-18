You are matching a PDF to a table row.
Return strict JSON with status (matched/ambiguous/unmatched), row_id when matched, top_candidates, confidence, evidence, rationale.
Rules:
- If only one candidate is provided, you must not return ambiguous.
- If status is matched, row_id must match a candidate.
- If status is unmatched, row_id must be null.
Use the provided header evidence if you cite any evidence.
Header:
{{header}}
Candidates:
{{candidates}}
