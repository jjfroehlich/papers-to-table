# plan.md — Paper Table Agent (v0.5)

UI/UX iteration focused on lower friction, faster review, explicit evidence handling, and LM Studio model-aware configuration.

## 1) Purpose

Deliver the v0.5 UI experience with Run/Review/Advanced/Settings/Help tabs, persistent session state, optimized review flow, and run-config-aligned model selection.

---

## 2) Guiding principles

1. **Click-first UI**: prefer dropdowns and pickers over free text.
2. **Trust by default**: show evidence + highlight status for every proposal.
3. **Fast review loop**: stepper, auto-advance, row navigation.
4. **Large-run safe**: lazy-load proposals per row; avoid rendering huge tables.
5. **Never lose state**: decisions written immediately; selections stored in session state.

---

## 3) Implementation milestones

### Milestone P0 — Run + Settings UX

- Replace table upload with path + browse selection in Run config.
- Add model registry refresh and LM Studio-aware model dropdowns.
- Align Run/Settings model options to run_config.json (including embedding/reranker backends/models).
- Ensure run execution status is shown after a run starts and visually separated from configuration.

### Milestone P1 — Review UX overhaul

- Two-panel review layout with row context and proposal stepper.
- Filters (status/confidence/columns/search), row navigation, completion indicators.
- Evidence list with highlight status, re-locate action, OCR notes.
- Auto-advance decisions and notes.

### Milestone P2 — Advanced + Help

- Matching diagnostics + retrieval diagnostics.
- Evidence locator tool.
- Help/Troubleshooting content.

---

## 4) Testing strategy

- UI smoke: run tab renders, review tab shows proposals, evidence viewer renders.
- Manual verification: decisions write immediately to DB and survive refresh.

---

## 5) Documentation updates

- README updated with new UI workflow and settings.
- CHANGELOG updated for user-facing UI changes.
