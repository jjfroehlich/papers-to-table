# tasks.md — Paper Table Agent (v0.4)

UI/UX iteration with optimized review flow and settings.

Conventions:
* “AC” = Acceptance Criteria
* Update README during implementation (not only at the end)

---

## P0 — Run + Settings UX

### [x] T0.1 Run tab controls + validation

**Work**
* Add table uploader, schema source selection, run naming, mode toggle, OCR/GROBID toggles.
* Add retrieval presets and model dropdowns.
* Validation indicators + Start disabled until valid.

**AC**
* Run tab shows required controls and validates inputs before enabling Start.

---

### [x] T0.2 Settings tab model/provider routing

**Work**
* Add provider selection (LM Studio/Ollama/OpenAI-compatible).
* Add model routing dropdowns and performance controls.

**AC**
* Settings tab updates session state used by Run tab.

---

## P1 — Review UX overhaul

### [x] T1.1 Row review layout + filters

**Work**
* Two-panel layout with row context + proposal stepper.
* Status/confidence/column filters + search.
* Row navigation and completion indicators.

**AC**
* Review supports row-by-row navigation and filtering.

---

### [x] T1.2 Evidence viewer + decision controls

**Work**
* PDF viewer with highlight status and evidence list.
* Accept/Accept with edit/Reject + notes + needs-more-evidence toggle.
* Auto-advance toggle.

**AC**
* Decisions persist immediately and evidence panel updates highlights.

---

## P2 — Advanced + Help

### [x] T2.1 Advanced diagnostics

**Work**
* Matching diagnostics table.
* Retrieval diagnostics panel.
* Evidence locator tool.

**AC**
* Advanced tab shows diagnostics for selected run.

---

### [x] T2.2 Help/Troubleshooting content

**Work**
* Add 3-step startup guide and common failure modes.

**AC**
* Help tab contains required guidance and links.

---

## P3 — Docs

### [x] T3.1 README + CHANGELOG update

**Work**
* Update README status, UI workflow, and settings.
* Update CHANGELOG with UI/UX changes.

**AC**
* Docs reflect v0.4 UI.
