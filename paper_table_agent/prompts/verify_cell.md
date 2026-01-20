Verify if locked cell value is supported by evidence.
Evidence rule: include quote + page + chunk_id; quote must be a verbatim substring of the chunk text. If not possible, return unclear with empty evidence.
Return JSON with {"column": ..., "status": "supports|contradicts|unclear", "evidence": [{"quote":..., "page":..., "chunk_id":..., "locator_hint":...}], "rationale": ...}
Row context:
{{row_context}}
Cell value:
{{cell_value}}
Retrieved chunks:
{{chunks}}
