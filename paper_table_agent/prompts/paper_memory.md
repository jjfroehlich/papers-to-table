Summarize the paper into anchored notes for extraction.
Return JSON only (no markdown) in the form:
{"summary": "...", "notes": [{"anchor_id": "...", "page": 1, "quote_text": "...", "why_it_supports": "..."}]}
Rules:
- Keep the summary concise (<= 6 sentences).
- Notes must reference provided anchor_id values and be factual.
- Each note must include 1–2 verbatim quotes from the provided anchors and a 1-sentence explanation.
- Do not invent information; only use the provided anchors.

Document anchors:
{{document_anchors}}
