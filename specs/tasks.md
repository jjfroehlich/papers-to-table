# tasks.md — Paper Table Agent (v0.6)

Unified functional + UI/UX implementation tasks.

Conventions:
* “AC” = Acceptance Criteria
* Update README during implementation (not only at the end)

---

## P0 — Spec + data contracts

### [x] T0.1 Consolidate unified spec + plan + tasks

**Work**
* Merge functional + UI requirements into a single coherent spec.
* Update plan and tasks to reflect unified milestones.

**AC**
* spec.md, plan.md, tasks.md are aligned and consistent.

---

## P1 — Matching + extraction accuracy

### [ ] T1.1 Two-pass matching with deterministic margin rule

**Work**
* Implement deterministic RapidFuzz shortlist + margin rule.
* Fall back to strict-JSON LLM adjudication when needed.

**AC**
* Matching succeeds when year is missing; LLM only used when deterministic rule fails.

---

### [ ] T1.2 Duplicate detection + mapping report

**Work**
* Enforce one-PDF-per-row with duplicate flags.
* Generate mapping report with candidate tables.

**AC**
* mapping_report.html lists matched/ambiguous/unmatched counts and duplicates.

---

### [ ] T1.3 Evidence-first proposal persistence

**Work**
* Persist per-column records even when unclear/no-evidence.
* Cache highlight rectangles in DB.

**AC**
* Review UI shows proposals for all requested columns with evidence status.

---

## P2 — Retrieval + parsing upgrades

### [ ] T2.1 Per-PDF micro-index + hybrid retrieval

**Work**
* Implement per-PDF indexes with BM25 + dense embeddings.
* Add reranker pass with configurable model.

**AC**
* Retrieval diagnostics show BM25/dense/fused/rerank scores.

---

### [ ] T2.2 Multi-query + HyDE retrieval

**Work**
* Add query expansion and HyDE generation paths.
* Fuse results and rerank to final top M.

**AC**
* Retrieval pipeline supports multi-query and HyDE toggles.

---

### [ ] T2.3 Optional GROBID + table extraction

**Work**
* Support GROBID metadata extraction behind a flag.
* Integrate optional table extraction for evidence.

**AC**
* App runs without GROBID, and uses it when enabled.

---

## P3 — Review UI overhaul

### [ ] T3.1 Two-panel row review + stepper

**Work**
* Implement row context card, stepper, and decision controls.
* Add auto-advance and notes.

**AC**
* Users can step through proposals and persist decisions immediately.

---

### [ ] T3.2 Evidence list + PDF highlights

**Work**
* Show evidence list with go-to and re-locate actions.
* Render PDF highlights when rectangles are available.

**AC**
* Evidence highlights render for most proposals; fallback marks needs_more_evidence.

---

## P4 — Advanced + Settings + Help

### [ ] T4.1 Diagnostics + evidence locator

**Work**
* Expose matching diagnostics, retrieval diagnostics, and evidence locator UI.

**AC**
* Advanced tab surfaces matching/retrieval details for a selected run.

---

### [ ] T4.2 Provider/model routing + performance controls

**Work**
* Add Settings UI for provider and model routing.
* Add concurrency, retry, and caching controls.

**AC**
* Model routing is persisted in run_config.json and used during runs.

---

### [ ] T4.3 Help/Troubleshooting content

**Work**
* Add onboarding steps and common failure guidance.

**AC**
* Help tab shows onboarding steps and links to run folder/logs.
