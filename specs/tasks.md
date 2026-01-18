# tasks.md — Paper Table Agent (v0.3)

Batch PDF→Table proposals with evidence + post-run row review

Conventions:
* “AC” = Acceptance Criteria
* Keep prompts/templates in `paper_table_agent/prompts/`
* Update README during implementation (not only at the end)

---

## P0 — Stability & correctness

### [x] T0.1 Proposal persistence + evidence discipline

**Work**
* Ensure one record per column in each extraction group (including `unclear`/`no_evidence`).
* Enforce evidence rule: no proposed value without quote+page; otherwise `unclear` + `needs_more_evidence=true`.
* Never drop LLM outputs due to schema mismatch.

**AC**
* Review tab always lists proposals for each extracted column.
* Proposals with missing evidence are flagged and have no proposed value.

---

### [x] T0.2 Matching rule updates + JSON validation

**Work**
* Two-pass matching with title+authors primary; year as tie-breaker.
* Deterministic match requires margin over next candidate.
* Add internal adjudication validator + one repair retry.
* Never return `ambiguous` for single-candidate shortlist.

**AC**
* Matching works when year is missing.
* Deterministic matches recorded without LLM.

---

### [x] T0.3 Evidence highlighting fallback + OCR-aware tokens

**Work**
* Use PyMuPDF search_for with quote/page; fallback to locator_hint.
* If not found, show page without highlight and flag needs_more_evidence.
* Cache rectangles in DB.
* When OCR is enabled, use token/word-box matching for highlights.

**AC**
* Needs-more-evidence is set when highlights can’t be resolved.
* OCR PDFs still render page with evidence warnings.

---

### [x] T0.4 GROBID optional parsing

**Work**
* Add optional GROBID extraction (OFF by default).
* Capture structured header metadata and section segmentation.
* Persist GROBID artifacts and feed into matching/retrieval.

**AC**
* System runs without GROBID.
* When enabled, structured metadata improves header context.

---

## P1 — UX overhaul

### [x] T1.1 Review UI redesign

**Work**
* Completed runs only in Review dropdown.
* PDF dropdown within run.
* Row-by-row review with Prev/Next per proposal.
* Side-by-side layout: proposal panel + PDF highlight panel.
* Decisions: Accept, Accept-with-edit, Reject.

**AC**
* Review supports Prev/Next per proposal and shows PDF page/highlight.

---

## P2 — Extraction quality upgrades

### [x] T2.1 Prompt upgrades + try-hard strategy

**Work**
* Include schema descriptions for every column.
* Include few-shot examples per column.
* Per-column retrieval + second attempt on unclear/no_evidence.

**AC**
* Prompt includes schema and examples for each column.
* Retry path executes when evidence is unclear.

---

### [x] T2.2 Retrieval configurability + debug view

**Work**
* Embedding + reranker configurable with defaults.
* Dense retrieval path is exercised in tests.
* Debug view shows scores + source pages.

**AC**
* Tests confirm dense retrieval is active.

---

## P3 — Workflow & docs

### [x] T3.1 LangGraph structured nodes + per-group checkpointing

**Work**
* Implement nodes: parse_pdf → extract_header → match_row → build_index → extract_group(s) → persist_results.
* Checkpoint after each PDF and each group extraction.
* Ensure resume works.

**AC**
* Resume continues without duplicating proposals.

---

### [x] T3.2 README + CHANGELOG update

**Work**
* Update README (purpose, quickstart, config, reliability, troubleshooting).
* Document model routing + caching strategy + GROBID flag.
* Update CHANGELOG for user-facing changes.

**AC**
* Docs reflect new behavior and configuration.

---

## Testing

### [x] T4.1 Tests + verification

**Work**
* Update/extend unit tests for matching margin + evidence rules + retrieval dense path.
* Run `pip install -e ".[test]"` and `pytest -q`.

**AC**
* Tests pass locally.
