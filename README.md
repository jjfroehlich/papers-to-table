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
3. Retrieve evidence chunks and propose values with quotes + pages.
4. Review proposals row-by-row in the UI and export updates.

### Evidence + review

- Proposals must include quote + page + chunk reference; missing evidence stays `unclear`.
- Review shows only matched rows and columns with proposals or evidence.
- Highlights are drawn on the PDF page when quotes are located.

## Config (single source of truth)

All settings live in `run_config.json`. The UI reads defaults from this file but only overrides the table/PDF paths you select. Generate a starter config with `paper-table-agent init-config --output run_config.json`, or use `tests/fixtures/stub_run_config.json` for a deterministic, offline test run.

Debug-only artifacts (mapping report, proposals JSONL) are gated by `output.debug_reports=true` in the config.

## Troubleshooting

- **LLM endpoint errors**: confirm `provider.base_url` and models in `run_config.json` point to your backend (LM Studio/Ollama/OpenAI-compatible).
- **No proposals**: check `run_report.json` and `logs/run.log` for sanity-check diagnostics.
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
- Debug outputs are opt-in via config.
