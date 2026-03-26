"""
Shared pytest fixtures for backend tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_run_store():
    """
    Reset the module-level run_store before each test that uses the FastAPI app.

    This prevents cross-test contamination from background parse threads
    that were started by a previous test but hadn't finished yet.
    """
    from backend.app import main
    from backend.app.runner import RunStore

    original = main.run_store
    fresh_store = RunStore()
    main.run_store = fresh_store
    yield fresh_store
    # Restore original (cleanup); background threads are daemons so they die with the process
    main.run_store = original
