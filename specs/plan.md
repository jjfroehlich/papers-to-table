# plan.md — Paper Table Agent (simplified product execution plan)

Phased implementation plan for the simplified “best possible extraction + simple review” product.
Each phase includes acceptance checks aligned with the v0.7 spec.

## Phase A — UI simplification (Run/Review only)

**Focus**
- Remove Advanced/Settings/Help tabs and all filtering widgets.
- Keep only Run + Review screens with minimal controls.
- Add in-app path picker (directory/file browser) for table/PDF paths.

**Acceptance checks**
- UI shows exactly **Run** and **Review**.
- Run screen has only table path + PDF folder path inputs with in-app picker.
- Review screen is step-through (row → column) with Accept / Accept-with-edit / Reject only.
- No confidence filters, search, column multi-select, or tuning controls.

---

## Phase B — Config consolidation + best defaults

**Focus**
- Single config object (pydantic settings/run_config.json) for models + retrieval params.
- UI reads defaults but never overrides model/retrieval/ocr/grobid settings.
- Use a single “optimal” retrieval profile and keep try-hard retry enabled.

**Acceptance checks**
- No UI model dropdowns or preset selectors.
- Retrieval config defaults match the single optimal profile.
- CLI uses the same config object for runs and resume.

---

## Phase C — Output simplification

**Focus**
- Keep primary outputs: proposals.sqlite, updated_table.xlsx, audit_log.csv, run_report.json.
- Keep mapping report for diagnostics but do not surface prominently in UI.
- Gate extra exports behind a debug flag.

**Acceptance checks**
- Default runs write only primary artifacts.
- Extra exports (proposals.jsonl, pdf_row_matches.csv) are only written when debug is enabled.

---

## Phase D — Testing strategy improvements

**Focus**
- Mock provider for deterministic JSON responses (matching, extraction, query expansion/HyDE).
- End-to-end pytest fixture using mock provider + tiny XLSX/PDF.
- Tests validate proposal persistence, evidence validation, export outputs, and review persistence.

**Acceptance checks**
- `pytest -q` passes in a mock-only environment.
- Integration test asserts: proposals for requested columns, evidence validation passes, updated_table.xlsx produced, reviews persist.
