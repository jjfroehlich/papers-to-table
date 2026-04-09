#!/usr/bin/env bash

set -euo pipefail

label="${1:-overnight}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
session_id="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"
optimizer_python="${PAPER_OPTIMIZER_PYTHON:-python}"

compare_config="$repo_root/configs/compare_models_dev.json"
prompt_config="$repo_root/configs/compare_prompts_dev.json"
retrieval_config="$repo_root/configs/compare_retrieval_dev.json"
optimize_config="$repo_root/configs/optimize_overnight.json"
compare_run_name="${session_id}_compare_models_dev_${safe_label}"
prompt_run_name="${session_id}_compare_prompts_dev_${safe_label}"
retrieval_run_name="${session_id}_compare_retrieval_dev_${safe_label}"
optimize_run_name="${session_id}_optimize_overnight_${safe_label}"

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

config = json.loads(source_path.read_text(encoding="utf-8"))
best = json.loads(best_path.read_text(encoding="utf-8"))

winner_prompt = best.get("prompt_bundle_id") or config["baseline_candidate"]["prompt_bundle_id"]
winner_model = best.get("text_model_id") or config["baseline_candidate"]["text_model_id"]
winner_knobs = dict(best.get("optimizer_knobs_flat") or {})

def apply_candidate(candidate: dict, *, include_knobs: bool) -> None:
	candidate["prompt_bundle_id"] = winner_prompt
	candidate["text_model_id"] = winner_model
	if include_knobs and winner_knobs:
		candidate["optimizer_knobs"] = winner_knobs

if mode == "prompt_compare":
	apply_candidate(config["baseline_candidate"], include_knobs=False)
	for row in config.get("compare_candidates", []):
		apply_candidate(row, include_knobs=False)
elif mode == "retrieval_compare":
	apply_candidate(config["baseline_candidate"], include_knobs=False)
	for row in config.get("compare_candidates", []):
		apply_candidate(row, include_knobs=False)
elif mode == "optimize":
	apply_candidate(config["baseline_candidate"], include_knobs=True)
	if winner_prompt not in config.get("search_space", {}).get("prompt_bundle_ids", []):
		config.setdefault("search_space", {}).setdefault("prompt_bundle_ids", []).insert(0, winner_prompt)
	if winner_model not in config.get("search_space", {}).get("text_model_ids", []):
		config.setdefault("search_space", {}).setdefault("text_model_ids", []).insert(0, winner_model)
	if winner_knobs:
		for knob_name, knob_value in winner_knobs.items():
			knob_spec = config.get("search_space", {}).get("numeric_knobs", {}).get(knob_name)
			if not isinstance(knob_spec, dict):
				continue
			values = list(knob_spec.get("values", []))
			if knob_value not in values:
				values.insert(0, knob_value)
			knob_spec["values"] = values
else:
	raise SystemExit(f"Unsupported materialization mode: {mode}")

target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY
}

tmp_dir="$repo_root/runs/${session_id}_overnight_materialized_${safe_label}"
mkdir -p "$tmp_dir"
prompt_config_materialized="$tmp_dir/compare_prompts_dev.json"
retrieval_config_materialized="$tmp_dir/compare_retrieval_dev.json"
optimize_config_materialized="$tmp_dir/optimize_overnight.json"

echo "[$(date -Iseconds)] Step 1: fast config preflight"
pushd "$repo_root" >/dev/null
"$optimizer_python" -m paper_optimizer.cli preflight --config "$compare_config"
popd >/dev/null

echo "[$(date -Iseconds)] Step 2: main compare study"
PAPER_OPTIMIZER_RUN_NAME="$compare_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" compare "$compare_config" "${safe_label}_compare"

echo "[$(date -Iseconds)] Step 3: prompt compare on the model-compare winner"
materialize_config_with_winner "$prompt_config" "$(require_best_candidate_json "$compare_run_name")" "$prompt_config_materialized" prompt_compare
PAPER_OPTIMIZER_RUN_NAME="$prompt_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" compare "$prompt_config_materialized" "${safe_label}_prompts"

echo "[$(date -Iseconds)] Step 4: retrieval sweep on the prompt-compare winner"
materialize_config_with_winner "$retrieval_config" "$(require_best_candidate_json "$prompt_run_name")" "$retrieval_config_materialized" retrieval_compare
PAPER_OPTIMIZER_RUN_NAME="$retrieval_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" compare "$retrieval_config_materialized" "${safe_label}_retrieval"

echo "[$(date -Iseconds)] Step 5: optimize study from the retrieval-compare winner"
materialize_config_with_winner "$optimize_config" "$(require_best_candidate_json "$retrieval_run_name")" "$optimize_config_materialized" optimize
PAPER_OPTIMIZER_RUN_NAME="$optimize_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" optimize "$optimize_config_materialized" "${safe_label}_optimize"

echo "[$(date -Iseconds)] Overnight workflow finished"
echo "Compare run: $repo_root/runs/$compare_run_name"
echo "Prompt run: $repo_root/runs/$prompt_run_name"
echo "Retrieval run: $repo_root/runs/$retrieval_run_name"
echo "Optimize run: $repo_root/runs/$optimize_run_name"
