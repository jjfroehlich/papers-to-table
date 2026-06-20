#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

SCRATCH_DIRNAME = "scratch_delete_after_success"
SCRATCH_ROOT_MARKER = ".papers_to_table_scratch_root"
SCRATCH_RUN_MARKER = ".papers_to_table_scratch"


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def cleanup_scratch(output_dir: Path, *, run_ids: list[str] | None = None) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    scratch_root = (output_dir / SCRATCH_DIRNAME).resolve()
    if not _is_within(scratch_root, output_dir):
        raise ValueError("Scratch root must be inside output_dir.")
    if not scratch_root.exists():
        return {"output_dir": str(output_dir), "scratch_dir": str(scratch_root), "deleted": [], "missing": True}
    if not (scratch_root / SCRATCH_ROOT_MARKER).exists():
        return {
            "output_dir": str(output_dir),
            "scratch_dir": str(scratch_root),
            "deleted": [],
            "skipped": [str(scratch_root)],
            "missing": False,
            "reason": "missing_scratch_root_marker",
        }

    targets: list[Path]
    if run_ids:
        targets = [(scratch_root / run_id).resolve() for run_id in run_ids]
    else:
        targets = [path.resolve() for path in scratch_root.iterdir() if path.name != SCRATCH_ROOT_MARKER]

    deleted: list[str] = []
    skipped: list[str] = []
    for target in targets:
        if not _is_within(target, scratch_root) or target == scratch_root:
            skipped.append(str(target))
            continue
        if not target.exists():
            skipped.append(str(target))
            continue
        if target.is_dir():
            if not (target / SCRATCH_RUN_MARKER).exists():
                skipped.append(str(target))
                continue
            shutil.rmtree(target)
        else:
            skipped.append(str(target))
            continue
        deleted.append(str(target))

    return {
        "output_dir": str(output_dir),
        "scratch_dir": str(scratch_root),
        "deleted": deleted,
        "skipped": skipped,
        "missing": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete only papers-to-table scratch_delete_after_success artifacts.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output workspace containing scratch_delete_after_success/.")
    parser.add_argument("--run-id", action="append", default=[], help="Limit cleanup to one run ID. Repeat for multiple runs.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable cleanup results.")
    args = parser.parse_args(argv)

    result = cleanup_scratch(args.output_dir, run_ids=args.run_id or None)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    for path in result["deleted"]:
        print(f"deleted: {path}")
    for path in result.get("skipped", []):
        print(f"skipped: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
