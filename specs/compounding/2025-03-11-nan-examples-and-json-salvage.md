# NaN prompt pollution and JSON salvage

## What happened

Retrieval prompts were being populated with NaN/empty examples, which polluted embedding queries and reduced recall. At the same time, local-model JSON outputs were failing validation more often due to fenced or mixed-format responses.

## Why it mattered

Embedding queries with literal “nan” strings dramatically reduce retrieval quality, leading to fewer proposals. Weak JSON parsing means valid responses are discarded, which further suppresses proposals and makes failures hard to debug.

## Fix

- Sanitize prompt inputs by dropping NaN/empty values and omitting examples when none remain.
- Harden JSON parsing by stripping fences, extracting the first JSON object, and logging raw responses and validation errors.
- Add optional LLM request/response recording for replay debugging.

## Durable rule?

Yes: always normalize prompt inputs before embedding or LLM calls, and log raw model outputs + validation errors to speed up diagnosis when parsers fail.
