from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .benchmarks import BenchmarkManifest
from .contracts import Candidate, LaunchResult
from .utils import (
    deep_merge_dicts,
    normalize_python_command_prefix,
    read_json,
    set_nested_value,
    sha256_text,
    stable_json_dumps,
    utc_now_iso,
    write_json,
)


class LaunchError(RuntimeError):
    pass


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
    raise LaunchError("main-app automation did not emit a machine-readable JSON payload")


def _format_subprocess_failure(*, return_code: int, stdout: str, stderr: str) -> str:
    stderr_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    stdout_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    detail = stderr_lines[-1] if stderr_lines else (stdout_lines[-1] if stdout_lines else "no output captured")
    return f"main-app automation failed with exit code {return_code}: {detail}"


def _default_knob_path(knob_name: str) -> str:
    alias_map = {
        "retrieval_mode": "retrieval.mode",
        "retrieval_top_k": "retrieval.top_k",
        "typed_scoring_context": "retrieval.typed_scoring_context",
        "recall_rescue_enabled": "retrieval.recall_rescue_enabled",
        "whole_document_mode": "retrieval.whole_document_mode",
        "whole_document_max_chars": "retrieval.whole_document_max_chars",
        "parser_allow_basic_fallback": "parser.allow_basic_fallback",
        "style_profiles_enabled": "style_profiles.enabled",
        "style_profiles_max_examples": "style_profiles.max_examples",
        "figure_review_enabled": "figure_review.enabled",
        "text_temperature": "provider.text_model.temperature",
        "text_max_tokens": "provider.text_model.max_tokens",
        "text_top_p": "provider.text_model.top_p",
        "text_top_k": "provider.text_model.top_k",
        "text_min_p": "provider.text_model.min_p",
        "text_presence_penalty": "provider.text_model.presence_penalty",
        "text_repetition_penalty": "provider.text_model.repetition_penalty",
        "text_extra_body": "provider.text_model.extra_body",
        "text_chat_template_kwargs": "provider.text_model.chat_template_kwargs",
        "vision_temperature": "provider.vision_model.temperature",
        "vision_max_tokens": "provider.vision_model.max_tokens",
        "vision_top_p": "provider.vision_model.top_p",
        "vision_top_k": "provider.vision_model.top_k",
        "vision_min_p": "provider.vision_model.min_p",
        "vision_presence_penalty": "provider.vision_model.presence_penalty",
        "vision_repetition_penalty": "provider.vision_model.repetition_penalty",
        "vision_extra_body": "provider.vision_model.extra_body",
        "vision_chat_template_kwargs": "provider.vision_model.chat_template_kwargs",
    }
    return alias_map.get(knob_name, knob_name)


def build_main_app_overlay(config: dict[str, Any], *, candidate: Candidate) -> dict[str, Any]:
    main_cfg = config["main_app"]
    knob_map = dict(main_cfg.get("optimizer_knob_map", {}))

    overlay: dict[str, Any] = {
        "eval_mode": True,
        "verify_mode": False,
        "prompt": {"bundle": candidate.prompt_bundle_id},
        "provider": {
            "text_model": {"model_id": candidate.text_model_id},
            "vision_model": None if candidate.vision_model_id is None else {"model_id": candidate.vision_model_id},
        },
    }

    for knob_name, value in candidate.optimizer_knobs.items():
        path = knob_map.get(knob_name, _default_knob_path(knob_name))
        set_nested_value(overlay, path, value)

    return overlay


def build_resolved_main_config(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    benchmark: BenchmarkManifest,
    run_output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    main_cfg = config["main_app"]
    base_config_path = Path(main_cfg["base_config_path"])
    base_config = read_json(base_config_path)
    overlay = build_main_app_overlay(config, candidate=candidate)
    resolved = deep_merge_dicts(base_config, overlay)
    resolved["output_dir"] = str(run_output_dir.resolve())

    if benchmark.table_path:
        resolved["table_path"] = benchmark.table_path
    if benchmark.schema_path:
        resolved["schema_path"] = benchmark.schema_path
    if benchmark.pdf_dir:
        resolved["pdf_dir"] = benchmark.pdf_dir

    return overlay, resolved


def _write_launch_metadata_files(
    out_dir: Path,
    *,
    overlay: dict[str, Any],
    resolved_config: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    overlay_path = out_dir / "main_config_overlay.json"
    resolved_config_path = out_dir / "resolved_main_config.json"
    write_json(overlay_path, overlay)
    write_json(resolved_config_path, resolved_config)

    artifact_paths = {
        "main_config_overlay_path": str(overlay_path.resolve()),
        "resolved_main_config_path": str(resolved_config_path.resolve()),
        "main_config_overlay_hash": sha256_text(stable_json_dumps(overlay)),
        "resolved_main_config_hash": sha256_text(stable_json_dumps(resolved_config)),
    }

    if payload is not None:
        payload_path = out_dir / "automation_result.json"
        write_json(payload_path, payload)
        artifact_paths["automation_result_path"] = str(payload_path.resolve())

    return artifact_paths


def _build_real_main_command(main_cfg: dict[str, Any], resolved_config_path: Path, benchmark: BenchmarkManifest) -> tuple[list[str], str]:
    command_prefix = normalize_python_command_prefix(
        main_cfg.get(
            "command_prefix",
            [main_cfg.get("python_executable") or sys.executable, "-m", main_cfg.get("module", "backend.app.automation")],
        )
    )
    command = command_prefix + ["start", "--config-path", str(resolved_config_path), "--wait"]
    timeout_seconds = main_cfg.get("timeout_seconds")
    if timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(timeout_seconds)])
    command.extend(list(benchmark.main_args))
    command.extend(list(main_cfg.get("main_args", [])))
    return command, str(Path(main_cfg["repo_root"]).resolve())


def _legacy_launch_main_app(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    candidate_manifest_path: Path,
    benchmark_id: str,
    out_dir: Path,
) -> LaunchResult:
    main_cfg = config["main_app"]
    replacements = {
        "candidate_manifest": str(candidate_manifest_path),
        "benchmark_id": benchmark_id,
        "out_dir": str(out_dir),
        "candidate_id": candidate.candidate_id,
    }
    command = _render_command(main_cfg["command"], replacements)
    command.extend(config["benchmarks"]["manifests"].get(benchmark_id, {}).get("main_args", []))

    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    ended_at = utc_now_iso()
    duration_seconds = time.monotonic() - started_monotonic

    reference_file = out_dir / main_cfg.get("run_reference_file", "main_run.json")
    run_id = None
    run_path = None
    payload: dict[str, Any] = {}
    artifact_paths: dict[str, Any] = {}
    if reference_file.exists():
        payload = read_json(reference_file)
        artifact_paths["run_reference_path"] = str(reference_file.resolve())
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
        duration_seconds=duration_seconds,
        run_id=run_id,
        run_path=run_path,
        output_path=str(out_dir.resolve()),
        payload=payload,
        artifact_paths=artifact_paths,
    )


def launch_main_app(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    candidate_manifest_path: Path,
    benchmark: BenchmarkManifest,
    benchmark_id: str,
    out_dir: Path,
) -> LaunchResult:
    main_cfg = config["main_app"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if "base_config_path" not in main_cfg:
        return _legacy_launch_main_app(
            config,
            candidate=candidate,
            candidate_manifest_path=candidate_manifest_path,
            benchmark_id=benchmark_id,
            out_dir=out_dir,
        )

    main_run_output_dir = out_dir / "out"
    overlay, resolved_config = build_resolved_main_config(
        config,
        candidate=candidate,
        benchmark=benchmark,
        run_output_dir=main_run_output_dir,
    )
    initial_artifacts = _write_launch_metadata_files(out_dir, overlay=overlay, resolved_config=resolved_config)
    resolved_config_path = Path(initial_artifacts["resolved_main_config_path"])
    command, working_dir = _build_real_main_command(main_cfg, resolved_config_path, benchmark)

    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False, cwd=working_dir)
    ended_at = utc_now_iso()
    duration_seconds = time.monotonic() - started_monotonic

    try:
        payload = _parse_json_stdout(proc.stdout)
    except LaunchError as exc:
        raise LaunchError(
            _format_subprocess_failure(return_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
        ) from exc
    artifact_paths = _write_launch_metadata_files(out_dir, overlay=overlay, resolved_config=resolved_config, payload=payload)
    artifact_paths.update(initial_artifacts)

    artifacts = payload.get("artifacts", {}) if isinstance(payload, dict) else {}
    run_id = payload.get("run_id")
    run_path = artifacts.get("run_dir") or payload.get("run_path")

    success = proc.returncode == 0 and bool(run_id) and bool(run_path)
    required_paths = [artifacts.get("run_dir"), artifacts.get("run_json_path")]
    if success and any(not path for path in required_paths):
        raise LaunchError("main-app automation payload is missing required run artifact paths")

    return LaunchResult(
        success=success,
        command=command,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        run_id=str(run_id) if run_id is not None else None,
        run_path=str(run_path) if run_path is not None else None,
        working_dir=working_dir,
        output_path=str(out_dir.resolve()),
        payload=payload,
        artifact_paths={**artifact_paths, **artifacts},
    )
