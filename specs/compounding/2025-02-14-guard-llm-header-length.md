# Guard LLM prompts with explicit length caps

## Context
A header-extraction LLM call failed with a 400 context-length error when the first two pages of a PDF produced too much text for the model's 4k token limit.

## Lesson
Even short-looking inputs (e.g., two PDF pages) can exceed smaller context windows once template instructions are included. Add explicit, configurable length caps before rendering prompts so the workflow fails gracefully and stays under model limits.

## Durable rule proposal
When introducing LLM calls that ingest raw document text, always include a configurable maximum character (or token) budget and log when truncation occurs.
