You are extracting values for a group of columns from retrieved chunks.
Return JSON: {"proposals": [{"column": ..., "proposed_value": ..., "status": "found|inferred|not_found", "confidence": 0-1, "evidence": [{"quote":..., "page":..., "locator_hint":...}], "flags": {"needs_more_evidence": bool, "mapping_dependent": bool}, "reasoning": ...}]}
Row context:
{{row_context}}
Group schema:
{{group_schema}}
Retrieved chunks:
{{chunks}}
