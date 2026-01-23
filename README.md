# Paper Table Agent

Paper Table Agent is a local-first PDF→table pipeline that matches PDFs to table rows, proposes values for missing cells with evidence, and lets you review each proposal in a minimal Run/Review UI before exporting updates.

## Install

```bash
python --version  # requires >=3.10
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

## Quickstart

### Run the UI

```bash
paper-table-agent ui
```

The UI has two tabs: **Run** (select table + PDF folder) and **Review** (approve/reject proposals).

### Run the CLI

```bash
paper-table-agent init-config --output run_config.json
paper-table-agent run --config run_config.json
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

## Config (single source of truth)

All settings live in `run_config.json`. The UI reads defaults from this file but only overrides the table/PDF paths you select. Generate a starter config with `paper-table-agent init-config --output run_config.json`, or use `tests/fixtures/stub_run_config.json` for a deterministic, offline test run.

Debug-only artifacts (mapping report, proposals JSONL) are gated by `output.debug_reports=true` in the config.

## Diagnostics

```bash
paper-table-agent snapshot
paper-table-agent doctor
```

- `snapshot` writes a shareable project snapshot bundle under `runs/_diagnostics/latest_snapshot/`.
- `doctor` validates that README/specs reference real paths and CLI commands.

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
