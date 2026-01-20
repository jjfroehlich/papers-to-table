# Changelog

## Unreleased

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
- Updated the UI with Run/Review/Advanced/Settings/Help tabs, run validation gates, and enhanced review filters + evidence tools.
- Replaced table upload with path-based selection and added LM Studio model registry-aware embedding/reranker configuration.
