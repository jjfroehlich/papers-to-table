# Paper-table-agent

Paper-table-agent is an experimental local-first pipeline to extract and organize information from research papers using large language models. 

## How to use it
Input: 
 - a .xlsx table with one row per paper, columns Title/Authors/Year and a column for each of the desired information. Optional: an extra tab with a brief description of what each column should capture. Optional: some cells in the main table manually populated, as examples for the extraction language model. 
 - a folder with .pdf files of papers. 
 
 The app first matches .pdfs to rows, then extracts values for each cell, and lets you review each proposed value in a minimal Run/Review UI together with reasoning and evidence.

## Installation

1. Clone the repo:
```bash
git clone https://github.com/jjfroehlich/paper-table-agent
cd paper-table-agent
```
2. Create the virtual environment and install dependencies:
```bash
# Verify python version (requires >=3.10)
python --version  

# Create virtual environment (run once)
python -m venv .venv

# Activate the environment (Windows Git Bash)
source .venv/Scripts/activate
# Note: For PowerShell use: .venv\Scripts\Activate.ps1

# Install package and dependencies (run once)
pip install -e ".[test]"
```

You also need LM Studio, models specialized in embedding (e.g. text-embedding-nomic-embed-text-v1.5, text-embedding-bge-small-en-v1.5), and a capable model for extraction and reasoning (e.g. qwen/qwen3-30b-a3b-2507). Optional: LM Studio can also be connected to more capable cloud-based models (e.g. Gemini Pro 3, GPT-5.2) with API keys.

## Quickstart
```bash
# Activate Environment
source .venv/Scripts/activate

# Run the UI
paper-table-agent ui
```

The UI has two tabs: **Run** (select table + PDF folder) and **Review** (approve/reject proposals).


## Terminal CLI 
### Help
```bash
paper-table-agent --help
```

### Run 
```bash
paper-table-agent init-config --output run_config.json
paper-table-agent run --config run_config.json
```

### Review + export
```bash
paper-table-agent export --run_dir runs/<timestamp>__<table>/
```

This writes `exports/updated_table.xlsx` and `exports/audit_log.csv` in the run directory.

###  For development
```bash
# Headless UI smoke check
paper-table-agent ui --smoke

# Stub run, no LLM required
paper-table-agent run --config tests/fixtures/stub_run_config.json

# Bundle a run 
paper-table-agent bundle --run_dir runs/<timestamp>__<table>/

# Bundle a snapshot of the app
paper-table-agent snapshot
```

## How it works technically

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

All settings live in `run_config.json`. The UI reads defaults from this file but only overrides the table/PDF paths you select. 

Generate a starter config with `paper-table-agent init-config --output run_config.json`.

Debug-only artifacts (mapping report, proposals JSONL) are gated by `output.debug_reports=true` in the config.

To capture raw LLM requests/responses for replay debugging, set `provider.record_requests=true`. This writes `logs/llm_records.jsonl` in the run directory unless you override `provider.record_path`.

Guided JSON (`provider.guided_json_mode`) uses response_format/json_schema when supported. In `auto`, guided mode is disabled for local/private endpoints or when health checks detect schema rejections, and prompt-only JSON remains the fallback.


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
- Evidence locator fills missing pages when possible, backfills weak evidence snippets, and rejects low-quality highlight candidates.
- LLM capability probes route structured vs prompt-only JSON, with constraints-off mode for LM Studio-style backends.
- Whole-text + paper-memory extraction is available behind config flags for proposal models that need broader context.
- Context planning chooses fulltext/memory/retrieval per PDF and drives column-first extraction with anchored evidence.
