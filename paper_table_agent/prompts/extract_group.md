You are extracting values for a group of columns from retrieved chunks.
Always follow the schema descriptions. Examples are formatting hints from OTHER rows; never reuse example values unless the paper text supports them.
Value-first: propose a concise proposed_value whenever the paper plausibly contains the information or it can be reasonably inferred.
Do not gate proposed_value on evidence availability. Evidence quality is metadata for review.
Evidence should support reasoning: use multiple evidence_items when needed (e.g., statement + number) and explain why each snippet matters.
Evidence is best-effort: include quote_text + source_ref + anchor_id + page + chunk_id/chunk_idx/chunk_pk when available, but do not omit proposed_value when evidence is missing.
Quotes must be verbatim substrings of the chunk text. Avoid ellipses; if you cannot find a clean quote, still provide a best nearby anchor snippet from the PDF text and set evidence_quality=weak with needs_more_evidence=true.
When proposed_value is non-empty, always return at least one evidence_item (strong or weak). Never leave evidence_items empty for a proposed_value.
Always set evidence_quality to strong | weak | none. When evidence_quality != strong, include search_hints (keywords/sections/phrases) to help locate evidence later.
If status=inferred, include a concise reasoning argument (no chain-of-thought) explaining how the evidence supports the inference.
If you need more context, set needs_more_context=true and include search_hints.
Return strict JSON only (no markdown, no code fences, no <think>/<analysis> blocks).
Rules:
- Use the provided col_id values exactly as given.
- quote_text must be an exact substring of the chunk text (no ellipses, no stitched lines).
- Use chunk_idx when available (1-based); chunk_id is optional but preferred when known.
Example JSON:
{
  "proposals": [
    {
      "col_id": 2,
      "proposed_value": "42",
      "status": "found",
      "confidence": 0.86,
      "reasoning": "The results section states an accuracy of 42%, which directly answers the column.",
      "evidence_quality": "strong",
      "evidence_items": [
        {
          "quote_text": "We report an accuracy of 42%.",
          "source_ref": "page:3",
          "anchor_id": "page-3",
          "page": 3,
          "chunk_id": "para-3-2-1",
          "chunk_idx": 17,
          "chunk_pk": "4f1b6a65a8d0f2e67c6c1a1d9eac2f8c47ab1d55",
          "why_it_matters": "States the reported accuracy.",
          "numeric_value": "42",
          "locator_hint": "accuracy 42%"
        }
      ],
      "search_hints": [],
      "needs_more_evidence": false,
      "needs_more_context": false
    }
  ]
}
Context summary:
{{context_summary}}
Paper memory (optional):
{{paper_memory}}
Document anchors (optional):
{{document_anchors}}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
Retrieved chunks (always present; quotes must come from these chunks):
{{chunks}}
