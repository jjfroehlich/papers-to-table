from __future__ import annotations

import importlib.metadata as im
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _project_name() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return data["project"]["name"]


def test_console_script_entrypoint() -> None:
    distribution = im.distribution(_project_name())
    console_scripts = {
        entrypoint.name: entrypoint.value
        for entrypoint in distribution.entry_points
        if entrypoint.group == "console_scripts"
    }
    assert console_scripts.get("paper-table-agent") == "paper_table_agent.cli:main"
