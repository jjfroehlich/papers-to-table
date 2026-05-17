#!/usr/bin/env bash

set -eEuo pipefail

label="full_benchmark"
resume_manifest=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--label)
			label="${2:?--label requires a value}"
			shift 2
			;;
		--resume)
			resume_manifest="${2:?--resume requires an overnight_manifest.json path}"
			shift 2
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
optimizer_python="${PAPER_OPTIMIZER_PYTHON:-python}"

if [[ -n "$resume_manifest" ]]; then
	eval "$("$optimizer_python" - "$resume_manifest" <<'PY'
import json
import shlex
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1]).resolve()
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
session_id = str(payload["session_id"])
label = str(payload.get("label") or "full_benchmark")
print(f"session_id={shlex.quote(session_id)}")
print(f"safe_label={shlex.quote(label)}")
print(f"label={shlex.quote(label)}")
print(f"resume_manifest={shlex.quote(str(manifest_path))}")
print(f"resume_overnight_dir={shlex.quote(str(manifest_path.parent))}")
PY
)"
fi

compare_config="$repo_root/configs/compare_models.json"
prompt_config="$repo_root/configs/compare_prompts.json"
retrieval_parameter_config="$repo_root/configs/compare_retrieval_parameters.json"
extraction_feature_config="$repo_root/configs/compare_extraction_features.json"
compare_run_name="${session_id}_fb_model"
prompt_run_name="${session_id}_fb_prompt"
retrieval_parameter_run_name="${session_id}_fb_retrieval"
extraction_feature_run_name="${session_id}_fb_features"
overnight_dir="${resume_overnight_dir:-$repo_root/runs/${session_id}_full_benchmark_${safe_label}}"

resolve_best_candidate_json() {
	local run_name="$1"
	printf '%s\n' "$repo_root/runs/$run_name/experiment/best_candidate.json"
}

require_best_candidate_json() {
	local run_name="$1"
	local best_path
	best_path="$(resolve_best_candidate_json "$run_name")"
	if [[ -f "$best_path" ]]; then
		printf '%s\n' "$best_path"
		return 0
	fi

	local summary_path="$repo_root/runs/$run_name/experiment/summary.json"
	if [[ -f "$summary_path" ]]; then
		"$optimizer_python" - "$summary_path" "$run_name" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
run_name = sys.argv[2]
summary = json.loads(summary_path.read_text(encoding="utf-8"))
winner = summary.get("winner_candidate_id")
completed = summary.get("completed_candidate_count")
failed = summary.get("failed_candidate_count")
reasons = summary.get("rejection_reason_counts")
raise SystemExit(
    f"Run '{run_name}' did not produce best_candidate.json because no completed winner was recorded. "
    f"winner_candidate_id={winner!r}, completed_candidate_count={completed}, failed_candidate_count={failed}, "
    f"rejection_reason_counts={reasons}."
)
PY
	fi

	echo "Run '$run_name' did not produce best_candidate.json and no summary.json was found." >&2
	return 1
}

resolve_results_jsonl() {
	local run_name="$1"
	printf '%s\n' "$repo_root/runs/$run_name/experiment/results/results.jsonl"
}

materialize_config_with_winner() {
	local source_config="$1"
	local best_candidate_json="$2"
	local target_config="$3"
	local mode="$4"

	"$optimizer_python" - "$source_config" "$best_candidate_json" "$target_config" "$mode" <<'PY'
import json
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
best_path = Path(sys.argv[2])
target_path = Path(sys.argv[3])
mode = sys.argv[4]

PATH_FIELD_NAMES = {
	"repo_root",
	"base_config_path",
	"table_path",
	"schema_path",
	"pdf_dir",
	"gold_path",
	"eval_schema_path",
}

config = json.loads(source_path.read_text(encoding="utf-8"))
best = json.loads(best_path.read_text(encoding="utf-8"))

winner_prompt = best.get("prompt_bundle_id") or config["baseline_candidate"]["prompt_bundle_id"]
winner_model = best.get("text_model_id") or config["baseline_candidate"]["text_model_id"]
winner_vision = best.get("vision_model_id")
winner_knobs = dict(best.get("optimizer_knobs_flat") or {})


def resolve_path_fields(payload, *, base_dir: Path):
	if isinstance(payload, dict):
		resolved = {}
		for key, value in payload.items():
			if key in PATH_FIELD_NAMES and isinstance(value, str) and value.strip():
				candidate = Path(value)
				resolved[key] = str(candidate.resolve()) if candidate.is_absolute() else str((base_dir / candidate).resolve())
			else:
				resolved[key] = resolve_path_fields(value, base_dir=base_dir)
		return resolved
	if isinstance(payload, list):
		return [resolve_path_fields(item, base_dir=base_dir) for item in payload]
	return payload

def apply_candidate(candidate: dict, *, include_knobs: bool, preserve_prompt_bundle: bool = False) -> None:
	if not preserve_prompt_bundle:
		candidate["prompt_bundle_id"] = winner_prompt
	candidate["text_model_id"] = winner_model
	candidate["vision_model_id"] = winner_vision
	if include_knobs and winner_knobs:
		candidate["optimizer_knobs"] = winner_knobs

if mode == "prompt_compare":
	apply_candidate(config["baseline_candidate"], include_knobs=False, preserve_prompt_bundle=True)
	for row in config.get("compare_candidates", []):
		apply_candidate(row, include_knobs=False, preserve_prompt_bundle=True)
elif mode == "retrieval_compare":
	apply_candidate(config["baseline_candidate"], include_knobs=False)
	for row in config.get("compare_candidates", []):
		apply_candidate(row, include_knobs=False)
else:
	raise SystemExit(f"Unsupported materialization mode: {mode}")

config = resolve_path_fields(config, base_dir=source_path.resolve().parent)
target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY
}

materialize_extraction_feature_config() {
	local source_config="$1"
	local results_jsonl="$2"
	local target_config="$3"
	local max_seed_candidates="$4"

	"$optimizer_python" - "$source_config" "$results_jsonl" "$target_config" "$max_seed_candidates" <<'PY'
import json
import sys
from copy import deepcopy
from pathlib import Path

source_path = Path(sys.argv[1])
results_path = Path(sys.argv[2])
target_path = Path(sys.argv[3])
max_seed_candidates = int(sys.argv[4])

PATH_FIELD_NAMES = {
	"repo_root",
	"base_config_path",
	"table_path",
	"schema_path",
	"pdf_dir",
	"gold_path",
	"eval_schema_path",
}

def resolve_path_fields(payload, *, base_dir: Path):
	if isinstance(payload, dict):
		resolved = {}
		for key, value in payload.items():
			if key in PATH_FIELD_NAMES and isinstance(value, str) and value.strip():
				candidate = Path(value)
				resolved[key] = str(candidate.resolve()) if candidate.is_absolute() else str((base_dir / candidate).resolve())
			else:
				resolved[key] = resolve_path_fields(value, base_dir=base_dir)
		return resolved
	if isinstance(payload, list):
		return [resolve_path_fields(item, base_dir=base_dir) for item in payload]
	return payload

def sort_key(record: dict) -> tuple[int, float, float, str]:
	status = str(record.get("score_status") or "")
	status_priority = {"scored": 0, "scored_degraded": 1, "unscored": 2, "failed": 3}.get(status, 9)
	primary_metric = str(config.get("acceptance", {}).get("primary_metric") or "content_correctness")
	primary = record.get("primary_metrics", {}).get(primary_metric)
	primary_value = float(primary) if isinstance(primary, (int, float)) else float("-inf")
	runtime = record.get("runtime_seconds")
	runtime_value = float(runtime) if isinstance(runtime, (int, float)) else float("inf")
	return (status_priority, -primary_value, runtime_value, str(record.get("candidate_id") or "zzz"))

config = json.loads(source_path.read_text(encoding="utf-8"))
records = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
records.sort(key=sort_key)
seed_records = [record for record in records if record.get("candidate_status") == "completed"][:max_seed_candidates]
if not seed_records:
	raise SystemExit("No completed retrieval-parameter candidates were available for extraction-feature materialization.")

template_candidates = list(config.get("compare_candidates", []))
if not template_candidates:
	raise SystemExit("Extraction-feature template has no compare_candidates to expand.")

materialized_candidates = []
for seed in seed_records:
	seed_prompt = seed.get("prompt_bundle_id") or config["baseline_candidate"]["prompt_bundle_id"]
	seed_model = seed.get("text_model_id") or config["baseline_candidate"]["text_model_id"]
	seed_vision = seed.get("vision_model_id")
	seed_knobs = dict(seed.get("optimizer_knobs_flat") or {})
	seed_retrieval_mode = seed_knobs.get("retrieval_mode")
	seed_retrieval_top_k = seed_knobs.get("retrieval_top_k")
	for template in template_candidates:
		candidate = deepcopy(template)
		candidate["prompt_bundle_id"] = seed_prompt
		candidate["text_model_id"] = seed_model
		candidate["vision_model_id"] = seed_vision
		candidate.setdefault("optimizer_knobs", {})
		if seed_retrieval_mode is not None:
			candidate["optimizer_knobs"]["retrieval_mode"] = seed_retrieval_mode
		if seed_retrieval_top_k is not None:
			candidate["optimizer_knobs"]["retrieval_top_k"] = seed_retrieval_top_k
		materialized_candidates.append(candidate)

config["baseline_candidate"] = deepcopy(materialized_candidates[0])
config["compare_candidates"] = materialized_candidates
config = resolve_path_fields(config, base_dir=source_path.resolve().parent)
target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY
}

tmp_dir="$overnight_dir/materialized_configs"
mkdir -p "$tmp_dir" "$overnight_dir"
prompt_config_materialized="$tmp_dir/compare_prompts.json"
retrieval_parameter_config_materialized="$tmp_dir/compare_retrieval_parameters.json"
extraction_feature_config_materialized="$tmp_dir/compare_extraction_features.json"
manifest_path="$overnight_dir/overnight_manifest.json"

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
elif status == "running":
	payload.pop("completed_at", None)
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
stage_payload = {
	"stage_name": stage_name,
	"run_name": run_name,
	"run_root": str((repo_root / "runs" / run_name).resolve()),
}
stages = [stage for stage in stages if stage.get("stage_name") != stage_name]
stages.append(stage_payload)
payload["stages"] = stages
manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

stage_recorded() {
	local stage_name="$1"
	"$optimizer_python" - "$manifest_path" "$stage_name" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
stage_name = sys.argv[2]
if not manifest_path.exists():
    raise SystemExit(1)
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
for stage in payload.get("stages", []) or []:
    if stage.get("stage_name") == stage_name:
        raise SystemExit(0)
raise SystemExit(1)
PY
}

run_stage() {
	local stage_name="$1"
	local run_name="$2"
	local study_type="$3"
	local config_path="$4"
	local label_suffix="$5"
	if stage_recorded "$stage_name"; then
		echo "[$(date -Iseconds)] Skipping $stage_name; already recorded in manifest"
		return 0
	fi
	PAPER_OPTIMIZER_RUN_NAME="$run_name" PAPER_OPTIMIZER_RESUME=1 PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" "$study_type" "$config_path" "${safe_label}_${label_suffix}"
	append_stage "$stage_name" "$run_name"
	refresh_overnight_report
}

refresh_overnight_report() {
	pushd "$repo_root" >/dev/null
	"$optimizer_python" -m paper_optimizer.cli overnight-report --manifest "$manifest_path"
	popd >/dev/null
}

preflight_config() {
	local config_path="$1"
	pushd "$repo_root" >/dev/null
	"$optimizer_python" -m paper_optimizer.cli preflight --config "$config_path"
	popd >/dev/null
}

mark_failed() {
	local exit_code="$1"
	if [[ "$exit_code" -eq 0 ]]; then
		return 0
	fi
	write_manifest failed "$(date -Iseconds)"
	refresh_overnight_report || true
	return 0
}

trap 'mark_failed "$?"' EXIT

write_manifest running

echo "[$(date -Iseconds)] Step 1: fast config preflight"
preflight_config "$compare_config"

echo "[$(date -Iseconds)] Step 2: main compare study"
run_stage model_compare "$compare_run_name" compare "$compare_config" compare

echo "[$(date -Iseconds)] Step 3: prompt compare on the model-compare winner"
materialize_config_with_winner "$prompt_config" "$(require_best_candidate_json "$compare_run_name")" "$prompt_config_materialized" prompt_compare
preflight_config "$prompt_config_materialized"
run_stage prompt_compare "$prompt_run_name" compare "$prompt_config_materialized" prompts

echo "[$(date -Iseconds)] Step 4: retrieval sweep on the prompt-compare winner"
materialize_config_with_winner "$retrieval_parameter_config" "$(require_best_candidate_json "$prompt_run_name")" "$retrieval_parameter_config_materialized" retrieval_compare
preflight_config "$retrieval_parameter_config_materialized"
run_stage retrieval_parameter_compare "$retrieval_parameter_run_name" compare "$retrieval_parameter_config_materialized" retrieval_parameters

echo "[$(date -Iseconds)] Step 5: extraction feature sweep on the top retrieval-parameter candidates"
materialize_extraction_feature_config "$extraction_feature_config" "$(resolve_results_jsonl "$retrieval_parameter_run_name")" "$extraction_feature_config_materialized" 2
preflight_config "$extraction_feature_config_materialized"
run_stage extraction_feature_compare "$extraction_feature_run_name" compare "$extraction_feature_config_materialized" extraction_features

write_manifest completed "$(date -Iseconds)"
refresh_overnight_report
trap - EXIT

echo "[$(date -Iseconds)] Full benchmark workflow finished"
echo "Full benchmark report: $overnight_dir/report.html"
echo "All candidates CSV: $overnight_dir/all_candidates.csv"
echo "Compare run: $repo_root/runs/$compare_run_name"
echo "Prompt run: $repo_root/runs/$prompt_run_name"
echo "Retrieval parameter run: $repo_root/runs/$retrieval_parameter_run_name"
echo "Extraction feature run: $repo_root/runs/$extraction_feature_run_name"
