You are extracting paper metadata from PDF text.
Rules:
- Title must be a substring of the text.
- Authors must include at least one surname that appears in the text.
- Year must be a 4-digit year found in the text, or null.
Return JSON with: title, authors (list), year, evidence (list of {quote, page, locator_hint}), confidence.
Text:
{{text}}
