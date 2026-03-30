from __future__ import annotations

import json
import os
import pathlib
from typing import Any


def get_run_dir(output_dir: str, run_id: str) -> pathlib.Path:
    return pathlib.Path(output_dir) / run_id


def get_run_json_path(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "run.json"


def get_config_snapshot_path(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "config.snapshot.json"


def get_input_summary_path(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "inputs" / "input_summary.json"


def get_proposals_dir(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "proposals"


def get_evidence_dir(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "evidence"


def get_review_dir(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "review"


def get_run_summary_path(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "summaries" / "run_summary.json"


def get_reviewer_summary_path(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "summaries" / "reviewer_summary.json"


def get_logs_dir(output_dir: str, run_id: str) -> pathlib.Path:
    return get_run_dir(output_dir, run_id) / "logs"


def init_run_bundle(output_dir: str, run_id: str) -> pathlib.Path:
    """Create the full directory structure for a run bundle."""
    run_dir = get_run_dir(output_dir, run_id)
    subdirs = [
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
    run_dir.mkdir(parents=True, exist_ok=True)
    for sub in subdirs:
        (run_dir / sub).mkdir(exist_ok=True)
    return run_dir


def write_json(path: pathlib.Path, data: Any) -> None:
    """Atomic write: write to .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def read_json(path: pathlib.Path) -> Any:
    """Read JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_jsonl(path: pathlib.Path, record: Any) -> None:
    """Append a record as a JSON line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: pathlib.Path) -> list[Any]:
    """Read all records from a JSONL file."""
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def lookup_by_id(jsonl_path: pathlib.Path, id_field: str, id_value: str) -> Any | None:
    """Lookup a record by id from a JSONL file."""
    for record in read_jsonl(jsonl_path):
        if record.get(id_field) == id_value:
            return record
    return None


def list_run_ids(output_dir: str) -> list[str]:
    """List all run IDs in output_dir."""
    base = pathlib.Path(output_dir)
    if not base.exists():
        return []
    return [
        d.name
        for d in base.iterdir()
        if d.is_dir() and (d / "run.json").exists()
    ]
