# tasks.md — Paper Table Agent (current)

Conventions:
- Use checkboxes.
- Tag tasks as **P0 / P1 / P2**.
- Reference concrete repo paths/modules.
- Include tests to add/update for each P0 area.

---

## P0 — Evidence-backed proposals + robust matching/retrieval

### [x] **P0.T1** Fix extraction groups default semantics
**Paths**: `paper_table_agent/graph/runner.py`, `tests/test_runner.py`
**AC**
- `extraction.groups=[]` still extracts all non-locked columns.
- Test covers default behavior.

### [x] **P0.T2** Normalize identifiers to prevent Unicode drift
**Paths**: `paper_table_agent/text/normalization.py`, `paper_table_agent/io/schema.py`, `paper_table_agent/graph/extraction.py`
**AC**
- `normalize_key` applied to schema columns and chunk IDs.
- Evidence validation tolerates dash/space variants.
- Tests cover NBSP + non-breaking hyphen.

### [x] **P0.T3** ID-based extraction outputs (col_id + chunk_idx)
**Paths**: `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/graph/extraction.py`, `paper_table_agent/llm/models.py`
**AC**
- Prompt uses `col_id` + `chunk_idx`.
- Proposals map back to canonical column names.
- Evidence stores `chunk_idx` and validates against stored chunks.

### [x] **P0.T4** Matching fallback + header grounding + report detail
**Paths**: `paper_table_agent/graph/matching.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py`, `paper_table_agent/prompts/match_header_repair.md`
**AC**
- Fallback adjudication attempted for plausible top scores.
- Header extraction repaired when substrings mismatch; deterministic fallback available.
- Mapping report shows top-5 candidates + adjudication status.

### [x] **P0.T5** Retrieval + parsing robustness
**Paths**: `paper_table_agent/retrieval/*`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py`
**AC**
- Chunking avoids tiny/huge chunks and uses stable chunk_idx.
- Embedding/reranker failures fall back to TF-IDF.
- Parsing sanity metrics recorded in `run_report.json`.
- Retrieval debug stored when debug reports or empty proposals.

### [x] **P0.T6** Highlight locator + review evidence UX
**Paths**: `paper_table_agent/pdf/highlight.py`, `paper_table_agent/ui/app.py`, `tests/test_highlight.py`
**AC**
- Quote locator retries normalized/locator/token strategies.
- Review shows highlights + “Locate highlight” action.
- Locator unit test passes on fixture PDF.

### [x] **P0.T7** Minimal UX + remove doctor command
**Paths**: `paper_table_agent/ui/*`, `paper_table_agent/cli.py`, `README.md`
**AC**
- UI remains Run + Review only; no extra model knobs.
- `doctor` command removed from CLI/docs/tests.

### [x] **P0.T8** Run sanity warnings + diagnostics
**Paths**: `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py`
**AC**
- Runs with matched PDFs but zero proposals marked `completed_with_warnings`.
- `why_no_values` diagnostics included in run report.

---

## P1 — Optional improvements

### [x] **P1.T1** Streamlit smoke test
**Paths**: `tests/test_ui_smoke.py`
**AC**
- Import app module without crash (skip if Streamlit test utils unavailable).

### [x] **P1.T2** LLM provider compatibility logging + prompt budgets
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/graph/extraction.py`, `paper_table_agent/graph/runner.py`, `tests/test_llm_prompt_budget.py`
**AC**
- LLM requests can record exact payloads for debugging.
- Prompt budgets trim retrieved chunks before requests to avoid context overflow.
- Regression test verifies extract prompt trimming under tight budgets.

---

## P0 — CLI install + smoke coverage

### [x] **P0.T9** Console script entrypoint verified
**Paths**: `pyproject.toml`, `paper_table_agent/cli.py`, `tests/test_cli_entrypoint.py`
**AC**
- `paper-table-agent` console script is registered in metadata.
- `paper_table_agent.cli:main` is the target entrypoint.

### [x] **P0.T10** Headless UI smoke mode
**Paths**: `paper_table_agent/cli.py`, `tests/test_ui_smoke.py`
**AC**
- `paper-table-agent ui --smoke` imports UI and exits 0 without launching Streamlit server.
- Pytest covers CLI smoke path with subprocess.

### [x] **P0.T11** Deterministic stub run integration test
**Paths**: `tests/fixtures/stub_run_config.json`, `tests/test_stub_run_cli.py`
**AC**
- Stub run produces at least one matched pdf→row, one proposal with non-empty proposed value, and one evidence-backed proposal.
- CLI run invoked in tests using temp output directory.

### [x] **P0.T12** Operator smoke script + docs update
**Paths**: `scripts/dev/smoke_cli.sh`, `README.md`, `specs/*`
**AC**
- Script provisions venv, installs editable + tests, and runs help/UI-smoke/stub run.
- README quickstart shows minimal Windows Git Bash path.

---

## P0 — Propose-first extraction + robust review UX

### [x] **P0.T13** Evidence annotation (do not gate proposed values)
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/ui/app.py`
**AC**
- Proposed values are preserved even when evidence is missing/weak.
- Evidence validation writes flags (`evidence_missing`, `quote_has_ellipsis`, `evidence_validation_errors`).
- Review UI shows evidence-strength badge.

### [x] **P0.T14** Parsing health checks + OCR fallback thresholds
**Paths**: `paper_table_agent/pdf/parser.py`, `paper_table_agent/pdf/ocr.py`, `paper_table_agent/graph/runner.py`
**AC**
- Page text preserves spaces via word reconstruction.
- Sanity metrics include whitespace ratio + avg token length.
- OCR triggers on low whitespace or glued tokens and logs warnings.

### [x] **P0.T15** Review navigation + constrained PDF pane
**Paths**: `paper_table_agent/ui/app.py`, `paper_table_agent/ui/review_queue.py`
**AC**
- Review shows matched rows with proposed values/evidence/needs_review.
- Prev/Next field navigation and auto-advance decisions.
- PDF pane constrained to viewport height with scrolling.

### [x] **P0.T16** DOI-aware matching bonus + header DOI extraction
**Paths**: `paper_table_agent/graph/matching.py`, `paper_table_agent/config.py`, `paper_table_agent/store/schema.sql`
**AC**
- DOI extracted from header text when available.
- DOI bonus improves deterministic candidate scoring when table has DOI column.

### [x] **P0.T17** Evidence finder pass + chunk table repair
**Paths**: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/graph/extraction.py`, `paper_table_agent/store/schema.sql`
**AC**
- Evidence finder runs for weak/none evidence and attaches quotes/pages/highlights.
- Chunk validation repairs unknown chunk references via fuzzy matching or quote search.

### [x] **P0.T18** Chunk table canonicalization
**Paths**: `paper_table_agent/retrieval/chunking.py`, `paper_table_agent/store/db.py`
**AC**
- Chunks persist chunk_pk, chunk_type, and text_norm in DB.
- Evidence validation checks against full chunk table, not retrieved subset.

### [x] **P0.T19** Deterministic hash retrieval backends
**Paths**: `paper_table_agent/llm/embeddings.py`, `paper_table_agent/retrieval/*`, `tests/*`
**AC**
- embedding_backend/reranker_backend support `hash` for offline tests.
- Retrieval tests validate hash backend end-to-end.

### [x] **P0.T20** Extraction attempt diagnostics
**Paths**: `paper_table_agent/store/schema.sql`, `paper_table_agent/graph/runner.py`
**AC**
- Per-column retrieval/extraction attempts persisted with queries, debug, and raw outputs.

### [x] **P0.T21** Value-first extraction + inferred rationale
**Paths**: `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/graph/extraction.py`
**AC**
- Extraction keeps proposed values even when evidence is missing.
- Inferred proposals include rationale and search hints.
- Evidence quality is metadata, not a hard gate.

### [x] **P0.T22** Evidence locator fallbacks + page inference
**Paths**: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/graph/runner.py`
**AC**
- Evidence finder uses column description + hints to search full chunk table.
- Missing page numbers are inferred from chunk metadata or page text.
- Highlight attempts record strategy + status even when missing.

### [x] **P0.T23** Chunk table stability + page chunks for every page
**Paths**: `paper_table_agent/retrieval/chunking.py`
**AC**
- Always create page chunks, even for sparse pages.
- Store compact normalization for matching in `text_norm`.

### [x] **P0.T24** Review skim navigation + PDF pane sizing
**Paths**: `paper_table_agent/ui/app.py`
**AC**
- Prev/Next proposal navigation available without decision.
- PDF pane scrolls within a constrained height.

### [x] **P0.T25** Run report fallback visibility
**Paths**: `paper_table_agent/graph/reporting.py`
**AC**
- Run report includes embedding/reranker/retrieval fallback events.

## P2 — Regression fixtures + highlight coverage

### [x] **P2.T1** Parsing/tokenization regression test
**Paths**: `tests/test_parsing_quality.py`
**AC**
- Fixture parsing meets whitespace ratio + token length thresholds.

### [x] **P2.T2** Highlight locator handles ellipsis fragments
**Paths**: `paper_table_agent/pdf/highlight.py`, `tests/test_highlight.py`
**AC**
- Ellipsis quote fragments still locate a bbox in fixtures.

### [x] **P2.T3** Stub run produces multiple values + highlightable evidence
**Paths**: `tests/test_stub_run_cli.py`
**AC**
- Stub run yields >=3 proposed values and at least one highlightable bbox.

---

## P0 — LLM robustness + evidence upgrades

### [x] **P0.T26** JSON extraction hardening for messy model outputs
**Paths**: `paper_table_agent/llm/client.py`, `tests/test_llm_json_parsing.py`
**AC**
- JSON parsing extracts last fenced block or balanced span before repair.
- Leading commentary does not block header/mapping parsing.
- Unit tests cover GLM-style output with leading text.

### [x] **P0.T27** Regex-400 fallback + capability probes
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py`, `tests/test_llm_guided_json_fallback.py`
**AC**
- HTTP 400 regex/grammar errors retry with constraints-off prompt-only mode.
- Per-model capability probes cache guided vs prompt-only JSON support.
- Debug logs include constraint mode and payload flags.

### [x] **P0.T28** Context assembly + summaries for extraction
**Paths**: `paper_table_agent/retrieval/pipeline.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/prompts/summarize_sections.md`
**AC**
- Retrieval expands neighbor windows and optional section chunks before token trimming.
- Summary prompt provides broader paper context for extraction.
- Retry-on-unclear uses expanded context with summaries.

### [x] **P0.T29** Evidence schema upgrades + highlight robustness
**Paths**: `paper_table_agent/llm/models.py`, `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/pdf/highlight.py`, `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/ui/app.py`
**AC**
- Proposal evidence supports multi-snippet `evidence_items` with quote_text/source_ref/why_it_matters.
- Highlighting falls back to page-text normalized/fuzzy matches when exact fails.
- UI surfaces per-evidence why_it_matters + numeric_value.

### [x] **P0.T30** Proposal evaluation harness
**Paths**: `scripts/dev/eval_proposals.py`
**AC**
- Script reports proposal count, evidence coverage, and highlight rate from proposals.sqlite.

---

## P0 — Whole-text proposals + backend compatibility

### [x] **P0.T31** Spec-driven proposal model + anchored evidence contract
**Paths**: `specs/spec.md`, `paper_table_agent/llm/models.py`, `paper_table_agent/prompts/extract_group.md`
**AC**
- Spec defines proposal model inference behavior + anchored evidence requirements.
- Proposal schema includes rationale, confidence grading, and anchored evidence_items.
- Prompts explicitly ban wrappers (`<think>`, code fences) for JSON outputs.

### [x] **P0.T32** GLM-safe header extraction parsing + prompt hardening
**Paths**: `paper_table_agent/prompts/match_header_extract.md`, `paper_table_agent/llm/client.py`, `tests/test_llm_json_parsing.py`
**AC**
- Header extraction prompt requires JSON-only output with no `<think>` or code fences.
- Parser tolerates wrapped outputs (strip `<think>` blocks + fenced JSON).
- Test covers GLM-style wrapped output for header extraction.

### [x] **P0.T33** Backend compatibility probe + regex incompat classification
**Paths**: `paper_table_agent/graph/runner.py`, `paper_table_agent/llm/client.py`, `paper_table_agent/graph/reporting.py`
**AC**
- Startup probe validates model/backend compatibility and records failures in run report.
- Regex/grammar 400 errors are classified as `model_incompatible_backend_regex`.
- UX surfaces actionable fallback guidance.

### [x] **P0.T34** Whole-text + paper-memory extraction (feature-flagged)
**Paths**: `paper_table_agent/config.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/extraction.py`
**AC**
- Feature flag enables whole-text packaging or memory+retrieval fallback when context is too large.
- Evidence anchors include page + quote text for deterministic highlighting.
- Retry-on-unclear uses expanded anchors or memory refresh.

### [x] **P0.T35** Evidence anchoring + highlight reliability improvements
**Paths**: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/pdf/highlight.py`, `paper_table_agent/graph/runner.py`
**AC**
- Fix page_outside_chunk occurrences via anchor/page resolution.
- Evidence finder avoids irrelevant evidence with term/units filters or anchor matching.
- Missing highlights record clear status and retry paths.

### [x] **P0.T36** Diagnostics + provenance artifacts
**Paths**: `paper_table_agent/store/schema.sql`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py`
**AC**
- Per-stage LLM metadata (model, tokens, truncation) recorded per attempt.
- Per-proposal provenance records which anchors/chunks were supplied.
- Debug flag gates full response capture for reproducibility.
