# tasks.md — Paper Table Agent (simplified spec)

Conventions:
- Use checkboxes.
- Tag tasks as **P0 / P1 / P2**.
- Reference concrete repo paths/modules.
- Include tests to add/update for each P0 area.

---

## P0 — Proposals appear + review works end-to-end (stub providers)

### [x] **P0.T0** Update spec/plan/tasks artifacts (`specs/spec.md`, `specs/plan.md`, `specs/tasks.md`)

### [x] **P0.T1** Fix “no proposals” root cause + sanity check diagnostics
**Paths**: `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py`
**AC**
- If matched_pdfs > 0 and proposals == 0: run_report marks FAILED and stores diagnostics (schema load, missing cells, extraction invoked).
- Diagnostic is logged and persisted in run_report.json.

### [x] **P0.T2** Minimal Review queue (matched rows only, pending-only)
**Paths**: `paper_table_agent/ui/app.py`, `paper_table_agent/ui/review_queue.py`
**AC**
- Review list only includes matched rows with pending proposals.
- Each row shows “N proposals pending.”
- Unclear/not_found proposals still appear when the cell is empty.

### [x] **P0.T3** Remove UI knobs + single settings source
**Paths**: `paper_table_agent/ui/app.py`, `paper_table_agent/ui/defaults.py`, `README.md`
**AC**
- UI shows only Run + Review tabs with two path pickers.
- No model/retrieval/OCR controls in UI.
- README notes that configuration lives in a single settings file.

### [x] **P0.T4** Stub providers + fixtures + CLI integration test
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/llm/embeddings.py`, `paper_table_agent/retrieval/*`, `tests/fixtures/*`, `tests/test_integration.py`
**AC**
- Stub LLM + embeddings/reranker run without external providers.
- CLI run uses fixtures and produces proposals for matched rows.

### [x] **P0.T5** Minimal export set
**Paths**: `paper_table_agent/graph/reporting.py`
**AC**
- Required exports: proposals.sqlite, updated_table.xlsx, audit_log.csv, pdf_row_matches.csv, run_report.json.
- mapping_report.html only in debug mode.

### [x] **P0.T6** Streamlit AppTest for Review
**Paths**: `tests/test_ui_streamlit.py`, `paper_table_agent/ui/app.py`
**AC**
- AppTest loads a completed run and renders a proposal in Review.
- Keyboard shortcuts and highlight-missing indicator are present.

---

## P1 — Optional improvements

### [ ] **P1.T1** Streamlit smoke test
**Paths**: `tests/test_ui_smoke.py`
**AC**
- Import app module without crash (skip if Streamlit test utils unavailable).
