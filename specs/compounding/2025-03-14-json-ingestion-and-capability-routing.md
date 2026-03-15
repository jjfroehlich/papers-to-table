# JSON ingestion + capability routing for mixed LLM backends

## What changed
- Added JSON extraction that prefers the last fenced block or first balanced JSON span before any repair attempts, so models that prepend commentary no longer zero out downstream stages.
- Implemented regex/grammar 400 retry that strips constrained decoding fields and switches to strict prompt-only JSON.
- Added per-model capability probes to cache structured-output support and route each stage to guided or prompt-only JSON accordingly.

## Why it matters
Different local backends (LM Studio, llama.cpp derivatives) reject regex-based schemas or prepend extra text. Without robust ingestion + per-model routing, entire runs can fail before extraction, even when models are otherwise capable.

## Durable rule?
Yes. Treat structured-output features as optional per model/backend, probe them early, and always keep a prompt-only fallback plus robust JSON extraction.

## Proposed update
Add a short provider checklist in docs/runbooks to require capability probes and prompt-only fallbacks for any new LLM backend.
