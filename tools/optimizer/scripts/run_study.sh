#!/usr/bin/env bash

set -euo pipefail

study_type="${1:?usage: run_study.sh <compare|optimize> <config-path> [label]}"
config_path="${2:?usage: run_study.sh <compare|optimize> <config-path> [label]}"
label="${3:-study}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
session_id="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"
run_name="${PAPER_OPTIMIZER_RUN_NAME:-${session_id}_${study_type}_${safe_label}}"
run_root="$repo_root/runs/$run_name"
experiment_dir="$run_root/experiment"
holdout_dir="$run_root/holdout"
log_file="$repo_root/logs/${run_name}.log"
metadata_file="$run_root/run_metadata.json"
mkdir -p "$run_root" "$experiment_dir" "$repo_root/logs"

resolve_optimizer_python() {
  if [[ -n "${PAPER_OPTIMIZER_PYTHON:-}" ]]; then
    echo "$PAPER_OPTIMIZER_PYTHON"
    return
  fi

  local candidate
  for candidate in \
    "$repo_root/.venv/Scripts/python.exe" \
    "$repo_root/.venv/bin/python" \
    "$repo_root/venv/Scripts/python.exe" \
    "$repo_root/venv/bin/python"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done

  echo python
}

optimizer_python="$(resolve_optimizer_python)"
status="running"
holdout_status="not_run"

sync_holdout_summary() {
  local holdout_state="$1"
  local skip_reason="${2:-}"
  "$optimizer_python" - "$experiment_dir" "$holdout_dir" "$holdout_state" "$skip_reason" <<'PY'
import json
import sys
from pathlib import Path

experiment_dir = Path(sys.argv[1])
holdout_dir = Path(sys.argv[2])
holdout_state = sys.argv[3]
skip_reason = sys.argv[4] or None
summary_path = experiment_dir / "summary.json"
if not summary_path.exists():
  raise SystemExit(0)
summary = json.loads(summary_path.read_text(encoding="utf-8"))
holdout = summary.get("holdout_validation", {}) if isinstance(summary.get("holdout_validation"), dict) else {}
holdout.update(
  {
    "configured": holdout.get("configured", True),
    "status": holdout_state,
    "ran": holdout_state == "completed",
    "skip_reason": skip_reason,
    "output_dir": str(holdout_dir.resolve()),
  }
)
summary["holdout_validation"] = holdout
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

write_metadata() {
  "$optimizer_python" - "$metadata_file" <<'PY'
import json
import os
import sys

metadata_path = sys.argv[1]
payload = {
    "run_name": os.environ["RUN_NAME"],
    "study_type": os.environ["STUDY_TYPE"],
    "config_path": os.environ["CONFIG_PATH"],
    "experiment_dir": os.environ["EXPERIMENT_DIR"],
    "holdout_dir": os.environ["HOLDOUT_DIR"],
    "log_file": os.environ["LOG_FILE"],
    "status": os.environ["RUN_STATUS"],
    "holdout_status": os.environ["HOLDOUT_STATUS"],
    "skip_holdout": os.environ["SKIP_HOLDOUT"],
    "exit_code": int(os.environ["EXIT_CODE"]),
}
with open(metadata_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
PY
}

on_exit() {
  local rc=$?
  RUN_NAME="$run_name" \
  STUDY_TYPE="$study_type" \
  CONFIG_PATH="$config_path" \
  EXPERIMENT_DIR="$experiment_dir" \
  HOLDOUT_DIR="$holdout_dir" \
  LOG_FILE="$log_file" \
  RUN_STATUS="$status" \
  HOLDOUT_STATUS="$holdout_status" \
  SKIP_HOLDOUT="${PAPER_OPTIMIZER_SKIP_HOLDOUT:-0}" \
  EXIT_CODE="$rc" \
  write_metadata
  exit "$rc"
}

trap on_exit EXIT

{
  echo "[$(date -Iseconds)] Starting $study_type study"
  echo "Config: $config_path"
  echo "Experiment dir: $experiment_dir"
  echo "Holdout dir: $holdout_dir"
  echo "Log file: $log_file"
  echo "Optimizer command: $optimizer_python -m paper_optimizer.cli"

  "$optimizer_python" - "$config_path" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
config = json.loads(config_path.read_text(encoding="utf-8"))


def _module_from_command_prefix(prefix, default):
    if isinstance(prefix, list):
        for idx, token in enumerate(prefix):
            if token == "-m" and idx + 1 < len(prefix):
                candidate = prefix[idx + 1]
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return default


required_modules = []

main_cfg = config.get("main_app", {}) if isinstance(config, dict) else {}
if isinstance(main_cfg, dict) and "command" not in main_cfg:
    main_module = _module_from_command_prefix(main_cfg.get("command_prefix"), main_cfg.get("module", "backend.app.automation"))
    required_modules.append(("main_app", main_module))

eval_cfg = config.get("eval_app", {}) if isinstance(config, dict) else {}
if isinstance(eval_cfg, dict) and "command" not in eval_cfg:
    eval_module = _module_from_command_prefix(eval_cfg.get("command_prefix"), eval_cfg.get("module", "paper_eval"))
    required_modules.append(("eval_app", eval_module))

missing = []
for section, module_name in required_modules:
    if not isinstance(module_name, str) or not module_name.strip():
        continue
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        missing.append((section, module_name))

if missing:
    for section, module_name in missing:
        print(
            f"Missing module '{module_name}' required by {section} using optimizer python '{sys.executable}'.",
            file=sys.stderr,
        )
    print(
        "Set PAPER_OPTIMIZER_PYTHON to an interpreter with all required packages installed.",
        file=sys.stderr,
    )
    sys.exit(2)
PY

  pushd "$repo_root" >/dev/null
  "$optimizer_python" -m paper_optimizer.cli optimize --study-type "$study_type" --config "$config_path" --out "$experiment_dir"
  if [[ "${PAPER_OPTIMIZER_SKIP_HOLDOUT:-0}" == "1" ]]; then
    holdout_status="skipped"
    echo "[$(date -Iseconds)] Skipping holdout validation because PAPER_OPTIMIZER_SKIP_HOLDOUT=1"
    sync_holdout_summary skipped PAPER_OPTIMIZER_SKIP_HOLDOUT
  else
    if "$optimizer_python" -m paper_optimizer.cli validate-best --config "$config_path" --experiment "$experiment_dir" --out "$holdout_dir"; then
      holdout_status="completed"
    else
      holdout_status="failed"
      sync_holdout_summary failed validate_best_failed
      exit 1
    fi
  fi
  "$optimizer_python" -m paper_optimizer.cli summarize --config "$config_path" --experiment "$experiment_dir"
  "$optimizer_python" - "$experiment_dir/summary.json" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
if not summary_path.exists():
    raise SystemExit("summary.json was not produced")

summary = json.loads(summary_path.read_text(encoding="utf-8"))
candidate_count = summary.get("candidate_count")
completed_count = summary.get("completed_candidate_count")

if isinstance(candidate_count, int) and candidate_count > 0 and isinstance(completed_count, int) and completed_count == 0:
    raise SystemExit("No candidates completed successfully; failing run")
PY
  popd >/dev/null

  status="completed"
  echo "[$(date -Iseconds)] Finished $study_type study"
  echo "Summary: $experiment_dir/summary.json"
  echo "Best candidate: $experiment_dir/best_candidate.json"
  echo "Run metadata: $metadata_file"
} 2>&1 | tee "$log_file"
