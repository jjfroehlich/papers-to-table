from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_default_run_config(path: Path = Path("run_config.json")) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def resolve_default_paths(defaults: dict[str, Any]) -> tuple[str | None, str | None]:
    return defaults.get("table_path"), defaults.get("pdf_folder")
