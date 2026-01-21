# tasks.md — Paper Table Agent (simplified spec)

Conventions:
- Use checkboxes.
- Tag tasks as **P0 / P1 / P2**.
- Reference concrete repo paths/modules.
- Include tests to add/update for each P0 area.

---

## P0 — Simplified product (must not regress)

### [x] **P0.T0** Update spec/plan/tasks artifacts (`specs/spec.md`, `specs/plan.md`, `specs/tasks.md`)

### [x] **P0.T1** UI simplification: Run + Review only
**Paths**: `paper_table_agent/ui/app.py`
**AC**
- Exactly two screens (Run, Review).
- No Settings/Advanced/Help tabs or filter/search widgets.
- Review is row → column step-through with Accept / Accept-with-edit / Reject only.

### [x] **P0.T2** In-app path picker (no upload)
**Paths**: `paper_table_agent/ui/app.py`
**AC**
- Table/PDF inputs use an in-app file/directory browser.
- Last-used paths persist in `session_state`.

### [x] **P0.T3** Config consolidation (single source)
**Paths**: `paper_table_agent/config.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/ui/app.py`, `run_config.json`
**AC**
- Models/params only in config file.
- UI reads defaults but does not override model/retrieval/OCR/GROBID settings.

### [x] **P0.T4** Output simplification
**Paths**: `paper_table_agent/graph/exporter.py`, `paper_table_agent/graph/reporting.py`
**AC**
- Default outputs: proposals.sqlite, updated_table.xlsx, audit_log.csv, run_report.json.
- Extra exports (proposals.jsonl, pdf_row_matches.csv) gated behind a debug flag.

### [x] **P0.T5** Mock provider for deterministic tests
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/config.py`
**Tests**: `tests/test_integration.py`
**AC**
- Mock provider supports matching/extraction/query expansion/HyDE deterministically.
- Selectable via config (provider.mode = "mock").

### [x] **P0.T6** Regression tests
**Paths**: `tests/test_integration.py`, `tests/test_ui_defaults.py`
**AC**
- UI defaults load from config.
- Pipeline writes minimal artifacts and export outputs.
- Review decisions persist and update exports.

---

## P1 — Optional improvements

### [ ] **P1.T1** Streamlit smoke test
**Paths**: `tests/test_ui_smoke.py`
**AC**
- Import app module without crash (skip if Streamlit test utils unavailable).
