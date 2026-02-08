# Compounding lesson: evidence quality floors + prompt caps

## What changed
- Raised default prompt caps and aligned context planning with effective token/char limits so whole-text/memory modes can run without silent truncation.
- Added evidence quality floors (header/footer detection, short-quote rejection) and stricter quote-only verification that downgrades weak `found` proposals to `inferred`.
- Reduced LLM call explosion by batching retrieval, caching per column batch, and skipping HyDE/query expansion for metadata-only fields.

## Lesson
When context limits are inconsistent across modules, long-document workflows silently degrade; make caps explicit, propagate them through planning, and surface them in run reports. Evidence systems also need a quality floor so failures are recoverable instead of misleading—treat weak anchors as retryable metadata, not as blocking errors, and couple strict verification to stored quotes so review decisions stay grounded.
