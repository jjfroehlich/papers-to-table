#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
app_dir="$repo_root/app"
python_bin="${PAPER_APP_PYTHON:-python}"

cd "$app_dir"
exec "$python_bin" -m pytest tests/backend -m "not e2e and not smoke" "$@"