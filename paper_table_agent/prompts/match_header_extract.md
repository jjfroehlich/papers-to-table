You are extracting paper metadata from PDF text.
Rules:
- Return JSON only. Do NOT include markdown, code fences, or <think>/<analysis> blocks.
- Do not add extra keys beyond the schema.
- Title must be a substring of the text.
- Authors must include at least one surname that appears in the text.
- Year must be a 4-digit year found in the text, or null.
Return JSON with: title, authors (list), year, doi (string or null), evidence (list of {quote, page, locator_hint}), confidence.
Text:
{{text}}
