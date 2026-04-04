from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputLayout:
    root: Path
    per_run_root: Path

    def run_dir(self, run_id: str) -> Path:
        return self.per_run_root / run_id


def create_output_layout(root: Path) -> OutputLayout:
    root.mkdir(parents=True, exist_ok=True)
    per_run_root = root / "per-run"
    per_run_root.mkdir(parents=True, exist_ok=True)
    return OutputLayout(root=root, per_run_root=per_run_root)
