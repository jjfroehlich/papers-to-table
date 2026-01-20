# plan.md — Paper Table Agent (forever spec execution plan)

Phased implementation plan grounded in current repo state. Each phase includes measurable acceptance checks.

## Phase 0 — Packaging/install + tests + smoke run

**Focus**
- Validate installability, test harness, and CLI/UI entrypoints.

**Acceptance checks**
- `pip install -e ".[test]"` succeeds.
- `pytest -q` passes.
- `paper-table-agent ui` launches Streamlit without crashing.
- `paper-table-agent run --config run_config.json` completes and writes a run folder.

---

## Phase 1 — Correctness regressions (matching consistency, evidence validation, proposal persistence)

**Focus**
- Enforce matching consistency rules and deterministic-first behavior.
- Enforce evidence validation (quote+page+chunk_id substring) and highlight status.
- Persist per-column proposals even on malformed LLM output; record structured errors.

**Acceptance checks**
- Matching JSON rejects ambiguous+row_id and row_id without matched.
- When only one plausible candidate exists, ambiguous is coerced to matched with warning.
- Proposals exist for every requested column, even on LLM failure.
- Evidence validation forces unclear when quote not in chunk; error metadata is persisted.

---

## Phase 1.5 — Spec consistency + verify semantics + evidence normalization

**Focus**
- Align verify-only review semantics with the three-decision rule.
- Normalize evidence validation (exact vs normalized) and enforce chunk page ranges.
- Ensure run_report metrics are comprehensive and logged.

**Acceptance checks**
- Verify-only review semantics are documented and map to Accept/Accept-with-edit/Reject.
- Evidence validation supports exact vs normalized matching and enforces page-range checks.
- run_report includes fill rate, evidence validation pass rate, highlight success rate, ambiguous mapping rate, and per-column not_found rates.

---

## Phase 2 — Retrieval + prompting upgrades (“try hard”, multi-query, rerank) + metrics

**Focus**
- Implement explicit Fast/Balanced/Thorough retrieval presets.
- Ensure multi-query + HyDE + rerank are active for Balanced/Thorough.
- Track retrieval stats in run_report and Advanced diagnostics.

**Acceptance checks**
- Retrieval presets set explicit topK/query_variants/rerank values.
- Balanced/Thorough use query expansion + HyDE; Fast does not.
- run_report.json includes retrieval configuration and summary stats.

---

## Phase 3 — Highlight locator robustness + caching + “try re-locate”

**Focus**
- Ordered locator steps (exact → normalized → hint → pdfplumber tokens → OCR tokens).
- Cache highlight rectangles in DB and reuse in Review.
- Add “Try re-locate” action for evidence in UI.

**Acceptance checks**
- Evidence records include highlight_status and strategy.
- Cached rectangles are reused in Review without re-search.
- “Try re-locate” updates evidence and flags immediately.

---

## Phase 4 — UI/UX improvements (review speed + diagnostics)

**Focus**
- Maintain v0.5/v0.6 review UX while surfacing mapping + evidence diagnostics.
- Improve review filters and row navigation for large runs.

**Acceptance checks**
- Review tab supports Accept/Accept-with-edit/Reject only.
- Mapping diagnostics show side-by-side PDF metadata vs row metadata.
- Advanced tab exposes matching/retrieval/evidence locator panels.

---

## Phase 5 — Optional integrations (GROBID, OCR improvements)

**Focus**
- Optional GROBID metadata + sectioning.
- OCR quality and token alignment improvements.

**Acceptance checks**
- Runs succeed with or without GROBID enabled.
- OCR fallback triggers when pages are sparse and records OCR provenance.
