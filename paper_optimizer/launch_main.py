from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .contracts import Candidate, LaunchResult
from .utils import read_json, utc_now_iso


class LaunchError(RuntimeError):
    pass


def _render_command(command_template: list[str], replacements: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for token in command_template:
        rendered.append(token.format(**replacements))
    return rendered


def launch_main_app(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    candidate_manifest_path: Path,
    benchmark_id: str,
    out_dir: Path,
) -> LaunchResult:
    main_cfg = config["main_app"]
    out_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "candidate_manifest": str(candidate_manifest_path),
        "benchmark_id": benchmark_id,
        "out_dir": str(out_dir),
        "candidate_id": candidate.candidate_id,
    }
    command = _render_command(main_cfg["command"], replacements)
    command.extend(config["benchmarks"]["manifests"].get(benchmark_id, {}).get("main_args", []))

    started_at = utc_now_iso()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    ended_at = utc_now_iso()

    reference_file = out_dir / main_cfg.get("run_reference_file", "main_run.json")
    run_id = None
    run_path = None
    if reference_file.exists():
        payload = read_json(reference_file)
        run_id = payload.get("run_id")
        run_path = payload.get("run_path")

    return LaunchResult(
        success=proc.returncode == 0,
        command=command,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=0.0,
        run_id=run_id,
        run_path=run_path,
        output_path=str(out_dir),
    )
