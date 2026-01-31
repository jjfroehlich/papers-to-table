# Paper Table Agent

Paper Table Agent is a local-first PDF→table pipeline that matches PDFs to table rows, proposes values for missing cells with evidence, and lets you review each proposal in a minimal Run/Review UI before exporting updates.

## Install

On Windows Git Bash, activate the venv with `source .venv/Scripts/activate`.

```bash
python --version  # requires >=3.10
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[test]"
```

## Quickstart

```bash
paper-table-agent --help
```

### Run the UI

```bash
paper-table-agent ui
```

### Headless UI smoke check (CI/Codex safe)

```bash
paper-table-agent ui --smoke
```

The UI has two tabs: **Run** (select table + PDF folder) and **Review** (approve/reject proposals).

### Run the CLI

```bash
paper-table-agent init-config --output run_config.json
paper-table-agent run --config run_config.json
```

### Deterministic stub run (no local LLM required)

```bash
paper-table-agent run --config tests/fixtures/stub_run_config.json
```

### Review + export

```bash
paper-table-agent export --run_dir runs/<timestamp>__<table>/
```

This writes `exports/updated_table.xlsx` and `exports/audit_log.csv` in the run directory.

### Bundle a run (optional)

```bash
paper-table-agent bundle --run_dir runs/<timestamp>__<table>/
```

## How it works

### Pipeline flow

1. Parse PDFs into text + layout tokens, then chunk text for retrieval.
2. Extract header metadata (title/authors/year) and match PDFs to table rows.
3. Retrieve evidence chunks and propose values with best-effort quotes + pages, then run an evidence finder pass for weak/none evidence.
4. Review proposals row-by-row in the UI and export updates.

### Evidence + review

- Proposals are value-first: infer a proposed value when plausible; evidence quality is metadata, not a hard gate.
- Review shows only matched rows and columns with proposed values, evidence, or explicit review flags.
- Evidence supports argumentation with multiple snippets when needed, and highlights can be re-located in UI (evidence finder).

## Config (single source of truth)

All settings live in `run_config.json`. The UI reads defaults from this file but only overrides the table/PDF paths you select. Generate a starter config with `paper-table-agent init-config --output run_config.json`, or use `tests/fixtures/stub_run_config.json` for a deterministic, offline test run.

Debug-only artifacts (mapping report, proposals JSONL) are gated by `output.debug_reports=true` in the config.

To capture raw LLM requests/responses for replay debugging, set `provider.record_requests=true`. This writes `logs/llm_records.jsonl` in the run directory unless you override `provider.record_path`.

Guided JSON (`provider.guided_json_mode`) uses response_format/json_schema when supported. In `auto`, guided mode is disabled for local/private endpoints or when health checks detect schema rejections, and prompt-only JSON remains the fallback.

## Troubleshooting

- **LLM endpoint errors**: confirm `provider.base_url` and models in `run_config.json` point to your backend (LM Studio/Ollama/OpenAI-compatible).
- **No proposals**: check `run_report.json` and `logs/run.log` for parsing/retrieval diagnostics, evidence-finder stats, and whitespace warnings.
- **Retrieval queries polluted with NaN/empty examples**: ensure the table schema and data use empty strings or known sentinels so prompts can omit empty examples cleanly.
- **Need more debug output**: enable `output.debug_reports=true` in your config.

## Repo structure (short)

- `paper_table_agent/`: pipeline + UI code
- `paper_table_agent/graph/`: LangGraph workflow, matching, extraction, reporting
- `paper_table_agent/ui/`: Streamlit UI
- `specs/`: product spec + plan + tasks (canonical)
- `tests/`: unit/integration tests

## Status

- Core pipeline runs end-to-end with stub providers and OpenAI-compatible backends.
- UI is minimal (Run + Review only) with config-driven behavior.
- Evidence is best-effort (values are preserved even when evidence is weak), with in-UI re-location for highlights.
- Evidence locator fills missing pages when possible and tries token-based highlight alignment.
- LLM capability probes route structured vs prompt-only JSON and retry on regex-constrained failures.
- Whole-text + paper-memory extraction is available behind config flags for proposal models that need broader context.

## Near-term to-dos

- Expand DOI-aware matching defaults based on real tables.
- Add more fixture PDFs for multi-column/scanned edge cases.
- Tune evidence search hints with more domain-specific phrases.
