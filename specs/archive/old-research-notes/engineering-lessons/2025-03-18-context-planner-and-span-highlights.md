# Compounding lesson: context planning + span highlights

## What changed
- Added a context planner that selects fulltext, memory, or retrieval modes per PDF and batches columns column-first.
- Introduced a fulltext trimming ladder and memory notes with anchored quotes to keep prompts grounded under tight budgets.
- Switched highlight anchoring to span-first matching with stricter guardrails to avoid fuzzy letter soup.

## Lesson
Grounding degrades when prompts are truncated or stitched together from weak anchors; a deterministic context plan (fulltext → memory → retrieval) preserves evidence fidelity while keeping token usage predictable. Span-first highlighting keeps evidence readable and reviewable, and hard rejection criteria are essential to avoid misleading rectangles when the text is too short or too diffuse.
