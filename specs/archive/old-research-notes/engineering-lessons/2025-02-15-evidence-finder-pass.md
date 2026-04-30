# Compounding lesson: evidence finder pass for weak citations

## Context
Evidence validation was marking many proposals as weak or missing, leaving Review with low highlight coverage and limited context. This often stemmed from chunk-ID drift or quotes that were present elsewhere in the PDF but not in the retrieved subset.

## What changed
- Introduced an evidence finder pass that searches the full chunk table and page text for quotes when evidence is weak/none.
- Added token-level fuzzy highlighting to recover rectangles when exact matches fail.
- Persisted per-column extraction attempts with queries and outputs so failures are diagnosable.

## Why it matters
Separating value extraction from evidence attachment preserves proposal coverage while still improving reviewer trust when evidence can be found.

## Potential durable rule
**Evidence lookup should never be limited to retrieved chunks only.** Always validate against the full chunk table and allow a follow-up search pass when evidence is weak or missing.
