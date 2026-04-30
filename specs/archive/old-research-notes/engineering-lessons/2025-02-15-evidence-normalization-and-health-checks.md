# Evidence normalization + health checks prevent silent empty proposals

## What happened
A real run produced matched rows but every proposal lacked evidence and values, with retries firing. The root causes were a combination of extraction group handling, overly strict quote validation against malformed PDF text, and missing health checks allowing LLM/embedding failures to masquerade as successful runs.

## Fix
- Normalized chunk text and quote validation consistently (raw + normalized), so missing spaces or ligatures no longer invalidate otherwise correct quotes.
- Preserved proposed values when evidence is missing, adding explicit failure reasons instead of nulling values.
- Added run health checks and retrieval fallbacks so LLM/embedding outages surface as run-level errors.
- Added debug extraction metrics to trace retrieval hits, extraction attempts, and top failure reasons per PDF.

## Impact
We now get actionable failure reasons in the UI and run report, and healthy runs produce populated proposals with evidence. When dependencies are down, the run stops with clear diagnostics instead of silently completing with empty proposals.

## Durable rule?
Yes: **always keep raw + normalized text variants and validate evidence using both**, and **treat dependency health as a first-class run status**. Consider adding a short rule to AGENTS.md under non-functional requirements about storing both raw/normalized text and exposing failure reasons when evidence is missing.
