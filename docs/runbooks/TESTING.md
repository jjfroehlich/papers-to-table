# Testing & Evaluation Runbook (local iterative workflow)

## 1) Start LM Studio
- Launch LM Studio and start a server with a chat model for extraction/matching.
- Optional: load embedding models if you plan to run the full retrieval pipeline (TF-IDF works offline).

## 2) Configure environment variables
```bash
export PTA_LIVE_LLM=1
export PTA_LMSTUDIO_BASE_URL="http://localhost:1234/v1"
export PTA_LMSTUDIO_API_KEY=""  # optional
export PTA_LIVE_MODEL="qwen/qwen3-30b-a3b-2507"
export PTA_LIVE_CTX_WINDOW="32000"  # optional
export PTA_LIVE_TIMEOUT_S="180"     # optional
```

## 3) Run hermetic tests (no network)
```bash
pytest
```

## 4) Run live LM Studio tests
```bash
pytest -m live_llm
```

Optional convenience script (writes run reports under `runs/live_llm`):
```bash
scripts/tools/live_llm_tests.sh
```

## 5) Run a sample extraction locally
```bash
paper-table-agent run --config run_config.json
```

## 6) Evaluate audit proposals against filled cells
```bash
paper-table-agent eval --run_dir runs/<timestamp>__<table>/
```

Artifacts written:
- `proposal_eval.json`: summary + per-column metrics + bounded per-cell records.
- `proposal_eval.md`: human-readable summary report.
- `run_report.json`: updated with evaluation + audit summary.

To generate audit proposals during extraction, set in `run_config.json`:
```json
{
  "audit": {
    "use_filled_cells_as_gold": true
  }
}
```

## 7) Iterate
- Adjust schema definitions/examples or prompts as needed.
- Re-run the pipeline, then `paper-table-agent eval` to track improvements.

## 8) Capture a project snapshot (app state only)
```bash
paper-table-agent snapshot
```

The snapshot bundle includes specs/runbooks, run config, prompt templates, and a manifest of bundled files.

Include a run when needed:
```bash
paper-table-agent snapshot --include-run runs/<timestamp>__<table>/
```

To bundle run artifacts only (defaults to latest run):
```bash
paper-table-agent bundle
```
