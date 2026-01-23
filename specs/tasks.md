# tasks.md — Paper Table Agent (current)

Conventions:
- Use checkboxes.
- Tag tasks as **P0 / P1 / P2**.
- Reference concrete repo paths/modules.
- Include tests to add/update for each P0 area.

---

## P0 — Repo hygiene + docs/spec alignment

### [x] **P0.T1** Create repo audit inventory
**Paths**: `docs/repo_audit.md`
**AC**
- Lists entrypoints, UI screens, persistence, run artifacts, docs map, and unused candidates.

### [x] **P0.T2** Gate debug-only outputs
**Paths**: `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/workflow.py`, `tests/test_integration.py`
**AC**
- `pdf_row_matches.csv` and `mapping_report.html` only written when `output.debug_reports=true`.
- Integration test updated to match default behavior.

### [x] **P0.T3** Docs + spec rewrite to match reality
**Paths**: `README.md`, `specs/spec.md`, `specs/plan.md`, `specs/tasks.md`
**AC**
- README is shorter and matches CLI/UI.
- Spec describes actual pipeline and outputs.

### [x] **P0.T4** Add doc/spec doctor command
**Paths**: `paper_table_agent/doctor.py`, `paper_table_agent/cli.py`, `tests/test_doctor.py`
**AC**
- `paper-table-agent doctor` validates README/spec references and exits non-zero on errors.
- Test covers success path.

### [x] **P0.T5** Remove unused scripts
**Paths**: scripts directory (removed)
**AC**
- Delete unreferenced helper scripts with no code/test usage.

---

## P1 — Optional improvements

### [ ] **P1.T1** Streamlit smoke test
**Paths**: `tests/test_ui_smoke.py`
**AC**
- Import app module without crash (skip if Streamlit test utils unavailable).
