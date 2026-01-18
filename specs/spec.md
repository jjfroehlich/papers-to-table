# Spec: Paper Table Agent (LangGraph) — Batch PDF→Table Proposals with Evidence + Row Review (v0.3)

This v0.3 spec updates the previous version with:

* Proposal persistence fixes (never drop per-column records; store `unclear`/`no_evidence`).
* Matching stability: title+authors primary, year tie-breaker only; deterministic margin rule.
* Evidence highlighting hardening + OCR-aware fallback + cached rectangles in DB.
* Review UX redesign (row-by-row, Prev/Next per proposal, side-by-side layout).
* Dropdown-only run/PDF selection for review + advanced tools.
* Prompting upgrades (schema descriptions + few-shot examples + try-hard retrieval).
* Retrieval tuning (configurable embedding/reranker + debug view, dense path verified).
* Optional GROBID integration behind a flag.
* Explicit model routing config + caching strategy documentation.
* LangGraph nodes for parse→header→match→index→extract→persist with per-PDF and per-group checkpoints.

---

## 0) What we’re building

A local-first app that:

1. **Ingests a table** (XLSX/CSV) where each row is one publication and columns include at least title/authors/year.
2. **Ingests a folder of PDFs** (filenames unreliable).
3. For each PDF, **extracts title/authors/year** and matches it to a row via two-pass matching.
4. For each matched row, **extracts missing values** and stores them as **proposals** (never edits the original table during the run).
5. Every proposed cell includes **evidence** (quote + page + highlight rectangles). If evidence is weak or missing, the proposal is **unclear** and **needs_more_evidence**.
6. After the run completes, you review **row-by-row** in a UI: Accept / Accept-with-edit / Reject, with the PDF displayed and evidence highlighted.
7. Exports an updated table copy + audit logs.

---

## 1) Core policies

### 1.1 Locking

* Any cell is **locked** if it is non-empty and not exactly `" "` (single space).
* Locked cells are never overwritten during extraction.

### 1.2 Evidence requirement (P0)

* **No proposed value without quote+page.**
* If evidence is missing or can’t be located, proposal becomes `unclear` and `needs_more_evidence=true`.
* Every column in the target group produces a record even if status is `unclear` or `no_evidence`.

### 1.3 Values as text

All proposals stored and exported as text (even if numeric).

---

## 2) Matching PDF → Row (two-pass, deterministic-first)

### 2.1 Header extraction

Extract title/authors/year from the PDF content (GROBID header metadata if enabled, otherwise page text). Evidence includes quote + page.

### 2.2 Two-pass matching

**Pass 1 — deterministic shortlist**

* RapidFuzz title similarity + author last-name overlap.
* Year is optional and only a small tie-breaker bonus (missing year allowed).
* Deterministic rule: if the top candidate is **above threshold by margin** (and unique), status = `matched`.

**Pass 2 — LLM adjudication**

* Only invoked when the deterministic rule is not satisfied.
* LLM output must be strict JSON and internally consistent (validated; one repair retry).
* Never return `ambiguous` when there is only one candidate.

---

## 3) Proposal persistence

* Never silently drop LLM outputs due to schema mismatch.
* Store a per-column record in the database for every requested column, even if `unclear`/`no_evidence`.
* Cache resolved highlight rectangles in DB for speed.

---

## 4) Evidence highlighting

* Use **PyMuPDF search_for** with quote/page.
* If quote not found, try **locator_hint** keywords.
* If still not found, show the page **without** highlight and flag `needs_more_evidence=true`.
* OCR-heavy PDFs: when OCR is enabled, use token/word-box matches; otherwise show the page and flag `needs_more_evidence`.

---

## 5) Review UI (row-by-row)

* Run selection via dropdown **(completed runs only)**.
* PDF selection via dropdown within a run.
* Within a row, step through proposals with **Prev/Next**.
* Side-by-side layout: proposal panel + PDF panel with highlight.
* Decisions: **Accept**, **Accept-with-edit**, **Reject**.

Reject keeps the cell empty and eligible for future runs.

---

## 6) Retrieval + prompting upgrades (P2)

### 6.1 Prompting

* Always include **schema descriptions** for each column.
* Include **few-shot examples**: sample existing non-empty values for each column.
* “Try hard” strategy: **multi-query retrieval per column** + **second attempt** if first attempt yields `unclear`/`no_evidence`.
* Evidence rule enforced in post-processing.

### 6.2 Retrieval tuning

* Embeddings and reranker configurable with defaults.
* Dense retrieval must be used (unit/integration test asserts path runs).
* Debug view shows top chunks + scores + source pages.

---

## 7) GROBID integration (optional, OFF by default)

* Structured metadata: title/authors/abstract.
* Section segmentation (used to improve retrieval chunking).
* Optional reference parsing (for future use).
* Two supported modes:
  1. Local GROBID server URL (user provides).
  2. Docker-based local run instructions in README.

If GROBID is unavailable, system continues using existing PDF parsing.

---

## 8) LangGraph orchestration

Structured nodes:

`parse_pdf → extract_header → match_row → build_index → extract_group(s) → persist_results`

* Checkpoint after each PDF and each group extraction.
* LLM calls have strict JSON validation + one repair retry.

---

## 9) Model routing + caching

* Explicit model routing config for:
  * Header extraction
  * Match adjudication
  * Group extraction
  * Query expansion / HyDE
* Caching strategy:
  * Per-PDF retrieval index artifacts
  * Highlight rectangles cached in DB
  * Run checkpoints for resumability

---

## 10) Definition of done

* `pip install -e ".[test]"` works and `pytest -q` passes.
* Completed runs appear in Review dropdown.
* Review allows Prev/Next per proposal and shows PDF + highlight (or needs_more_evidence flag).
* Matching works when year is missing.
* Proposals are persisted and visible (even if unclear).
