from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .contracts import LaunchResult
from .utils import read_json, utc_now_iso


def _render_command(command_template: list[str], replacements: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for token in command_template:
        rendered.append(token.format(**replacements))
    return rendered


def launch_eval_app(
    config: dict[str, Any],
    *,
    benchmark_id: str,
    main_run_ref_path: Path,
    out_dir: Path,
) -> tuple[LaunchResult, dict[str, Any]]:
    eval_cfg = config["eval_app"]
    out_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "main_run_ref": str(main_run_ref_path),
        "benchmark_id": benchmark_id,
        "out_dir": str(out_dir),
    }
    command = _render_command(eval_cfg["command"], replacements)
    command.extend(config["benchmarks"]["manifests"].get(benchmark_id, {}).get("eval_args", []))

    started_at = utc_now_iso()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    ended_at = utc_now_iso()

    summary_file = out_dir / eval_cfg.get("summary_file", "eval_summary.json")
    summary: dict[str, Any] = {}
    if summary_file.exists():
        summary = read_json(summary_file)

    launch = LaunchResult(
        success=proc.returncode == 0,
        command=command,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=0.0,
        output_path=str(out_dir),
    )
    return launch, summary
