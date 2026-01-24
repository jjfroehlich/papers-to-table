You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions and mimic the examples.
If a value exists, return a concise proposed_value. If uncertain, set status=unclear and include the best supporting quote (if any).
Evidence rule: you must include at least one quote + page + chunk_idx for any proposed_value. The quote must be a verbatim substring of the chunk text. If you cannot, mark status as unclear or not_found and leave proposed_value null.
Return strict JSON:
{"proposals": [{"col_id": int, "proposed_value": string|null, "status": "found|inferred|not_found|unclear", "confidence": 0-1, "evidence": [{"quote":string, "page":int, "chunk_idx":int, "locator_hint":string|null}], "needs_more_evidence": bool, "rationale": string}]}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
Retrieved chunks:
{{chunks}}
