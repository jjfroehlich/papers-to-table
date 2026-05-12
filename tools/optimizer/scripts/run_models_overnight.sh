#!/usr/bin/env bash

set -eEuo pipefail

label="${1:-models_overnight}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
session_id="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"

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

compare_config="$repo_root/configs/compare_models_overnight.json"
compare_run_name="${session_id}_models/model_compare"
overnight_dir="$repo_root/runs/${session_id}_models"
manifest_path="$overnight_dir/overnight_manifest.json"

mkdir -p "$overnight_dir"

write_manifest() {
	local status="$1"
	local completed_at="${2:-}"
	"$optimizer_python" - "$manifest_path" "$session_id" "$safe_label" "$status" "$completed_at" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
session_id = sys.argv[2]
label = sys.argv[3]
status = sys.argv[4]
completed_at = sys.argv[5] or None

if manifest_path.exists():
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
else:
    payload = {"session_id": session_id, "label": label, "stages": []}

payload["session_id"] = session_id
payload["label"] = label
payload["status"] = status
if completed_at is not None:
    payload["completed_at"] = completed_at
manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

append_stage() {
	local stage_name="$1"
	local run_name="$2"
	"$optimizer_python" - "$manifest_path" "$stage_name" "$repo_root" "$run_name" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
stage_name = sys.argv[2]
repo_root = Path(sys.argv[3])
run_name = sys.argv[4]

payload = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"stages": []}
stages = payload.get("stages", []) if isinstance(payload.get("stages"), list) else []
stages = [stage for stage in stages if stage.get("stage_name") != stage_name]
stages.append(
    {
        "stage_name": stage_name,
        "run_name": run_name,
        "run_root": str((repo_root / "runs" / run_name).resolve()),
    }
)
payload["stages"] = stages
manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

refresh_overnight_report() {
	pushd "$repo_root" >/dev/null
	"$optimizer_python" -m paper_optimizer.cli overnight-report --manifest "$manifest_path"
	popd >/dev/null
}

mark_failed() {
	local exit_code="$1"
	if [[ "$exit_code" -eq 0 ]]; then
		return 0
	fi
	write_manifest failed "$(date -Iseconds)" || true
	refresh_overnight_report || true
	return 0
}

trap 'mark_failed "$?"' EXIT

write_manifest running

echo "[$(date -Iseconds)] Step 1: model-only config preflight"
echo "[$(date -Iseconds)] Optimizer python: $optimizer_python"
pushd "$repo_root" >/dev/null
"$optimizer_python" -m paper_optimizer.cli preflight --config "$compare_config"
popd >/dev/null

echo "[$(date -Iseconds)] Step 2: model-only compare study"
PAPER_OPTIMIZER_RUN_NAME="$compare_run_name" bash "$script_dir/run_study.sh" compare "$compare_config" "${safe_label}_model_compare"
append_stage model_compare "$compare_run_name"
write_manifest completed "$(date -Iseconds)"
refresh_overnight_report
trap - EXIT

echo "[$(date -Iseconds)] Model-only overnight workflow finished"
echo "Overnight overview: $overnight_dir/overview.html"
echo "All candidates CSV: $overnight_dir/all_candidates.csv"
echo "Compare run: $repo_root/runs/$compare_run_name"
