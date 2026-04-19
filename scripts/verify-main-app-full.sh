#!/usr/bin/env bash

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
backend_status=0
frontend_status=0

if [[ $# -gt 0 ]]; then
  echo "This wrapper does not forward arbitrary arguments." >&2
  echo "Use scripts/test-main-backend.sh or scripts/test-main-frontend.sh for targeted runs." >&2
  exit 2
fi

echo "== Main App Full Verification =="
echo "Repository root: $repo_root"
echo

echo "-- Backend tests: scripts/test-main-backend.sh"
if bash "$repo_root/scripts/test-main-backend.sh"; then
  echo "PASS: backend tests"
else
  backend_status=$?
  echo "FAIL: backend tests (exit $backend_status)"
fi
echo

echo "-- Frontend tests: scripts/test-main-frontend.sh"
if bash "$repo_root/scripts/test-main-frontend.sh"; then
  echo "PASS: frontend tests"
else
  frontend_status=$?
  echo "FAIL: frontend tests (exit $frontend_status)"
fi
echo

echo "== Summary =="
if [[ $backend_status -eq 0 ]]; then
  echo "backend: PASS"
else
  echo "backend: FAIL (exit $backend_status)"
fi
if [[ $frontend_status -eq 0 ]]; then
  echo "frontend: PASS"
else
  echo "frontend: FAIL (exit $frontend_status)"
fi

if [[ $backend_status -ne 0 || $frontend_status -ne 0 ]]; then
  exit 1
fi