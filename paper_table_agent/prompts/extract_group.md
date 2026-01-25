You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions and mimic the examples.
Value-first: propose a concise proposed_value whenever the paper plausibly contains the information or it can be reasonably inferred.
Do not gate proposed_value on evidence availability. Evidence quality is metadata for review.
Evidence is best-effort: include quote + page + chunk_id/chunk_idx/chunk_pk when available, but do not omit proposed_value when evidence is missing.
Quotes must be verbatim substrings of the chunk text. Avoid ellipses; if you cannot find a clean quote, leave evidence empty and set evidence_quality=weak/none with needs_more_evidence=true.
Always set evidence_quality to strong | weak | none. When evidence_quality != strong, include search_hints (keywords/sections/phrases) to help locate evidence later.
If status=inferred, include a rationale explaining the inference.
Return strict JSON:
{"proposals": [{"col_id": int, "proposed_value": string|null, "status": "found|inferred|not_found|unclear", "confidence": 0-1, "evidence_quality": "strong|weak|none", "evidence": [{"quote":string, "page":int, "chunk_id":string|null, "chunk_idx":int|null, "chunk_pk":string|null, "locator_hint":string|null}], "search_hints": [string], "needs_more_evidence": bool, "rationale": string}]}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
Retrieved chunks:
{{chunks}}
