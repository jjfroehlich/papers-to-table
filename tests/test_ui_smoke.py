from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_ui_smoke_mode() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PAPER_TABLE_AGENT_TEST_MODE"] = "smoke"
    result = subprocess.run(
        [sys.executable, "-m", "paper_table_agent.cli", "ui", "--smoke"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
