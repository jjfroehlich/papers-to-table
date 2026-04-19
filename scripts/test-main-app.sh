#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

echo "INFO: scripts/test-main-app.sh is a compatibility alias. Use scripts/verify-main-app-full.sh." >&2
exec bash "$repo_root/scripts/verify-main-app-full.sh" "$@"