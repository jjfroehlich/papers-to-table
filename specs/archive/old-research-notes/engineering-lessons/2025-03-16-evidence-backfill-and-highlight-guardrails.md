# Compounding lesson: evidence backfill + highlight guardrails

## What changed
- Added a constraints-off routing layer for LM Studio-style backends to avoid structured decoding payloads that trigger regex/grammar failures.
- Made evidence identifiers globally unique by scoping chunk_pk with pdf_id and storing pdf_id on evidence items.
- Added deterministic weak-evidence backfill and highlight guardrails to prevent garbage rectangles.

## Lesson
Structured decoding assumptions leak across providers: the safest approach is to treat constrained decoding as a capability and make “constraints-off” absolute when a backend rejects schema/grammar. Evidence backfill and highlight validation should be deterministic and conservative; once evidence is missing or highlight quality is low, it is better to record a failure reason and attach a weak snippet than to show misleading highlights. This keeps proposals visible while maintaining trustworthy evidence artifacts.
