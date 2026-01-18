# Changelog

## Unreleased

- Added completion markers so finished runs appear in Review dropdowns without exporting.
- Enforced evidence-first proposals: no proposed value without quote+page; unclear/no_evidence records persist per column.
- Strengthened matching with margin-based deterministic rule, adjudication validation, and repair retry.
- Added OCR-aware highlight fallback and cached highlight rectangles in stored evidence.
- Introduced per-column retrieval with retry on unclear results and configurable embedding/reranker backends.
- Added optional GROBID integration for structured metadata + section chunking (off by default).
- Updated Review UI with PDF dropdown and side-by-side proposal/evidence layout.
