You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions and mimic the examples.
Evidence rule: you must include at least one quote + page + chunk_id for any proposed_value. The quote must be a verbatim substring of the chunk text. If you cannot, mark status as unclear or no_evidence and leave proposed_value null.
Return JSON: {"proposals": [{"column": ..., "proposed_value": ..., "status": "found|inferred|not_found|unclear|no_evidence", "confidence": 0-1, "evidence": [{"quote":..., "page":..., "chunk_id":..., "locator_hint":...}], "needs_more_evidence": bool, "rationale": ...}]}
Row context:
{{row_context}}
Group schema:
{{group_schema}}
Examples:
{{examples}}
Retrieved chunks by column:
{{chunks}}
