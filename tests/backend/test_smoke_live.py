"""
Batch 6 — T105

Non-hermetic smoke test for local LM Studio execution.

This test is opt-in: it only runs when the environment variable
PAPER_TABLE_AGENT_LIVE_TEST is set to "1".

Usage:
    PAPER_TABLE_AGENT_LIVE_TEST=1 python -m pytest tests/backend/test_smoke_live.py -v

Prerequisites:
- LM Studio running at the URL configured in PAPER_TABLE_AGENT_LIVE_BASE_URL
  (default: http://127.0.0.1:1234/v1)
- A model loaded in LM Studio
- A valid config file at PAPER_TABLE_AGENT_LIVE_CONFIG_PATH

The test launches a run through the FastAPI endpoint and waits for it to complete,
then inspects the run summary.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

LIVE_TEST_FLAG = os.environ.get("PAPER_TABLE_AGENT_LIVE_TEST", "").strip() == "1"

pytestmark = pytest.mark.skipif(
    not LIVE_TEST_FLAG,
    reason="Set PAPER_TABLE_AGENT_LIVE_TEST=1 to run live LM Studio smoke tests",
)


@pytest.fixture()
def live_config_path() -> str:
    """Return the config path from the environment, or skip if not set."""
    config_path = os.environ.get("PAPER_TABLE_AGENT_LIVE_CONFIG_PATH", "")
    if not config_path or not Path(config_path).is_file():
        pytest.skip(
            "Set PAPER_TABLE_AGENT_LIVE_CONFIG_PATH to a valid config file to run live tests"
        )
    return config_path


def test_live_run_completes(live_config_path: str) -> None:
    """
    Smoke test: create a run, wait for it to complete, and verify a terminal state.

    This test exercises the full pipeline (parse, match, extract) against a real
    LM Studio provider configured in the provided config file.
    """
    from fastapi.testclient import TestClient

    from backend.app.main import app, run_store
    from backend.app.runner import RunStore
    from backend.app.schemas import RunStatus

    # Use the app's real run_store (not the isolated test one)
    client = TestClient(app, raise_server_exceptions=False)

    # Create the run
    response = client.post("/api/runs", json={"config_path": live_config_path})
    assert response.status_code == 200, f"Run creation failed: {response.text}"
    run_id = response.json()["run_id"]

    # Poll until terminal state (max 5 minutes)
    max_wait_seconds = 300
    poll_interval = 5
    elapsed = 0
    terminal_states = {
        RunStatus.COMPLETED,
        RunStatus.COMPLETED_WITH_WARNINGS,
        RunStatus.FAILED,
    }

    final_status = None
    while elapsed < max_wait_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval
        summary_response = client.get(f"/api/runs/{run_id}/summary")
        if summary_response.status_code == 200:
            status_str = summary_response.json().get("status", "")
            try:
                status = RunStatus(status_str)
                if status in terminal_states:
                    final_status = status
                    break
            except ValueError:
                pass

    assert final_status is not None, (
        f"Run {run_id} did not reach a terminal state within {max_wait_seconds}s"
    )
    assert final_status in (RunStatus.COMPLETED, RunStatus.COMPLETED_WITH_WARNINGS), (
        f"Run {run_id} ended in {final_status}, expected completed or completed_with_warnings"
    )

    # Verify run summary is accessible
    summary = client.get(f"/api/runs/{run_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["run_id"] == run_id
