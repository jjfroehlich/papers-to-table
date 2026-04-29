#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
app_dir="$repo_root/app"
python_bin="${PAPER_APP_PYTHON:-python}"

cd "$app_dir"
if ! "$python_bin" -c "import backend.app" >/dev/null 2>&1 || ! "$python_bin" -c "import respx" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Backend test dependencies are missing for this environment.
Install them from the repo root with:
  cd app && python -m pip install -e ./backend[test]
Then rerun:
  bash scripts/test-main-backend.sh
EOF
  exit 2
fi
exec "$python_bin" -m pytest tests/backend -m "not e2e and not smoke" "$@"