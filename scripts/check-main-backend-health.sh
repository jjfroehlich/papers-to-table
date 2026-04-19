#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
app_dir="$repo_root/app"
python_bin="${PAPER_APP_PYTHON:-python}"
port="${PAPER_APP_HEALTH_PORT:-8010}"
timeout_seconds="${PAPER_APP_HEALTH_TIMEOUT_SECONDS:-30}"
health_url="http://127.0.0.1:${port}/api/health"
log_file="$(mktemp -t paper_app_health.XXXXXX.log)"
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -f "$log_file"
}

trap cleanup EXIT

cd "$app_dir"
"$python_bin" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$port" >"$log_file" 2>&1 &
server_pid="$!"

for ((attempt = 1; attempt <= timeout_seconds; attempt++)); do
  if curl -fsS "$health_url" >/dev/null 2>&1; then
    echo "PASS: backend health endpoint responded at $health_url"
    exit 0
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "FAIL: backend exited before the health endpoint responded" >&2
    cat "$log_file" >&2
    exit 1
  fi
  sleep 1
done

echo "FAIL: backend health endpoint did not respond within ${timeout_seconds}s: $health_url" >&2
cat "$log_file" >&2
exit 1