# Compounding lesson: propose-first evidence flags

## Context
We observed runs where `proposed_value` ended up NULL because evidence validation failed or quote matching was imperfect. That hid useful candidate values in review and created a false sense of extraction failure.

## What changed
- Evidence validation now annotates proposals with flags (`evidence_missing`, `evidence_validation_errors`, `quote_has_ellipsis`) but no longer clears proposed values.
- Review uses evidence-strength badges to keep human attention on weak/missing evidence without hiding the values.
- Parsing health checks and OCR triggers reduce glued-token failures that caused quote mismatches.

## Why it matters
Evidence quality is a review affordance, not a gating mechanism. Preserving the model’s best-effort value makes the pipeline more useful even when highlighting is imperfect.

## Potential durable rule
**If the extractor produces a value, never null it due to evidence validation.** Instead, attach evidence quality flags and surface them in review UX.
