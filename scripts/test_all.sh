#!/usr/bin/env bash
set -euo pipefail
bash scripts/test_backend.sh
bash scripts/test_frontend.sh
bash scripts/test_e2e.sh
