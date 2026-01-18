# plan.md — Paper Table Agent (v0.3)

Batch PDF→Table proposals with evidence + post-run row review

## 1) Purpose

Implement the v0.3 spec with stability, evidence discipline, and a redesigned row review UI.

---

## 2) Guiding principles

1. **Durability first**: per-PDF + per-group checkpointing.
2. **Evidence first**: no proposed value without quote+page.
3. **Local-first**: offline defaults; cloud optional.
4. **Click/select UX**: dropdown-driven selections; no free-text except filters.
5. **Make failures visible**: needs_more_evidence flags, mapping report, OCR warnings.

---

## 3) Implementation milestones

### Milestone P0 — Stability & correctness

* Proposal persistence: store per-column records even if unclear/no_evidence.
* Matching: title+authors primary, year tie-breaker only, deterministic margin rule.
* Strict JSON adjudication with internal validator + single repair retry.
* Evidence highlighting: PyMuPDF search, locator_hint fallback, page-only fallback with needs_more_evidence.
* OCR-aware token/word-box highlighting when OCR enabled.
* GROBID extraction (optional) with structured header + section segmentation.

### Milestone P1 — UX overhaul

* Review dropdowns for completed runs + PDF selection.
* Row-by-row review with Prev/Next per proposal and side-by-side PDF panel.
* Accept / Accept-with-edit / Reject decisions only.

### Milestone P2 — Extraction quality upgrades

* Prompt upgrades (schema descriptions + examples + try-hard strategy).
* Per-column retrieval, second attempt on unclear/no_evidence.
* Embedding + reranker configuration with defaults; dense path test.
* Retrieval debug view includes scores + source pages.

### Milestone P3 — Optional GROBID integration

* Off by default; enable via config.
* Server URL option + Docker instructions in README.

---

## 4) LangGraph design

Structured nodes:

`parse_pdf → extract_header → match_row → build_index → extract_group(s) → persist_results`

* Checkpoint after each PDF and each group.
* Resume uses DB status + LangGraph checkpoints.

---

## 5) Testing strategy

* Unit: matching margin rule, evidence rules, retrieval dense path.
* Integration: mock LLM run end-to-end; completed runs appear in Review dropdown.
* UI smoke: review panel shows proposals + PDF highlight.

---

## 6) Documentation updates

* README updated with model routing, config, caching, reliability rules.
* Troubleshooting section updated for OCR and GROBID.
* CHANGELOG updated for user-facing changes.
