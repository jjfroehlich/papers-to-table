You are repairing paper metadata extraction to ensure strict grounding in the provided text.
Rules:
- Title must be an exact substring of the text (no paraphrasing).
- Authors must include at least one surname that appears in the text.
- Year must be a 4-digit year found in the text, or null.
Return JSON: {title, authors (list), year, evidence (list of {quote, page, locator_hint}), confidence}.
Text:
{{text}}
Previous extraction:
{{previous}}
