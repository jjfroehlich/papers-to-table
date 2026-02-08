You are extracting values for one or a small batch of columns from the provided context.
Examples are formatting hints from OTHER rows; never reuse example values unless the paper text supports them.
Value-first: propose a concise proposed_value whenever the paper plausibly contains the information or it can be reasonably inferred.
Do not gate proposed_value on evidence availability. Evidence quality is metadata for review.
Evidence is required for each proposal: include 1–3 evidence_items with page + quote_text + why_it_supports. Quotes must be verbatim substrings of the context payload.
If status=unknown, still provide the best available anchor quote if possible, or explain why none is available.
Return strict JSON only (no markdown, no code fences, no <think>/<analysis> blocks).
Rules:
- Use the provided col_id values exactly as given.
- quote_text must be an exact substring of the context payload (no ellipses, no stitched lines).
- Always include page numbers in evidence_items.
- If status=inferred, include concise reasoning (no chain-of-thought).
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
          "page": 3,
          "why_it_supports": "States the reported accuracy."
        }
      ],
      "search_hints": [],
      "needs_more_evidence": false,
      "needs_more_context": false
    }
  ]
}
Context mode:
{{context_mode}}
Context payload:
{{context_payload}}
Row context:
{{row_context}}
Columns (use col_id in responses):
{{columns}}
