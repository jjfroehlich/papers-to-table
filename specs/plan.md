# plan.md — Paper Table Agent (v0.4)

UI/UX iteration focused on lower friction, faster review, and explicit evidence handling.

## 1) Purpose

Deliver the v0.4 UI experience with Run/Review/Advanced/Settings/Help tabs, persistent session state, and optimized review flow.

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

- Add Run tab validation, schema source selection, run naming, model selection, retrieval presets, OCR/GROBID toggles.
- Add Settings tab for provider, model routing, performance controls.
- Add run status top bar and artifact path visibility.

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
