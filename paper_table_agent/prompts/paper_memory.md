Summarize the paper into anchored notes for extraction.
Return JSON only (no markdown) in the form:
{"summary": "...", "notes": [{"anchor_id": "...", "note": "..."}]}
Rules:
- Keep the summary concise (<= 6 sentences).
- Notes must reference provided anchor_id values and be factual.
- Do not invent information; only use the provided anchors.

Document anchors:
{{document_anchors}}
