from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RunInfo:
    run_dir: Path
    label: str
    status: str
    table_path: str | None
    pdf_folder: str | None


def discover_runs(root: Path = Path("runs")) -> list[RunInfo]:
    runs: list[RunInfo] = []
    if not root.exists():
        return runs
    for run_dir in sorted(root.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        config_path = run_dir / "run_config.json"
        if not config_path.exists():
            continue
        status = _infer_run_status(run_dir)
        table_path = None
        pdf_folder = None
        try:
            data = config_path.read_text(encoding="utf-8")
            table_path = _extract_json_value(data, "table_path")
            pdf_folder = _extract_json_value(data, "pdf_folder")
        except OSError:
            pass
        runs.append(
            RunInfo(
                run_dir=run_dir,
                label=f"{run_dir.name} ({status})",
                status=status,
                table_path=table_path,
                pdf_folder=pdf_folder,
            )
        )
    return runs


def discover_tables(root: Path = Path(".")) -> list[Path]:
    tables: list[Path] = []
    for path in _walk_files(root, {".xlsx", ".csv"}):
        tables.append(path)
    return sorted(tables)


def discover_pdf_folders(root: Path = Path(".")) -> list[Path]:
    folders: set[Path] = set()
    for path in _walk_files(root, {".pdf"}):
        folders.add(path.parent)
    return sorted(folders)


def _infer_run_status(run_dir: Path) -> str:
    if (run_dir / "PAUSE").exists():
        return "paused"
    if (run_dir / "STOP").exists():
        return "stopped"
    if (run_dir / "FAILED").exists():
        return "failed"
    if (run_dir / "COMPLETED").exists():
        return "completed"
    if (run_dir / "exports" / "updated_table.xlsx").exists():
        return "completed"
    if (run_dir / "proposals.sqlite").exists():
        return "in_progress"
    return "unknown"


def _walk_files(root: Path, suffixes: Iterable[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            if _is_ignored_dir(path):
                continue
            continue
        if path.suffix.lower() in suffixes and not _is_ignored_dir(path.parent):
            yield path


def _is_ignored_dir(path: Path) -> bool:
    parts = set(path.parts)
    return any(part.startswith(".") for part in parts) or "runs" in parts or "venv" in parts


def _extract_json_value(data: str, key: str) -> str | None:
    marker = f'"{key}":'
    idx = data.find(marker)
    if idx == -1:
        return None
    start = data.find("\"", idx + len(marker))
    if start == -1:
        return None
    end = data.find("\"", start + 1)
    if end == -1:
        return None
    return data[start + 1 : end]
