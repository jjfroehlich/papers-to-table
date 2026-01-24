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
