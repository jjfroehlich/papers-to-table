#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
optimizer_dir="$repo_root/tools/optimizer"
python_bin="${PAPER_OPTIMIZER_PYTHON:-python}"

cd "$optimizer_dir"
export MPLBACKEND="${MPLBACKEND:-Agg}"
exec "$python_bin" -m pytest "$@"