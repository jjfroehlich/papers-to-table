#!/usr/bin/env bash

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
backend_status=0
frontend_build_status=0
eval_smoke_status=0
optimizer_smoke_status=0

if [[ $# -gt 0 ]]; then
  echo "This wrapper uses the default smoke command arguments." >&2
  echo "Run the underlying wrapper directly if you need custom paths or labels." >&2
  exit 2
fi

echo "== Minimum Smoke Verification =="
echo "Repository root: $repo_root"
echo

echo "-- Main app backend health: scripts/check-main-backend-health.sh"
if bash "$repo_root/scripts/check-main-backend-health.sh"; then
  echo "PASS: main app backend health"
else
  backend_status=$?
  echo "FAIL: main app backend health (exit $backend_status)"
fi
echo

echo "-- Main app frontend build: scripts/build-main-frontend.sh"
if bash "$repo_root/scripts/build-main-frontend.sh"; then
  echo "PASS: main app frontend build"
else
  frontend_build_status=$?
  echo "FAIL: main app frontend build (exit $frontend_build_status)"
fi
echo

echo "-- Eval smoke: scripts/run-eval-example.sh"
if bash "$repo_root/scripts/run-eval-example.sh"; then
  echo "PASS: eval smoke"
else
  eval_smoke_status=$?
  echo "FAIL: eval smoke (exit $eval_smoke_status)"
fi
echo

echo "-- Optimizer smoke: scripts/run-optimizer-smoke.sh"
if bash "$repo_root/scripts/run-optimizer-smoke.sh"; then
  echo "PASS: optimizer smoke"
else
  optimizer_smoke_status=$?
  echo "FAIL: optimizer smoke (exit $optimizer_smoke_status)"
fi
echo

echo "== Summary =="
if [[ $backend_status -eq 0 ]]; then
  echo "main_app_backend_health: PASS"
else
  echo "main_app_backend_health: FAIL (exit $backend_status)"
fi
if [[ $frontend_build_status -eq 0 ]]; then
  echo "main_app_frontend_build: PASS"
else
  echo "main_app_frontend_build: FAIL (exit $frontend_build_status)"
fi
if [[ $eval_smoke_status -eq 0 ]]; then
  echo "eval_smoke: PASS"
else
  echo "eval_smoke: FAIL (exit $eval_smoke_status)"
fi
if [[ $optimizer_smoke_status -eq 0 ]]; then
  echo "optimizer_smoke: PASS"
else
  echo "optimizer_smoke: FAIL (exit $optimizer_smoke_status)"
fi

if [[ $backend_status -ne 0 || $frontend_build_status -ne 0 || $eval_smoke_status -ne 0 || $optimizer_smoke_status -ne 0 ]]; then
  exit 1
fi