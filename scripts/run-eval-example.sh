#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
eval_dir="$repo_root/tools/eval"
python_bin="${PAPER_EVAL_PYTHON:-python}"
out_dir="${1:-out/example-single-monorepo}"

cd "$eval_dir"
exec "$python_bin" -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out "$out_dir"