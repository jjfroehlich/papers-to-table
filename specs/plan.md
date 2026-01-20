# plan.md — Paper Table Agent (v0.6)

Unified functional + UI/UX plan that prioritizes accurate extraction with evidence and a streamlined row-review experience.

## 1) Purpose

Deliver a single cohesive system that:
- Accurately matches PDFs to rows and extracts evidence-backed proposals.
- Persists proposals and evidence for reliable review.
- Provides a fast, low-friction UI for review and diagnostics.

---

## 2) Guiding principles

1. **Accuracy first**: evidence-backed values are mandatory.
2. **Deterministic where possible**: deterministic matching before LLM adjudication.
3. **Local-first & resumable**: checkpointing and cached artifacts for reliability.
4. **Fast review**: stepper + auto-advance + minimal typing.
5. **Large-run safe**: lazy-load, avoid massive table renders.

---

## 3) Implementation milestones

### Milestone P0 — Spec + data contracts

- Consolidate unified spec and update plan/tasks.
- Align proposal schema + evidence requirements with DB persistence.
- Confirm run outputs and artifact layout.

### Milestone P1 — Matching + extraction accuracy

- Two-pass matching with deterministic margin rule and LLM adjudication fallback.
- Duplicate detection + mapping report.
- Evidence-first extraction with needs_more_evidence rules.
- OCR fallback and highlight locator caching.

### Milestone P2 — Retrieval + parsing upgrades

- Per-PDF micro-index with hybrid retrieval and reranking.
- Multi-query + HyDE retrieval for high recall.
- Optional GROBID + table extraction integration.

### Milestone P3 — Review UI overhaul

- Two-panel row review layout with stepper, filters, row navigation.
- Evidence list + PDF highlights + relocate flow.
- Immediate persistence of decisions and review state.

### Milestone P4 — Advanced + Settings + Help

- Matching/retrieval diagnostics and evidence locator.
- Provider/model routing and performance controls.
- Troubleshooting guide and onboarding steps.

---

## 4) Testing strategy

- Unit tests for matching logic and proposal persistence.
- Integration tests for retrieval paths (dense + rerank enabled).
- UI smoke checks: run tab, review stepper, evidence rendering.

---

## 5) Documentation updates

- README updated for workflow changes and model configuration.
- CHANGELOG updated only for shipped user-facing changes.
