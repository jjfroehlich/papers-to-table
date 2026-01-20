# tasks.md — Paper Table Agent (forever spec)

Conventions:
- Use checkboxes.
- Tag tasks as **P0 / P1 / P2**.
- Reference concrete repo paths/modules.
- Include tests to add/update for each P0 area.

---

## P0 — Correctness + persistence (must not regress)

### [x] **P0.T0** Update spec/plan/tasks artifacts (`specs/spec.md`, `specs/plan.md`, `specs/tasks.md`)

### [x] **P0.T1** Matching consistency + coercion guardrails
**Paths**: `paper_table_agent/graph/matching.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/prompts/match_adjudicate.md`
**Tests**: `tests/test_matching.py`
**AC**
- `ambiguous` never returns a `row_id`.
- If `row_id` is present, status is `matched`.
- Single plausible candidate is coerced to matched with warning.

### [x] **P0.T2** Evidence validation w/ chunk_id + substring rule
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/llm/models.py`, `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/prompts/verify_cell.md`, `paper_table_agent/store/schema.sql`, `paper_table_agent/store/db.py`
**Tests**: `tests/test_extraction.py`
**AC**
- Proposals with missing/invalid evidence are forced to `unclear`.
- Evidence includes `chunk_id`; quote must be substring of chunk.
- Validation errors are persisted in flags.

### [x] **P0.T3** Proposal persistence + structured error metadata
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/llm/client.py`
**Tests**: `tests/test_extraction.py` (error metadata) + `tests/test_matching.py`
**AC**
- Every requested column persists a proposal record even on LLM failure.
- Error metadata includes `error_type`, `raw_output`, `repair_attempted`.

### [x] **P0.T4** Mapping report + run_report.json diagnostics
**Paths**: `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/store/db.py`, `paper_table_agent/store/schema.sql`
**Tests**: (add integration test if feasible)
**AC**
- Mapping report shows side-by-side PDF vs row metadata + candidates.
- `run_report.json` summarizes config, stats, and artifact paths.

### [x] **P0.T4a** Integration test fixture (tiny table + PDFs)
**Paths**: `tests/test_integration.py`
**Tests**: `pytest tests/test_integration.py::test_integration_run_report_and_validation -q`
**AC**
- Builds a tiny table + schema + 1–2 PDFs.
- Runs pipeline in a temp run directory.
- Asserts proposals per requested column, run_report exists, mapping report exists, and evidence validation passes at least one known case.

### [x] **P0.T5** Retrieval presets + backend fallback
**Paths**: `paper_table_agent/ui/app.py`, `paper_table_agent/graph/runner.py`
**Tests**: (add unit test for presets if feasible)
**AC**
- Fast/Balanced/Thorough set explicit topK/query variants/HyDE/second-pass.
- Missing embeddings/reranker fall back to BM25-only with warnings.

### [x] **P0.T6** README update (setup + retrieval configs)
**Paths**: `README.md`
**AC**
- LM Studio/Ollama setup is explicit.
- Embedding/reranker configuration and fallback documented.
- run_report.json described.

---

## P1 — Retrieval + diagnostics depth

### [x] **P1.T1** “Try hard” second-pass extraction improvements
**Paths**: `paper_table_agent/graph/runner.py`, `paper_table_agent/retrieval/pipeline.py`
**AC**
- Second pass uses expanded retrieval settings with clear logging.

### [x] **P1.T2** Run bundle artifact
**Paths**: `paper_table_agent/graph/reporting.py`, `paper_table_agent/cli.py`
**AC**
- `run_bundle.zip` collects run_report, mapping report, logs, and exports.

### [x] **P1.T3** UI diagnostics wiring
**Paths**: `paper_table_agent/ui/app.py`
**AC**
- Advanced tab surfaces run_report summary + retrieval diagnostics + evidence locator.

---

## P2 — Optional integrations + UX polish

### [x] **P2.T1** GROBID + OCR enhancements
**Paths**: `paper_table_agent/pdf/grobid.py`, `paper_table_agent/pdf/ocr.py`
**AC**
- Runs succeed with optional GROBID/OCR toggles.

### [ ] **P2.T2** Review speed polish
**Paths**: `paper_table_agent/ui/app.py`
**AC**
- Keyboard shortcuts documented and consistent across sessions.
