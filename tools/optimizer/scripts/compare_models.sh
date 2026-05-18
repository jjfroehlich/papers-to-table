#!/usr/bin/env bash

set -eEuo pipefail

label="compare_models"
initial_model=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--label)
			label="${2:?--label requires a value}"
			shift 2
			;;
		--initial-model)
			initial_model="${2:?--initial-model requires a model id}"
			shift 2
			;;
		--help|-h)
			cat <<'EOF'
Usage: compare_models.sh [--label LABEL] [--initial-model MODEL_ID]

Runs the canonical model-comparison workflow. With --initial-model, writes a
run-local compare_models.json limited to the requested text model id.
EOF
			exit 0
			;;
		-*)
			echo "Unknown option: $1" >&2
			exit 2
			;;
		*)
			label="$1"
			shift
			;;
	esac
done
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

base_compare_config="$repo_root/configs/compare_models.json"
compare_config="$base_compare_config"
compare_run_name="${session_id}_compare_models/compare"
overnight_dir="$repo_root/runs/${session_id}_compare_models"
manifest_path="$overnight_dir/overnight_manifest.json"
materialized_dir="$overnight_dir/materialized_configs"

mkdir -p "$overnight_dir"

write_manifest() {
	local status="$1"
	local completed_at="${2:-}"
	"$optimizer_python" - "$manifest_path" "$session_id" "$safe_label" "$status" "$completed_at" "$initial_model" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
session_id = sys.argv[2]
label = sys.argv[3]
status = sys.argv[4]
completed_at = sys.argv[5] or None
initial_model = sys.argv[6] or None

if manifest_path.exists():
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
else:
    payload = {"session_id": session_id, "label": label, "stages": []}

payload["session_id"] = session_id
payload["label"] = label
payload["status"] = status
if initial_model:
    payload["initial_model_filter"] = {"text_model_id": initial_model}
if completed_at is not None:
    payload["completed_at"] = completed_at
manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

materialize_initial_model_config() {
	local source_config="$1"
	local target_config="$2"
	local model_id="$3"

	"$optimizer_python" - "$source_config" "$target_config" "$model_id" <<'PY'
import json
import sys
from copy import deepcopy
from pathlib import Path

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
model_id = sys.argv[3]

config = json.loads(source_path.read_text(encoding="utf-8"))
path_fields = {
    "repo_root",
    "base_config_path",
    "table_path",
    "schema_path",
    "pdf_dir",
    "gold_path",
    "eval_schema_path",
    "path",
}

def resolve_path_fields(value):
    if isinstance(value, dict):
        resolved = {}
        for key, item in value.items():
            if key in path_fields and isinstance(item, str):
                path = Path(item)
                resolved[key] = str(path.resolve() if path.is_absolute() else (source_path.parent / path).resolve())
            else:
                resolved[key] = resolve_path_fields(item)
        return resolved
    if isinstance(value, list):
        return [resolve_path_fields(item) for item in value]
    return value

config = resolve_path_fields(config)
candidates = [config["baseline_candidate"], *list(config.get("compare_candidates", []) or [])]
matches = [deepcopy(candidate) for candidate in candidates if candidate.get("text_model_id") == model_id]
if not matches:
    available = sorted({str(candidate.get("text_model_id")) for candidate in candidates if candidate.get("text_model_id")})
    raise SystemExit(
        f"--initial-model {model_id!r} was not found in {source_path}. "
        f"Available model ids: {', '.join(available)}"
    )

selected = matches[0]
config["baseline_candidate"] = deepcopy(selected)
config["compare_candidates"] = [deepcopy(selected)]
config.setdefault("search_space", {})
config["search_space"]["text_model_ids"] = [model_id]
vision_model_id = selected.get("vision_model_id")
config["search_space"]["vision_model_ids"] = [vision_model_id] if vision_model_id else []
notes = config.setdefault("operator_todo", {}).setdefault("notes", [])
notes.append(
    f"Run-local compare-models override: comparison was limited to model {model_id}; "
    "the checked-in compare_models.json preset was not changed."
)
target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
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

if [[ -n "$initial_model" ]]; then
	mkdir -p "$materialized_dir"
	compare_config="$materialized_dir/compare_models.json"
	materialize_initial_model_config "$base_compare_config" "$compare_config" "$initial_model"
fi

write_manifest running

echo "[$(date -Iseconds)] Step 1: compare-models config preflight"
echo "[$(date -Iseconds)] Optimizer python: $optimizer_python"
pushd "$repo_root" >/dev/null
"$optimizer_python" -m paper_optimizer.cli preflight --config "$compare_config"
popd >/dev/null

echo "[$(date -Iseconds)] Step 2: compare-models study"
if PAPER_OPTIMIZER_RUN_NAME="$compare_run_name" bash "$script_dir/run_study.sh" compare "$compare_config" "${safe_label}_model_compare"; then
	append_stage model_compare "$compare_run_name"
	write_manifest completed "$(date -Iseconds)"
	refresh_overnight_report
else
	run_status=$?
	append_stage model_compare "$compare_run_name" || true
	write_manifest failed "$(date -Iseconds)" || true
	refresh_overnight_report || true
	trap - EXIT
	exit "$run_status"
fi
trap - EXIT

echo "[$(date -Iseconds)] Model-comparison workflow finished"
echo "Comparison overview: $overnight_dir/overview.html"
echo "All candidates CSV: $overnight_dir/all_candidates.csv"
echo "Compare run: $repo_root/runs/$compare_run_name"
