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

timestamp="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"
run_name="${PAPER_OPTIMIZER_RUN_NAME:-${timestamp}_${study_type}_${safe_label}}"
run_root="$repo_root/runs/$run_name"
experiment_dir="$run_root/experiment"
holdout_dir="$run_root/holdout"
logs_dir="$repo_root/logs"
log_file="$logs_dir/$run_name.log"
optimizer_cmd="${PAPER_OPTIMIZER_CMD:-paper-optimizer}"
skip_holdout="${PAPER_OPTIMIZER_SKIP_HOLDOUT:-0}"
metadata_file="$run_root/run_metadata.json"

if [[ "$optimizer_cmd" != *"/"* && "$optimizer_cmd" != *"\\"* ]]; then
  if ! command -v "$optimizer_cmd" >/dev/null 2>&1; then
    echo "Optimizer command is not on PATH: $optimizer_cmd" >&2
    exit 2
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

"$optimizer_cmd" optimize --study-type "$study_type" --config "$config_path" --out "$experiment_dir"
"$optimizer_cmd" summarize --config "$config_path" --experiment "$experiment_dir"

if [[ "$skip_holdout" == "1" ]]; then
  echo "[$(date -Iseconds)] Skipping holdout validation because PAPER_OPTIMIZER_SKIP_HOLDOUT=1"
else
  "$optimizer_cmd" validate-best --config "$config_path" --experiment "$experiment_dir" --out "$holdout_dir"
fi

echo "[$(date -Iseconds)] Finished $study_type study"
echo "Summary: $experiment_dir/summary.json"
echo "Best candidate: $experiment_dir/best_candidate.json"
echo "Run metadata: $metadata_file"

