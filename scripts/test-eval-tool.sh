#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
eval_dir="$repo_root/tools/eval"
python_bin="${PAPER_EVAL_PYTHON:-python}"

cd "$eval_dir"
exec "$python_bin" -m pytest "$@"