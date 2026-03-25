from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


BUNDLE_DIRS = [
    "inputs",
    "style_profiles",
    "parsed",
    "matching",
    "retrieval",
    "proposals",
    "evidence",
    "review",
    "summaries",
    "exports",
    "logs",
]


class RunArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def create(cls, output_dir: Path, run_id: str) -> "RunArtifacts":
        run_root = output_dir / run_id
        run_root.mkdir(parents=True, exist_ok=False)
        for directory in BUNDLE_DIRS:
            (run_root / directory).mkdir(parents=True, exist_ok=True)
        return cls(run_root)

    def path(self, relative_path: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative_path: str, payload: Any) -> Path:
        destination = self.path(relative_path)
        atomic_write_json(destination, payload)
        return destination

    def read_json(self, relative_path: str) -> Any:
        with self.path(relative_path).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def append_jsonl(self, relative_path: str, record: dict[str, Any]) -> Path:
        destination = self.path(relative_path)
        line = json.dumps(record, ensure_ascii=False)
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return destination

    def read_jsonl(self, relative_path: str) -> list[dict[str, Any]]:
        source = self.path(relative_path)
        if not source.exists():
            return []
        rows: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if raw:
                    rows.append(json.loads(raw))
        return rows

    def find_by_id(self, relative_path: str, id_field: str, value: str) -> dict[str, Any] | None:
        for item in self.read_jsonl(relative_path):
            if item.get(id_field) == value:
                return item
        return None


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
