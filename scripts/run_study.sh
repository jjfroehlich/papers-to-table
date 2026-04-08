#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: bash scripts/run_study.sh <compare|optimize> <config-path> [label]" >&2
  exit 2
fi

study_type="$1"
config_path="$2"
label="${3:-manual}"

if [[ "$study_type" != "compare" && "$study_type" != "optimize" ]]; then
  echo "study_type must be compare or optimize" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
if [[ ! -f "$config_path" ]]; then
  echo "Config file does not exist: $config_path" >&2
  exit 2
fi

config_skip_holdout="$({
  python - "$config_path" "$study_type" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
study_type = sys.argv[2]
config = json.loads(config_path.read_text(encoding="utf-8"))
benchmarks = config.get("benchmarks", {}) if isinstance(config.get("benchmarks"), dict) else {}
compare_cfg = config.get("compare", {}) if isinstance(config.get("compare"), dict) else {}

skip = False
if "holdout" not in benchmarks:
    skip = True
elif study_type == "compare" and int(compare_cfg.get("holdout_top_k", 0) or 0) <= 0:
    skip = True

print("1" if skip else "0")
PY
} 2>/dev/null || printf '0')"

timestamp="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"
run_name="${PAPER_OPTIMIZER_RUN_NAME:-${timestamp}_${study_type}_${safe_label}}"
run_root="$repo_root/runs/$run_name"
experiment_dir="$run_root/experiment"
holdout_dir="$run_root/holdout"
logs_dir="$repo_root/logs"
log_file="$logs_dir/$run_name.log"
optimizer_cmd="${PAPER_OPTIMIZER_CMD:-paper-optimizer}"
optimizer_python="${PAPER_OPTIMIZER_PYTHON:-python}"
skip_holdout="${PAPER_OPTIMIZER_SKIP_HOLDOUT:-0}"
metadata_file="$run_root/run_metadata.json"

if [[ "$config_skip_holdout" == "1" ]]; then
  skip_holdout="1"
fi

optimizer_cmd_kind="direct"
optimizer_cmd_display="$optimizer_cmd"

if [[ "$optimizer_cmd" != *"/"* && "$optimizer_cmd" != *"\\"* ]]; then
  if ! command -v "$optimizer_cmd" >/dev/null 2>&1; then
    if command -v "$optimizer_python" >/dev/null 2>&1; then
      optimizer_cmd_kind="python-module"
      optimizer_cmd_display="$optimizer_python -m paper_optimizer.cli"
    else
      echo "Optimizer command is not on PATH: $optimizer_cmd" >&2
      echo "Fallback python is not on PATH either: $optimizer_python" >&2
      exit 2
    fi
  fi
elif [[ ! -x "$optimizer_cmd" && ! -f "$optimizer_cmd" ]]; then
  echo "Optimizer command path does not exist: $optimizer_cmd" >&2
  exit 2
fi

mkdir -p "$experiment_dir" "$logs_dir" "$run_root"

exec > >(tee -a "$log_file") 2>&1

cat > "$metadata_file" <<EOF
{
  "run_name": "${run_name}",
  "study_type": "${study_type}",
  "config_path": "${config_path}",
  "experiment_dir": "${experiment_dir}",
  "holdout_dir": "${holdout_dir}",
  "log_file": "${log_file}"
}
EOF

echo "[$(date -Iseconds)] Starting $study_type study"
echo "Config: $config_path"
echo "Experiment dir: $experiment_dir"
echo "Holdout dir: $holdout_dir"
echo "Log file: $log_file"
echo "Optimizer command: $optimizer_cmd_display"

if [[ "$optimizer_cmd_kind" == "python-module" ]]; then
  "$optimizer_python" -m paper_optimizer.cli optimize --study-type "$study_type" --config "$config_path" --out "$experiment_dir"
  "$optimizer_python" -m paper_optimizer.cli summarize --config "$config_path" --experiment "$experiment_dir"
else
  "$optimizer_cmd" optimize --study-type "$study_type" --config "$config_path" --out "$experiment_dir"
  "$optimizer_cmd" summarize --config "$config_path" --experiment "$experiment_dir"
fi

if [[ "$skip_holdout" == "1" ]]; then
  echo "[$(date -Iseconds)] Skipping holdout validation because PAPER_OPTIMIZER_SKIP_HOLDOUT=1"
else
  if [[ "$optimizer_cmd_kind" == "python-module" ]]; then
    "$optimizer_python" -m paper_optimizer.cli validate-best --config "$config_path" --experiment "$experiment_dir" --out "$holdout_dir"
  else
    "$optimizer_cmd" validate-best --config "$config_path" --experiment "$experiment_dir" --out "$holdout_dir"
  fi
fi

echo "[$(date -Iseconds)] Finished $study_type study"
echo "Summary: $experiment_dir/summary.json"
echo "Best candidate: $experiment_dir/best_candidate.json"
echo "Run metadata: $metadata_file"

