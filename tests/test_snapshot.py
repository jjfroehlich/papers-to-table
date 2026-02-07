from __future__ import annotations

import zipfile
from pathlib import Path

from paper_table_agent import cli


def test_snapshot_command_creates_expected_files(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "snapshot"
    monkeypatch.setattr(
        "sys.argv",
        ["paper-table-agent", "snapshot", "--out", str(out_dir)],
    )

    cli.main()

    project_md = out_dir / "PROJECT_STATE.md"
    project_json = out_dir / "PROJECT_STATE.json"
    bundle_path = out_dir / "snapshot_bundle.zip"
    assert project_md.exists()
    assert project_json.exists()
    assert (out_dir / "repo_tree.txt").exists()
    assert (out_dir / "db_schema.sql").exists()
    assert (out_dir / "prompt_templates").is_dir()
    assert (out_dir / "test_inventory.md").exists()
    assert (out_dir / "sanity_checks.md").exists()
    assert (out_dir / "SNAPSHOT_MANIFEST.json").exists()
    assert (out_dir / "README.md").exists()
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as bundle:
        names = set(bundle.namelist())
    assert "PROJECT_STATE.md" in names
    assert "PROJECT_STATE.json" in names
    assert "SNAPSHOT_MANIFEST.json" in names
