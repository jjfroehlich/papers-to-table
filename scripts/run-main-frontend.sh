#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
frontend_dir="$repo_root/app/frontend"
npm_bin="${PAPER_FRONTEND_NPM:-npm}"

cd "$frontend_dir"
exec "$npm_bin" run dev "$@"