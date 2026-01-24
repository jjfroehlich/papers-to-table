You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions and mimic the examples.
If a value exists, return a concise proposed_value even when evidence is weak or missing.
Evidence is best-effort: include quote + page + chunk_id/chunk_idx when available, but do not omit proposed_value when evidence is missing.
Quotes must be verbatim substrings of the chunk text. Avoid ellipses; if you cannot find a clean quote, leave evidence empty and set evidence_quality=weak/none with needs_more_evidence=true.
Always set evidence_quality to strong | weak | none. When evidence_quality != strong, include search_hints (keywords/sections/phrases) to help locate evidence later.
Return strict JSON:
{"proposals": [{"col_id": int, "proposed_value": string|null, "status": "found|inferred|not_found|unclear", "confidence": 0-1, "evidence_quality": "strong|weak|none", "evidence": [{"quote":string, "page":int, "chunk_id":string|null, "chunk_idx":int|null, "locator_hint":string|null}], "search_hints": [string], "needs_more_evidence": bool, "rationale": string}]}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
Retrieved chunks:
{{chunks}}
