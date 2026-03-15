# LLM prompt budgets + payload logs for local providers

## What changed
- Added payload logging to capture the exact JSON request sent to local OpenAI-compatible servers when debugging failures.
- Trimmed retrieved chunks before building extraction prompts so requests stay within configured token/character budgets.
- Recorded prompt-budget trims in run events and extraction attempts for operator visibility.

## Why it matters
Local servers like LM Studio can reject oversized prompts or structured-output constraints. Capturing payloads and enforcing budgets early makes failures reproducible and prevents llama.cpp truncation errors.

## Durable rule?
Yes. Always enforce prompt budgets before sending requests, and provide an opt-in payload log for debugging provider incompatibilities.

## Proposed update
Document payload logging and prompt budgets in the provider compatibility notes for future integrations.
