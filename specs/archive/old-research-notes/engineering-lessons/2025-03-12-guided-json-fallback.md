# Guided JSON fallback for LM Studio schema errors

## What changed
- Observed that LM Studio/llama.cpp rejects JSON schema response_format payloads when regex constraints are present, which previously caused extraction to fail across an entire run.
- Added schema sanitization and a guided JSON fallback to prompt-only JSON, with health-check detection that disables guided mode for the run if schema rejection is detected.
- Surfaced HTTP status + error substrings in proposal flags and review UI so operators see the true cause instead of a generic JSON error.

## Why it matters
Guided JSON failures were poisoning every extraction attempt. Detecting and disabling guided mode early keeps runs productive and makes errors diagnosable without digging through logs.

## Durable rule?
Yes. When enabling response_format/json_schema in new providers, always validate schema compatibility early and fall back to prompt-only JSON if the provider rejects the schema.

## Proposed update
Add a short note to the repo’s LLM provider guidance to require guided JSON health checks and schema sanitization for any new provider integration.
