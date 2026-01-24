#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

python -m venv .venv
# Git Bash on Windows uses Scripts/activate
source .venv/Scripts/activate

python -m pip install --upgrade pip
pip install -e ".[test]"

paper-table-agent --help
paper-table-agent ui --smoke
paper-table-agent run --config tests/fixtures/stub_run_config.json

if [ -d "runs" ]; then
  latest_run=$(ls -1t runs | head -n 1 || true)
  if [ -n "$latest_run" ]; then
    echo "Latest run folder: runs/$latest_run"
  fi
fi
