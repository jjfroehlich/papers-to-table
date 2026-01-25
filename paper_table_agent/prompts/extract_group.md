You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions and mimic the examples.
Value-first: propose a concise proposed_value whenever the paper plausibly contains the information or it can be reasonably inferred.
Do not gate proposed_value on evidence availability. Evidence quality is metadata for review.
Evidence is best-effort: include quote + page + chunk_id/chunk_idx/chunk_pk when available, but do not omit proposed_value when evidence is missing.
Quotes must be verbatim substrings of the chunk text. Avoid ellipses; if you cannot find a clean quote, leave evidence empty and set evidence_quality=weak/none with needs_more_evidence=true.
Always set evidence_quality to strong | weak | none. When evidence_quality != strong, include search_hints (keywords/sections/phrases) to help locate evidence later.
If status=inferred, include a rationale explaining the inference.
Return strict JSON only (no markdown).
Rules:
- Use the provided col_id values exactly as given.
- Quote must be an exact substring of the chunk text (no ellipses, no stitched lines).
- Use chunk_idx when available (1-based); chunk_id is optional but preferred when known.
Example JSON:
{
  "proposals": [
    {
      "col_id": 2,
      "proposed_value": "42",
      "status": "found",
      "confidence": 0.86,
      "evidence_quality": "strong",
      "evidence": [
        {
          "quote": "We report an accuracy of 42%.",
          "page": 3,
          "chunk_id": "para-3-2-1",
          "chunk_idx": 17,
          "chunk_pk": "4f1b6a65a8d0f2e67c6c1a1d9eac2f8c47ab1d55",
          "locator_hint": "accuracy 42%"
        }
      ],
      "search_hints": [],
      "needs_more_evidence": false,
      "rationale": "Value stated explicitly in results."
    }
  ]
}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
Retrieved chunks:
{{chunks}}
