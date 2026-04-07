#!/usr/bin/env bash

set -euo pipefail

label="${1:-overnight}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
session_id="$(date +%Y%m%d_%H%M%S)"
safe_label="$(printf '%s' "$label" | tr ' /:' '___')"

smoke_config="$repo_root/configs/compare_models_smoke.json"
compare_config="$repo_root/configs/compare_models_dev.json"
retrieval_config="$repo_root/configs/compare_retrieval_dev.json"
optimize_config="$repo_root/configs/optimize_overnight.json"
smoke_run_name="${session_id}_compare_smoke_${safe_label}"
compare_run_name="${session_id}_compare_models_dev_${safe_label}"
retrieval_run_name="${session_id}_compare_retrieval_dev_${safe_label}"
optimize_run_name="${session_id}_optimize_overnight_${safe_label}"

echo "[$(date -Iseconds)] Step 1: smoke compare preflight"
PAPER_OPTIMIZER_RUN_NAME="$smoke_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" compare "$smoke_config" "${safe_label}_smoke"

echo "[$(date -Iseconds)] Step 2: main compare study"
PAPER_OPTIMIZER_RUN_NAME="$compare_run_name" bash "$script_dir/run_study.sh" compare "$compare_config" "${safe_label}_compare"

echo "[$(date -Iseconds)] Step 3: retrieval sweep on Gemma"
PAPER_OPTIMIZER_RUN_NAME="$retrieval_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" compare "$retrieval_config" "${safe_label}_retrieval"

echo "[$(date -Iseconds)] Step 4: optimize study on Gemma"
PAPER_OPTIMIZER_RUN_NAME="$optimize_run_name" PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash "$script_dir/run_study.sh" optimize "$optimize_config" "${safe_label}_optimize"

echo "[$(date -Iseconds)] Overnight workflow finished"
echo "Smoke run: $repo_root/runs/$smoke_run_name"
echo "Compare run: $repo_root/runs/$compare_run_name"
echo "Retrieval run: $repo_root/runs/$retrieval_run_name"
echo "Optimize run: $repo_root/runs/$optimize_run_name"
