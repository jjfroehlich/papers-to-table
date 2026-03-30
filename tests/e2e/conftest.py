"""
E2e test scaffolding for Paper Table Agent.

These tests require:
  - Backend running: uvicorn backend.app.main:app --port 8000
  - Frontend built and served: cd frontend && npm run preview -- --port 5173

Enable live e2e tests with: pytest tests/e2e -m e2e

Fixture preparation is separate from server startup per T016a.
"""
from __future__ import annotations

import pytest

# All e2e tests are marked 'e2e' so they can be opted in explicitly:
#   pytest tests/e2e -m e2e
# They are skipped by default in CI to avoid requiring a running server.


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring live backend and frontend")
