# Value-first proposals need explicit page inference for highlights

## What changed

When evidence quotes lacked page numbers or chunk IDs drifted, highlights routinely failed and proposals were downgraded or flagged as missing evidence. We updated the extraction/evidence flow to keep proposed values regardless of evidence strength, and we now infer missing page numbers from chunk metadata or fuzzy page-text matching before calling the highlighter.

## Why it mattered

Evidence gaps should not suppress proposals, but the review UX still depends on a usable page number to display the PDF and try highlights. Without page inference, evidence finder output stays unhighlighted even when the quote appears in the document.

## The fix

- Keep proposal status intact when evidence is weak/missing.
- Persist column descriptions as search hints and use them in evidence finder.
- Infer missing pages from chunk metadata or page-text fuzzy matching before highlight attempts.

## Follow-up question

Should we codify a durable rule in AGENTS.md that any evidence locator must attempt page inference from chunk metadata before declaring highlights missing?
