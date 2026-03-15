# Compounding lesson — ID normalization + ID-based extraction outputs

## What happened

Evidence validation was failing despite real quotes because LLM outputs sometimes used Unicode variants
(NBSP or non-breaking hyphen) for column or chunk identifiers. Those identifiers did not match stored
chunk IDs, so proposals were downgraded to “no evidence” even when quotes existed.

## Fix

We introduced a canonical `normalize_key` for identifiers, applied it to schema columns, internal
chunk IDs, and incoming LLM identifiers. We also moved extraction outputs to `col_id` + `chunk_idx`
so the model no longer emits free-text identifiers at all. This makes evidence mapping robust even
if the model returns unusual punctuation.

## Impact

- Proposals now retain valid evidence instead of being dropped.
- Evidence highlighting succeeds more consistently.
- Regression tests prevent Unicode drift from reappearing.

## Durable rule?

**Proposed rule**: Any identifier used for cross-component matching must use a canonical normalization
step (NFKC + whitespace/dash normalization), and model-facing prompts should use numeric IDs instead
of free-text identifiers wherever possible.
