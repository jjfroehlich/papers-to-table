from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .benchmarks import BenchmarkManifest
from .contracts import LaunchResult
from .utils import read_json, utc_now_iso, write_json


def _render_command(command_template: list[str], replacements: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for token in command_template:
        rendered.append(token.format(**replacements))
    return rendered


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("eval CLI did not emit a machine-readable JSON payload")


def _format_subprocess_failure(*, return_code: int, stdout: str, stderr: str) -> str:
    stderr_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    stdout_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    detail = stderr_lines[-1] if stderr_lines else (stdout_lines[-1] if stdout_lines else "no output captured")
    return f"eval CLI failed with exit code {return_code}: {detail}"


def _resolve_run_bundled_gold_path(main_run_dir: Path | None) -> Path | None:
    if main_run_dir is None:
        return None
    run_json_path = main_run_dir / "run.json"
    if not run_json_path.exists():
        return None
    try:
        run_payload = read_json(run_json_path)
    except Exception:
        return None
    eval_artifacts = run_payload.get("eval_artifacts") if isinstance(run_payload, dict) else None
    if not isinstance(eval_artifacts, dict):
        return None
    gold_table = eval_artifacts.get("gold_table")
    if not isinstance(gold_table, dict):
        return None
    snapshot_path = gold_table.get("snapshot_path")
    if not isinstance(snapshot_path, str) or not snapshot_path.strip():
        return None
    candidate = Path(snapshot_path)
    resolved = candidate if candidate.is_absolute() else (main_run_dir / candidate)
    resolved = resolved.resolve()
    if not resolved.exists():
        return None
    return resolved


def _metric_group_from_mapping(
    mapping: dict[str, str] | list[str] | None,
    *,
    flat_metrics: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, float]:
    if mapping is None:
        return {}

    grouped: dict[str, float] = {}
    if isinstance(mapping, list):
        for metric_name in mapping:
            value = flat_metrics.get(metric_name, summary.get(metric_name))
            if isinstance(value, (int, float)):
                grouped[metric_name] = float(value)
        return grouped

    for metric_name, source_name in mapping.items():
        value = flat_metrics.get(source_name, summary.get(source_name))
        if isinstance(value, (int, float)):
            grouped[metric_name] = float(value)
    return grouped


def map_eval_summary_to_metric_groups(
    eval_summary: dict[str, Any],
    eval_cfg: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    if any(group_name in eval_summary for group_name in ["primary_metrics", "guardrail_metrics", "diagnostic_metrics"]):
        primary = {k: float(v) for k, v in eval_summary.get("primary_metrics", {}).items() if isinstance(v, (int, float))}
        guardrail = {k: float(v) for k, v in eval_summary.get("guardrail_metrics", {}).items() if isinstance(v, (int, float))}
        diagnostic = {k: float(v) for k, v in eval_summary.get("diagnostic_metrics", {}).items() if isinstance(v, (int, float))}
        return primary, guardrail, diagnostic

    flat_metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
    metric_groups = eval_cfg.get("metric_groups", {}) if isinstance(eval_cfg.get("metric_groups"), dict) else {}

    primary = _metric_group_from_mapping(metric_groups.get("primary"), flat_metrics=flat_metrics, summary=eval_summary)
    guardrail = _metric_group_from_mapping(metric_groups.get("guardrail"), flat_metrics=flat_metrics, summary=eval_summary)
    diagnostic = _metric_group_from_mapping(metric_groups.get("diagnostic"), flat_metrics=flat_metrics, summary=eval_summary)

    if not primary and not guardrail and not diagnostic:
        primary = {k: float(v) for k, v in flat_metrics.items() if isinstance(v, (int, float))}

    return primary, guardrail, diagnostic


def _legacy_launch_eval_app(
    config: dict[str, Any],
    *,
    benchmark_id: str,
    main_run_ref_path: Path,
    out_dir: Path,
) -> tuple[LaunchResult, dict[str, Any]]:
    eval_cfg = config["eval_app"]
    replacements = {
        "main_run_ref": str(main_run_ref_path),
        "benchmark_id": benchmark_id,
        "out_dir": str(out_dir),
    }
    command = _render_command(eval_cfg["command"], replacements)
    command.extend(config["benchmarks"]["manifests"].get(benchmark_id, {}).get("eval_args", []))

    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    ended_at = utc_now_iso()
    duration_seconds = time.monotonic() - started_monotonic

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
        duration_seconds=duration_seconds,
        summary_path=str(summary_file.resolve()) if summary_file.exists() else None,
        output_path=str(out_dir.resolve()),
    )
    return launch, summary


def launch_eval_app(
    config: dict[str, Any],
    *,
    benchmark: BenchmarkManifest,
    benchmark_id: str,
    main_run_ref_path: Path,
    main_run_dir: Path | None,
    out_dir: Path,
) -> tuple[LaunchResult, dict[str, Any]]:
    eval_cfg = config["eval_app"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if "command" in eval_cfg:
        return _legacy_launch_eval_app(
            config,
            benchmark_id=benchmark_id,
            main_run_ref_path=main_run_ref_path,
            out_dir=out_dir,
        )

    if main_run_dir is None:
        raise ValueError("main_run_dir is required for real eval-app integration")
    bundled_gold_path = _resolve_run_bundled_gold_path(main_run_dir)
    gold_path = str(bundled_gold_path) if bundled_gold_path is not None else benchmark.gold_path
    if not gold_path:
        raise ValueError(f"Benchmark '{benchmark_id}' is missing gold_path required for eval")

    command_prefix = list(
        eval_cfg.get(
            "command_prefix",
            [eval_cfg.get("python_executable") or sys.executable, "-m", eval_cfg.get("module", "paper_eval")],
        )
    )
    command = command_prefix + [
        "evaluate",
        "--run",
        str(main_run_dir),
        "--gold",
        gold_path,
        "--out",
        str(out_dir),
        "--json-output",
    ]
    if benchmark.gold_sheet:
        command.extend(["--gold-sheet", benchmark.gold_sheet])
    if benchmark.eval_schema_path:
        command.extend(["--schema", benchmark.eval_schema_path])
    command.extend(list(benchmark.eval_args))

    working_dir = str(Path(eval_cfg["repo_root"]).resolve())
    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False, cwd=working_dir)
    ended_at = utc_now_iso()
    duration_seconds = time.monotonic() - started_monotonic

    try:
        payload = _parse_json_stdout(proc.stdout)
    except ValueError as exc:
        raise ValueError(_format_subprocess_failure(return_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)) from exc
    payload_path = out_dir / "eval_result.json"
    write_json(payload_path, payload)

    run_summary_paths = payload.get("run_summary_paths", []) if isinstance(payload, dict) else []
    summary_path = Path(run_summary_paths[0]) if run_summary_paths else None
    summary: dict[str, Any] = {}
    if summary_path and summary_path.exists():
        summary = read_json(summary_path)

    launch = LaunchResult(
        success=proc.returncode == 0 and bool(summary),
        command=command,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        run_id=(payload.get("run_ids") or [None])[0],
        run_path=str(main_run_dir.resolve()),
        summary_path=str(summary_path.resolve()) if summary_path and summary_path.exists() else None,
        working_dir=working_dir,
        output_path=str(out_dir.resolve()),
        payload=payload,
        artifact_paths={
            "eval_result_path": str(payload_path.resolve()),
            "gold_path": gold_path,
            "compare_dir": payload.get("compare_dir"),
            "per_run_dir": payload.get("per_run_dir"),
            "runs_comparison_csv": (payload.get("comparison_artifacts") or {}).get("runs_comparison_csv"),
            "runs_comparison_xlsx": (payload.get("comparison_artifacts") or {}).get("runs_comparison_xlsx"),
            "runs_comparison_parquet": (payload.get("comparison_artifacts") or {}).get("runs_comparison_parquet"),
        },
    )
    return launch, summary
