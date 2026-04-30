# Compounding lesson: prompt budgets + anchored values

## What changed
- Replaced naive prompt truncation with structured budgeting and column batching to keep retrieved chunks present and ensure all missing columns are attempted.
- Ensured evidence quotes are sourced from space-preserving chunk text and added a validator that downgrades “found” values lacking anchored quotes.
- Hardened constraints-off routing so incompatible backends never receive structured decoding payload fields, even in retries, and added extraction batch diagnostics to run reports.

## Lesson
Budgeting should be deterministic and section-aware: trim context in a controlled order and batch columns rather than dropping content. Evidence quality depends on readable, space-preserving quotes; using normalized text for anchoring can silently degrade highlights and trust. Finally, constraints-off needs to be absolute at the payload level—partial stripping still triggers backend regex/grammar failures.
