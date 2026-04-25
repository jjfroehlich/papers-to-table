#!/usr/bin/env bash

set -euo pipefail

label="${1:-monorepo_smoke}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
optimizer_dir="$repo_root/tools/optimizer"

cd "$optimizer_dir"
export PAPER_OPTIMIZER_SKIP_HOLDOUT="${PAPER_OPTIMIZER_SKIP_HOLDOUT:-1}"
exec bash scripts/run_study.sh compare configs/compare_models_contract_smoke.json "$label"