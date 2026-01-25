Verify if locked cell value is supported by evidence.
Evidence rule: include quote + page + chunk_id; quote must be a verbatim substring of the chunk text. If not possible, return unclear with empty evidence.
Return JSON only (no markdown). Example:
{"column": "Accuracy", "status": "supports", "evidence": [{"quote": "Accuracy was 42%.", "page": 3, "chunk_id": "para-3-2-1", "locator_hint": "Accuracy was 42%"}], "rationale": "Quote matches the locked value."}
Row context:
{{row_context}}
Cell value:
{{cell_value}}
Retrieved chunks:
{{chunks}}
