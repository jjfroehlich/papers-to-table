#!/usr/bin/env bash
set -euo pipefail

export PTA_LIVE_LLM=1
export PTA_LMSTUDIO_BASE_URL="${PTA_LMSTUDIO_BASE_URL:-http://localhost:1234/v1}"
export PTA_LIVE_MODEL="${PTA_LIVE_MODEL:-qwen/qwen3-30b-a3b-2507}"
export PAPER_TABLE_AGENT_RUNS_ROOT="${PAPER_TABLE_AGENT_RUNS_ROOT:-runs/live_llm}"

pytest -m live_llm

if [ -d "$PAPER_TABLE_AGENT_RUNS_ROOT" ]; then
  latest_run="$(ls -1 "$PAPER_TABLE_AGENT_RUNS_ROOT" | sort | tail -n 1)"
  if [ -n "$latest_run" ]; then
    report_path="$PAPER_TABLE_AGENT_RUNS_ROOT/$latest_run/run_report.json"
    if [ -f "$report_path" ]; then
      echo "Latest run report summary:"
      REPORT_PATH="$report_path" python - <<'PY'
import json
import os
from pathlib import Path
report = json.loads(Path(os.environ["REPORT_PATH"]).read_text(encoding="utf-8"))
summary = report.get("summary", {})
print(json.dumps({
    "mapping": summary.get("mapping"),
    "proposals": summary.get("proposals"),
    "evidence_coverage": summary.get("evidence_coverage"),
    "highlighting": summary.get("highlighting"),
}, indent=2))
PY
    fi
  fi
fi
