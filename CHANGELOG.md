# Changelog

## Unreleased

- Simplified the UI to Run/Review only with minimal inputs and step-through review decisions.
- Consolidated model/retrieval settings into a single config file with no UI tuning knobs.
- Added mock provider mode for deterministic test runs and query expansion/HyDE fallbacks.
- Simplified default outputs; extra exports are now gated behind a debug flag.
- Added run_report.json diagnostics with mapping/extraction/retrieval summaries and artifact paths.
- Mapping report now includes side-by-side PDF metadata vs row metadata.
- Evidence validation now requires chunk_id and verifies quote substring against stored chunks, with structured error flags.
- Retrieval presets (Fast/Balanced/Thorough) are explicit; missing embedding/reranker configs fall back to TF-IDF.
- Added a run bundle zip command and OCR metadata artifacts for easier diagnostics.
- Added completion markers so finished runs appear in Review dropdowns without exporting.
- Enforced evidence-first proposals: no proposed value without quote+page; unclear/no_evidence records persist per column.
- Strengthened matching with margin-based deterministic rule, adjudication validation, and repair retry.
- Added OCR-aware highlight fallback and cached highlight rectangles in stored evidence.
- Introduced per-column retrieval with retry on unclear results and configurable embedding/reranker backends.
- Added optional GROBID integration for structured metadata + section chunking (off by default).
- Updated the UI to use a single config-driven Run/Review flow with minimal controls.
- Added run-level sanity checks with diagnostics and FAILED status reporting when matched PDFs produce zero proposals.
- Added stub LLM + stub embeddings/reranker for deterministic offline tests and fixtures.
- Simplified run artifacts: pdf_row_matches.csv is required, mapping_report.html is debug-only.
- Added keyboard shortcuts and pending-only review queues for faster Review navigation.
