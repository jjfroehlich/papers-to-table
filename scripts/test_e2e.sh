#!/usr/bin/env bash
set -euo pipefail
cd frontend
export NODE_PATH="$(pwd)/node_modules"
npm run e2e
