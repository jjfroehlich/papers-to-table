from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _load_stub_config(repo_root: Path) -> dict:
    config_path = repo_root / "tests" / "fixtures" / "stub_run_config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _write_temp_config(tmp_path: Path, repo_root: Path) -> Path:
    config = _load_stub_config(repo_root)
    config["table_path"] = str((repo_root / config["table_path"]).resolve())
    config["schema_path"] = str((repo_root / config["schema_path"]).resolve())
    config["pdf_folder"] = str((repo_root / config["pdf_folder"]).resolve())
    config_path = tmp_path / "stub_run_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


def _latest_run_dir(runs_root: Path) -> Path:
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    assert run_dirs, f"No runs created in {runs_root}"
    return sorted(run_dirs)[-1]


def test_stub_run_produces_evidence(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = _write_temp_config(tmp_path, repo_root)
    runs_root = tmp_path / "runs"
    env = os.environ.copy()
    env["PAPER_TABLE_AGENT_RUNS_ROOT"] = str(runs_root)
    result = subprocess.run(
        [sys.executable, "-m", "paper_table_agent.cli", "run", "--config", str(config_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    run_dir = _latest_run_dir(runs_root)
    db_path = run_dir / "proposals.sqlite"
    assert db_path.exists(), f"Missing sqlite DB at {db_path}"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM matches")
        matches = [row[0] for row in cursor.fetchall()]
        assert any(status == "matched" for status in matches), "No matched pdf->row"

        cursor.execute("SELECT proposed_value, evidence_json, flags_json FROM proposals")
        rows = cursor.fetchall()
        assert rows, "No proposals recorded"

    proposals_with_value = 0
    proposals_with_strong_evidence = 0
    proposals_with_highlight = 0
    for proposed_value, evidence_json, flags_json in rows:
        if proposed_value:
            proposals_with_value += 1
        evidence = json.loads(evidence_json) if evidence_json else []
        flags = json.loads(flags_json) if flags_json else {}
        evidence_quality = flags.get("evidence_quality")
        for item in evidence:
            quote = (item.get("quote") or "").strip()
            page = item.get("page")
            chunk_ref = item.get("chunk_id") or item.get("chunk_idx")
            rects = item.get("rects") or []
            if quote and isinstance(page, int) and chunk_ref and evidence_quality == "strong":
                proposals_with_strong_evidence += 1
                if rects and item.get("highlight_status") == "highlighted":
                    proposals_with_highlight += 1
                break

    assert proposals_with_value >= 3, "Expected at least 3 proposals with non-empty proposed_value"
    assert proposals_with_strong_evidence >= 1, "No proposal with strong evidence quality"
    assert proposals_with_highlight >= 1, "No proposal with highlightable evidence bbox"
