# Evidence validation should normalize quotes and enforce page ranges

## Context
We expanded evidence validation to support normalized matching (whitespace, hyphenation, ligatures) and to require that evidence.page falls within the retrieved chunk’s page range. This prevents false negatives from PDF quirks while tightening grounding to the correct page scope.

## Lesson
Evidence validation should be **forgiving to formatting artifacts** but **strict about page-range alignment**. Normalization avoids rejecting accurate quotes, while page-range checks prevent cross-page leakage that can mislead review.

## Impact
- Reduces spurious “quote not found” errors from hyphenation and ligature differences.
- Ensures locators and highlights operate on the intended page boundaries.
- Provides clearer run_report metrics for validation health.

## Possible durable rule
When evidence validation fails, **record both the validation mode (exact/normalized/failed) and the reason**, and always enforce that evidence.page is within the referenced chunk’s page range.
