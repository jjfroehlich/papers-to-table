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

### [x] **P1.T3** Spec compliance documentation refresh
**Paths**: `specs/spec.md`, `docs/repo_audit.md`, `docs/spec_compliance_report.md`
**AC**
- Spec outputs align with actual run/export behavior.
- Repo audit includes pipeline stages + config validation locations.
- Spec compliance report exists and reflects current codebase.

### [x] **P1.T4** Implementation summary artifact
**Paths**: `exports/implementation_summary.md`
**AC**
- Summary documents changes, remaining tasks (if any), and how to run smoke/stub tests.

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
**Paths**: `scripts/tools/smoke_cli.sh`, `README.md`, `specs/*`
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

### [x] **P0.T28** Memory payload anchored to notes only
**Paths**: `paper_table_agent/graph/context_planner.py`, `tests/test_context_plan_integration.py`
**AC**
- Memory-mode extraction payload omits the summary and includes anchored notes only.
- Full paper-memory summary remains in artifacts for review.
- Test covers memory payload shape.
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
**Paths**: `paper_table_agent/cli.py`, `paper_table_agent/graph/evaluation.py`
**AC**
- `paper-table-agent eval` reports proposal count, evidence coverage, and highlight rate from proposals.sqlite.

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

### [x] **P0.T37** Run report includes capability probe summaries
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py`, `tests/test_run_report_capabilities.py`
**AC**
- LLM capability probe results (cached or fresh) are recorded per model.
- `run_report.json` surfaces `summary.llm_capabilities`.
- Test validates run report includes the capability summary.

---

## P0 — Constraints-off routing + evidence guardrails

### [x] **P0.T38** Constraints-off routing for LM Studio
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py`, `tests/test_llm_guided_json_fallback.py`
**AC**
- LM Studio base URLs force constraints-off mode (no response_format/json_schema/grammar/regex fields).
- Capability cache records supports_response_format_json_schema/grammar/regex as false and is written to run_report.
- Unit test asserts payloads omit response_format under constraints-off.

### [x] **P0.T39** Chunk identity uniqueness across PDFs
**Paths**: `paper_table_agent/retrieval/chunking.py`, `paper_table_agent/graph/extraction.py`, `tests/test_retrieval.py`
**AC**
- chunk_pk uses hash(pdf_id::chunk_id) to avoid collisions.
- Evidence stores pdf_id + chunk_id/chunk_idx for unambiguous lookups.
- Test validates chunk_pk differs across PDFs with identical chunk_id values.

### [x] **P0.T40** Evidence backfill + finder flags + run report metrics
**Paths**: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py`, `tests/test_evidence_finder.py`, `tests/test_integration.py`
**AC**
- Proposed values always carry at least one evidence item (strong or weak) via deterministic fallback.
- Evidence finder runs when missing/invalid/failed highlights and records attempted/succeeded/backfilled flags.
- run_report includes evidence coverage metrics and evidence_finder attempted rate.

### [x] **P0.T41** Highlight guardrails + rejection reasons
**Paths**: `paper_table_agent/pdf/highlight.py`, `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/graph/runner.py`, `tests/test_highlight.py`, `tests/test_evidence_finder.py`
**AC**
- Reject too-short quotes, excessive rect counts, and page-spanning rectangles with actionable reasons.
- Evidence records include highlight_strategy, match_score, and rejection reason when failed.
- Unit tests cover short-quote rejection and page-spanning rect rejection.

### [x] **P0.T42** Structured prompt budgeting + batching guarantees
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/prompts/extract_group.md`, `tests/test_llm_prompt_budget.py`
**AC**
- Prompt builder always includes retrieved chunks, trimming in order (chunk count → chunk text length → examples → column batching).
- All missing columns are attempted across batches (no silent drops).
- Unit test verifies chunk section presence under tiny budgets and batch coverage of col_ids.

### [x] **P0.T43** Evidence anchoring validation + quote source rules
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/graph/evidence_finder.py`, `tests/test_evidence_anchor.py`
**AC**
- quote_text for evidence comes from space-preserving text (`text`/`text_raw`) and not `text_norm`.
- status=`found` requires at least one evidence quote containing the proposed value (normalized equivalence allowed), else downgrade to inferred with needs_more_evidence.
- Unit test covers anchor downgrade and quote source.

### [x] **P0.T44** Constraints-off payload stripping + run diagnostics
**Paths**: `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py`, `tests/test_llm_guided_json_fallback.py`
**AC**
- Constraints-off backends never receive response_format/json_schema/grammar/regex/pattern fields (including retries).
- Capability probes record constraints_off flags in run_report.
- run_report includes extraction batch diagnostics + found-unanchored downgrade counts.

### [x] **P0.T45** Context planner + fulltext/memory/retrieval modes
**Paths**: `paper_table_agent/graph/context_planner.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/prompts/paper_memory.md`, `tests/test_context_planner.py`, `tests/test_context_plan_integration.py`
**AC**
- Context planner selects fulltext/memory/retrieval per PDF and batches columns column-first.
- Fulltext trimming ladder drops References first, then Acknowledgements, trims captions, and removes appendix/table blocks.
- Memory notes include page + verbatim quotes + why_it_supports and are logged in run_report.

### [x] **P0.T46** Column-first extraction + anchored evidence + span highlights
**Paths**: `paper_table_agent/graph/extraction.py`, `paper_table_agent/prompts/extract_column.md`, `paper_table_agent/pdf/highlight.py`, `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/graph/reporting.py`, `tests/test_llm_prompt_budget.py`, `tests/test_evidence_anchor.py`, `tests/test_context_plan_integration.py`
**AC**
- Extraction prompts operate column-first (or small batches) with context payloads and evidence-required outputs.
- Evidence quotes store span anchors (quote_start/quote_end) and use span-first highlighting with strict guardrails.
- Tests verify prompt batching under small budgets, quote span locating, and fulltext mode extraction produces evidence items.

---

## P0 — Two-tier testing + audit evaluation

### [x] **P0.T47** Audit mode extraction + evaluation harness
**Paths**: `paper_table_agent/config.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/evaluation.py`, `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/exporter.py`, `paper_table_agent/cli.py`, `tests/test_eval_harness.py`
**AC**
- Audit mode re-extracts filled cells and tags proposals with `proposal_kind=audit`.
- Audit proposals never export to tables.
- `paper-table-agent eval` writes proposal_eval.json/MD and updates run_report.json with audit/eval summaries.
- Tests cover evaluation metrics and audit export skip behavior.

### [x] **P0.T48** Live LM Studio E2E tests + synthetic fixtures
**Paths**: `tests/fixtures/build_fixture_pdfs.py`, `tests/test_live_llm_e2e.py`, `pyproject.toml`, `scripts/tools/live_llm_tests.sh`
**AC**
- Synthetic PDFs are generated at test time and include known facts.
- Live tests run only with `PTA_LIVE_LLM=1` and validate evidence anchoring + highlight guardrails.
- Pytest marker `live_llm` is registered and a convenience script runs live tests.

### [x] **P0.T49** Docs + spec updates for testing/eval workflows
**Paths**: `specs/spec.md`, `specs/plan.md`, `specs/tasks.md`, `README.md`, `docs/runbooks/TESTING.md`, `CHANGELOG.md`
**AC**
- Spec reflects two-tier testing, audit mode, eval artifacts, and run_report additions.
- README/runbook document hermetic vs live tests and eval usage.
- Changelog notes new eval command and audit-mode workflow.
