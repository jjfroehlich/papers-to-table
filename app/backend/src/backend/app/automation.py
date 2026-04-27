from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from .artifacts import (
    get_config_snapshot_path,
    get_provider_model_management_path,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    read_json,
)
from .config import RunConfig, apply_overrides, check_readiness, get_run_mode, load_config
from .export import run_export
from .extraction import load_proposals
from .ids import generate_run_id
from .ingest import load_schema, load_table
from .review import bulk_accept_proposals, get_export_candidates, get_latest_decision, recompute_summaries
from .runner import run_pipeline
from .schemas import DecisionSource, ProposalState, RunStatus

AUTOMATION_PAYLOAD_SCHEMA_VERSION = "main_app_automation.v1"
HEADLESS_ACCEPT_ALL_NOTE = "Auto-accepted by headless CLI (--accept-all)."

TERMINAL_STATUSES = {
    RunStatus.completed.value,
    RunStatus.completed_with_warnings.value,
    RunStatus.failed.value,
    RunStatus.interrupted.value,
}


def _is_terminal_status(status: Optional[str]) -> bool:
    return str(status or "") in TERMINAL_STATUSES


def _resolve_path_like(value: str, base_dir: pathlib.Path) -> str:
    candidate = pathlib.Path(value)
    if candidate.is_absolute():
        return str(candidate.resolve())
    return str((base_dir / candidate).resolve())


def _resolve_config_and_inputs(
    config_path: str,
    table_path: Optional[str],
    schema_path: Optional[str],
    pdf_dir: Optional[str],
) -> tuple[RunConfig, dict[str, Any], str]:
    resolved_config_path = str(pathlib.Path(config_path).resolve())
    config = load_config(resolved_config_path)
    config_base_dir = pathlib.Path(resolved_config_path).parent

    resolved_inputs: dict[str, Any] = {
        "table_path": {
            "source_kind": "config",
            "logical_source": config.table_path,
            "runtime_locator": config.table_path,
        },
        "schema_path": {
            "source_kind": "config",
            "logical_source": config.schema_path,
            "runtime_locator": config.schema_path,
        },
        "pdf_dir": {
            "source_kind": "config",
            "logical_source": config.pdf_dir,
            "runtime_locator": config.pdf_dir,
        },
    }

    overrides: dict[str, str] = {}

    if table_path:
        overrides["table_path"] = table_path
        resolved_inputs["table_path"] = {
            "source_kind": "path_override",
            "logical_source": table_path,
            "runtime_locator": _resolve_path_like(table_path, config_base_dir),
        }

    if schema_path:
        overrides["schema_path"] = schema_path
        resolved_inputs["schema_path"] = {
            "source_kind": "path_override",
            "logical_source": schema_path,
            "runtime_locator": _resolve_path_like(schema_path, config_base_dir),
        }

    if pdf_dir:
        overrides["pdf_dir"] = pdf_dir
        resolved_inputs["pdf_dir"] = {
            "source_kind": "path_override",
            "logical_source": pdf_dir,
            "runtime_locator": _resolve_path_like(pdf_dir, config_base_dir),
        }

    if overrides:
        config = apply_overrides(config, overrides, base_dir=str(config_base_dir))

    return config, resolved_inputs, resolved_config_path


def _latest_export_path(run_dir: pathlib.Path) -> Optional[str]:
    exports_dir = run_dir / "exports"
    if not exports_dir.exists():
        return None
    files = [p for p in exports_dir.glob("*.xlsx") if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0].resolve())


def _run_artifact_paths(output_dir: str, run_id: str) -> dict[str, Optional[str]]:
    run_dir = get_run_dir(output_dir, run_id)
    run_json = get_run_json_path(output_dir, run_id)
    config_snapshot = get_config_snapshot_path(output_dir, run_id)
    run_summary = get_run_summary_path(output_dir, run_id)
    reviewer_summary = get_reviewer_summary_path(output_dir, run_id)
    provider_model_management = get_provider_model_management_path(output_dir, run_id)
    return {
        "run_dir": str(run_dir.resolve()),
        "run_json_path": str(run_json.resolve()),
        "config_snapshot_path": str(config_snapshot.resolve()) if config_snapshot.exists() else None,
        "run_summary_path": str(run_summary.resolve()) if run_summary.exists() else None,
        "reviewer_summary_path": str(reviewer_summary.resolve()) if reviewer_summary.exists() else None,
        "provider_model_management_path": (
            str(provider_model_management.resolve()) if provider_model_management.exists() else None
        ),
        "latest_export_path": _latest_export_path(run_dir),
    }


def _build_output_payload(
    run_id: str,
    config: RunConfig,
    config_path: str,
    resolved_inputs: dict[str, Any],
    status: str,
    run_data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    mode = run_data.get("run_mode") if run_data else get_run_mode(config)
    is_terminal = _is_terminal_status(status)
    artifacts = _run_artifact_paths(config.output_dir, run_id)

    payload: dict[str, Any] = {
        "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "is_terminal": is_terminal,
        "mode": mode,
        "config_path": config_path,
        "output_dir": str(pathlib.Path(config.output_dir).resolve()),
        "resolved_inputs": resolved_inputs,
        "artifacts": artifacts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if run_data:
        payload["current_stage"] = run_data.get("current_stage")
        payload["error_message"] = run_data.get("error_message")
        payload["provider_readiness_error"] = run_data.get("provider_readiness_error")
        payload["provider_readiness_reason"] = run_data.get("provider_readiness_reason")
        payload["structured_output_mode"] = run_data.get("structured_output_mode")
        payload["structured_output_reason"] = run_data.get("structured_output_reason")
        payload["prompt_only_degraded_mode_used"] = bool(
            run_data.get("prompt_only_degraded_mode_used", False)
        )
        payload["style_profile_mode"] = run_data.get("style_profile_mode")
        payload["style_profile_source"] = run_data.get("style_profile_source")
        payload["style_profile_benchmark_safe"] = run_data.get("style_profile_benchmark_safe")
        payload["parser_cache_enabled"] = run_data.get("parser_cache_enabled")
        payload["parser_cache_dir"] = run_data.get("parser_cache_dir")
        payload["parse_cache_hit_count"] = int(run_data.get("parse_cache_hit_count", 0) or 0)
        payload["parse_cache_miss_count"] = int(run_data.get("parse_cache_miss_count", 0) or 0)
        payload["parse_repair_used"] = bool(run_data.get("parse_repair_used", False))
        payload["extraction_contract_valid"] = bool(
            run_data.get("extraction_contract_valid", False)
        )
        payload["extraction_contract_warnings"] = run_data.get("extraction_contract_warnings") or []
        payload["vision_structured_output_mode"] = run_data.get("vision_structured_output_mode")
        payload["vision_structured_output_reason"] = run_data.get("vision_structured_output_reason")
        payload["warnings"] = run_data.get("warnings") or []
        payload["run_summary"] = {
            "prompt_hash": run_data.get("prompt_hash"),
            "prompt_bundle_id": run_data.get("prompt_bundle_id"),
            "retrieval_mode": run_data.get("retrieval_mode"),
            "retrieval_top_k": run_data.get("retrieval_top_k"),
            "recall_rescue_enabled": bool(run_data.get("recall_rescue_enabled", False)),
            "whole_document_mode": bool(run_data.get("whole_document_mode", False)),
            "whole_document_max_chars": run_data.get("whole_document_max_chars"),
            "recall_rescue_used": bool(run_data.get("recall_rescue_used", False)),
            "recall_rescue_used_any": bool(run_data.get("recall_rescue_used_any", False)),
            "recall_rescue_invocation_count": int(run_data.get("recall_rescue_invocation_count", 0) or 0),
            "provider_mode": run_data.get("provider_mode"),
            "structured_output_mode": run_data.get("structured_output_mode"),
            "structured_output_reason": run_data.get("structured_output_reason"),
            "prompt_only_degraded_mode_used": bool(
                run_data.get("prompt_only_degraded_mode_used", False)
            ),
            "style_profile_mode": run_data.get("style_profile_mode"),
            "style_profile_source": run_data.get("style_profile_source"),
            "style_profile_benchmark_safe": run_data.get("style_profile_benchmark_safe"),
            "parser_cache_enabled": run_data.get("parser_cache_enabled"),
            "parser_cache_dir": run_data.get("parser_cache_dir"),
            "parse_cache_hit_count": int(run_data.get("parse_cache_hit_count", 0) or 0),
            "parse_cache_miss_count": int(run_data.get("parse_cache_miss_count", 0) or 0),
            "parse_repair_used": bool(run_data.get("parse_repair_used", False)),
            "extraction_contract_valid": bool(
                run_data.get("extraction_contract_valid", False)
            ),
            "extraction_contract_warnings": run_data.get("extraction_contract_warnings") or [],
            "retrieval_provenance": run_data.get("retrieval_provenance") or {},
        }
    return payload


def _load_run_data(output_dir: str, run_id: str) -> Optional[dict[str, Any]]:
    run_json_path = get_run_json_path(output_dir, run_id)
    if not run_json_path.exists():
        return None
    try:
        return read_json(run_json_path)
    except Exception:
        return None


async def _wait_for_terminal_status(
    *,
    run_id: str,
    output_dir: str,
    poll_interval: float,
    timeout_seconds: Optional[float],
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).timestamp()
    while True:
        run_data = _load_run_data(output_dir, run_id)
        if run_data and str(run_data.get("status")) in TERMINAL_STATUSES:
            return run_data

        if timeout_seconds is not None:
            elapsed = datetime.now(timezone.utc).timestamp() - started
            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    f"Timed out waiting for run {run_id} to reach a terminal state after {timeout_seconds} seconds"
                )
        await asyncio.sleep(poll_interval)


def _spawn_detached_worker(
    *,
    run_id: str,
    config_path: str,
    table_path: Optional[str],
    schema_path: Optional[str],
    pdf_dir: Optional[str],
) -> int:
    cmd = [
        sys.executable,
        "-m",
        "backend.app.automation",
        "_run-worker",
        "--run-id",
        run_id,
        "--config-path",
        config_path,
    ]
    if table_path:
        cmd.extend(["--table-path", table_path])
    if schema_path:
        cmd.extend(["--schema-path", schema_path])
    if pdf_dir:
        cmd.extend(["--pdf-dir", pdf_dir])

    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
        "cwd": str(pathlib.Path(config_path).resolve().parent),
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(cmd, **kwargs)
    return int(process.pid)


async def _run_worker(
    *,
    run_id: str,
    config_path: str,
    table_path: Optional[str],
    schema_path: Optional[str],
    pdf_dir: Optional[str],
) -> None:
    config, resolved_inputs, resolved_config_path = _resolve_config_and_inputs(
        config_path,
        table_path,
        schema_path,
        pdf_dir,
    )
    await run_pipeline(
        run_id=run_id,
        config=config,
        config_path=resolved_config_path,
        output_dir=config.output_dir,
        resolved_inputs=resolved_inputs,
    )


def run_start(
    *,
    config_path: str,
    table_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    pdf_dir: Optional[str] = None,
    wait: bool = False,
    poll_interval: float = 0.5,
    timeout_seconds: Optional[float] = None,
) -> tuple[int, dict[str, Any]]:
    config, resolved_inputs, resolved_config_path = _resolve_config_and_inputs(
        config_path,
        table_path,
        schema_path,
        pdf_dir,
    )
    run_id = generate_run_id()

    if wait:
        async def _run_and_wait() -> dict[str, Any]:
            pipeline_task = asyncio.create_task(
                run_pipeline(
                    run_id=run_id,
                    config=config,
                    config_path=resolved_config_path,
                    output_dir=config.output_dir,
                    resolved_inputs=resolved_inputs,
                )
            )
            try:
                if timeout_seconds is not None:
                    await asyncio.wait_for(pipeline_task, timeout=timeout_seconds)
                else:
                    await pipeline_task
            except asyncio.TimeoutError as exc:
                pipeline_task.cancel()
                raise TimeoutError(
                    f"Timed out waiting for run {run_id} after {timeout_seconds} seconds"
                ) from exc

            run_data = _load_run_data(config.output_dir, run_id) or {"status": RunStatus.failed.value}
            return run_data

        try:
            final_run_data = asyncio.run(_run_and_wait())
        except TimeoutError as exc:
            timeout_payload = _build_output_payload(
                run_id=run_id,
                config=config,
                config_path=resolved_config_path,
                resolved_inputs=resolved_inputs,
                status="timeout",
                run_data=_load_run_data(config.output_dir, run_id),
            )
            timeout_payload["error_message"] = str(exc)
            return 3, timeout_payload

        final_status = str(final_run_data.get("status", RunStatus.failed.value))
        payload = _build_output_payload(
            run_id=run_id,
            config=config,
            config_path=resolved_config_path,
            resolved_inputs=resolved_inputs,
            status=final_status,
            run_data=final_run_data,
        )
        exit_code = 0 if final_status in {RunStatus.completed.value, RunStatus.completed_with_warnings.value} else 2
        return exit_code, payload

    pid = _spawn_detached_worker(
        run_id=run_id,
        config_path=resolved_config_path,
        table_path=table_path,
        schema_path=schema_path,
        pdf_dir=pdf_dir,
    )
    startup_payload = _build_output_payload(
        run_id=run_id,
        config=config,
        config_path=resolved_config_path,
        resolved_inputs=resolved_inputs,
        status=RunStatus.created.value,
        run_data=None,
    )
    startup_payload["worker_pid"] = pid
    return 0, startup_payload


def run_status(*, run_id: str, output_dir: str) -> tuple[int, dict[str, Any]]:
    run_data = _load_run_data(output_dir, run_id)
    if run_data is None:
        return 4, {
            "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
            "run_id": run_id,
            "status": "not_found",
            "is_terminal": False,
            "output_dir": str(pathlib.Path(output_dir).resolve()),
            "error_message": f"Run not found: {run_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    artifacts = _run_artifact_paths(output_dir, run_id)
    payload = {
        "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
        "run_id": run_id,
        "status": run_data.get("status"),
        "is_terminal": _is_terminal_status(run_data.get("status")),
        "mode": run_data.get("run_mode"),
        "output_dir": str(pathlib.Path(output_dir).resolve()),
        "artifacts": artifacts,
        "current_stage": run_data.get("current_stage"),
        "error_message": run_data.get("error_message"),
        "provider_readiness_error": run_data.get("provider_readiness_error"),
        "provider_readiness_reason": run_data.get("provider_readiness_reason"),
        "warnings": run_data.get("warnings") or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return 0, payload


def run_wait(
    *,
    run_id: str,
    output_dir: str,
    poll_interval: float = 0.5,
    timeout_seconds: Optional[float] = None,
) -> tuple[int, dict[str, Any]]:
    try:
        run_data = asyncio.run(
            _wait_for_terminal_status(
                run_id=run_id,
                output_dir=output_dir,
                poll_interval=poll_interval,
                timeout_seconds=timeout_seconds,
            )
        )
    except TimeoutError as exc:
        timeout_payload = {
            "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
            "run_id": run_id,
            "status": "timeout",
            "is_terminal": False,
            "output_dir": str(pathlib.Path(output_dir).resolve()),
            "error_message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return 3, timeout_payload

    exit_code, payload = run_status(run_id=run_id, output_dir=output_dir)
    final_status = str(run_data.get("status", ""))
    if final_status in {RunStatus.completed.value, RunStatus.completed_with_warnings.value}:
        return 0, payload
    if _is_terminal_status(final_status):
        return 2, payload
    return exit_code, payload


def run_preflight(
    *,
    config_path: str,
    table_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    pdf_dir: Optional[str] = None,
) -> tuple[int, dict[str, Any]]:
    config, resolved_inputs, resolved_config_path = _resolve_config_and_inputs(
        config_path,
        table_path,
        schema_path,
        pdf_dir,
    )
    readiness = asyncio.run(check_readiness(config))

    table_rows = None
    schema_columns = None
    pdf_count = None
    scope_warnings: list[str] = []

    try:
        table_rows = len(load_table(config.table_path))
    except Exception as exc:
        scope_warnings.append(f"Table preview unavailable: {exc}")
    try:
        schema_columns = len(load_schema(config.schema_path, config.table_path))
    except Exception as exc:
        scope_warnings.append(f"Schema preview unavailable: {exc}")
    try:
        pdf_count = len([path for path in pathlib.Path(config.pdf_dir).iterdir() if path.suffix.lower() == ".pdf"])
    except Exception as exc:
        scope_warnings.append(f"PDF scope preview unavailable: {exc}")

    payload = {
        "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
        "command": "preflight",
        "status": "ok" if readiness.ok else "readiness_failed",
        "config_path": resolved_config_path,
        "run_mode": get_run_mode(config),
        "output_dir": str(pathlib.Path(config.output_dir).resolve()),
        "resolved_inputs": resolved_inputs,
        "provider": {
            "token": config.provider.token,
            "locality": config.provider.locality,
            "base_url": config.provider.base_url,
            "text_model_id": config.provider.text_model.model_id,
            "vision_model_id": config.provider.vision_model.model_id if config.provider.vision_model else None,
        },
        "scope": {
            "table_rows": table_rows,
            "schema_columns": schema_columns,
            "pdf_count": pdf_count,
        },
        "readiness": {
            "ok": readiness.ok,
            "errors": readiness.errors,
            "warnings": readiness.warnings + scope_warnings,
            "provider_mode": readiness.provider_mode,
            "provider_readiness_reason": readiness.provider_readiness_reason,
            "provider_readiness_error": readiness.provider_readiness_error,
        },
        "what_happens_next": [
            "Validate inputs and provider readiness again at run start.",
            "Parse PDFs and resolve row matching before extraction.",
            "Generate one best proposal per eligible target cell with evidence.",
            "Review proposals explicitly in the browser UI or use headless mode with --accept-all for an auditable auto-review export.",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return (0 if readiness.ok else 2), payload


def _reviewable_undecided_proposal_ids(run_dir: pathlib.Path) -> list[str]:
    proposal_ids: list[str] = []
    for proposal in load_proposals(run_dir):
        if proposal.state in (ProposalState.blocked, ProposalState.skipped):
            continue
        if get_latest_decision(run_dir, proposal.proposal_id) is not None:
            continue
        proposal_ids.append(proposal.proposal_id)
    return proposal_ids


def run_headless(
    *,
    config_path: str,
    table_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    pdf_dir: Optional[str] = None,
    accept_all: bool = False,
    export: bool = False,
    poll_interval: float = 0.5,
    timeout_seconds: Optional[float] = None,
) -> tuple[int, dict[str, Any]]:
    preflight_exit, preflight_payload = run_preflight(
        config_path=config_path,
        table_path=table_path,
        schema_path=schema_path,
        pdf_dir=pdf_dir,
    )
    if preflight_exit != 0:
        preflight_payload["command"] = "headless"
        return preflight_exit, preflight_payload

    exit_code, payload = run_start(
        config_path=config_path,
        table_path=table_path,
        schema_path=schema_path,
        pdf_dir=pdf_dir,
        wait=True,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
    )
    payload["command"] = "headless"
    payload["preflight"] = preflight_payload
    payload["headless_accept_all_requested"] = bool(accept_all)
    payload["headless_export_requested"] = bool(export)

    if exit_code != 0:
        return exit_code, payload

    run_dir = pathlib.Path(payload["artifacts"]["run_dir"])
    run_id = str(payload["run_id"])
    undecided_reviewable_ids = _reviewable_undecided_proposal_ids(run_dir)
    payload["pending_reviewable_proposals"] = len(undecided_reviewable_ids)

    if export and undecided_reviewable_ids and not accept_all:
        payload["status"] = "review_required"
        payload["is_terminal"] = True
        payload["error_message"] = (
            "Export requires explicit review decisions. Re-run with --accept-all for auditable headless auto-accept."
        )
        return 2, payload

    accepted_decisions = []
    if accept_all:
        accepted_decisions = bulk_accept_proposals(
            run_dir,
            run_id,
            undecided_reviewable_ids,
            decision_source=DecisionSource.automation_accept_all,
            reviewer_note=HEADLESS_ACCEPT_ALL_NOTE,
        )
        summaries = recompute_summaries(run_dir, run_id)
        payload["reviewer_summary"] = summaries["reviewer_summary"]
        payload["run_summary"] = summaries["run_summary"]
    else:
        reviewer_summary_path_value = payload["artifacts"].get("reviewer_summary_path")
        if reviewer_summary_path_value:
            reviewer_summary_path = pathlib.Path(reviewer_summary_path_value)
            payload["reviewer_summary"] = read_json(reviewer_summary_path)

    payload["auto_accepted_proposals"] = len(accepted_decisions)

    if export:
        export_result = run_export(run_dir, payload["output_dir"], run_id)
        payload["export"] = export_result
        payload["accepted_export_candidates"] = len(get_export_candidates(run_dir))
        payload["artifacts"]["latest_export_path"] = export_result["workbook_path"]

    return 0, payload


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-runner",
        description="Stable non-UI automation entrypoint for run start and monitoring.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight", help="Resolve config and report scope/readiness")
    preflight_parser.add_argument("--config-path", required=True)
    preflight_parser.add_argument("--table-path")
    preflight_parser.add_argument("--schema-path")
    preflight_parser.add_argument("--pdf-dir")

    start_parser = subparsers.add_parser("start", help="Start a run from config with optional overrides")
    start_parser.add_argument("--config-path", required=True)
    start_parser.add_argument("--table-path")
    start_parser.add_argument("--schema-path")
    start_parser.add_argument("--pdf-dir")
    start_parser.add_argument("--wait", action="store_true", help="Wait for terminal state and return final status")
    start_parser.add_argument("--poll-interval", type=float, default=0.5)
    start_parser.add_argument("--timeout-seconds", type=float)

    status_parser = subparsers.add_parser("status", help="Read run status from run artifacts")
    status_parser.add_argument("--run-id", required=True)
    status_parser.add_argument("--output-dir", default="./runs")

    wait_parser = subparsers.add_parser("wait", help="Wait until a run reaches terminal state")
    wait_parser.add_argument("--run-id", required=True)
    wait_parser.add_argument("--output-dir", default="./runs")
    wait_parser.add_argument("--poll-interval", type=float, default=0.5)
    wait_parser.add_argument("--timeout-seconds", type=float)

    headless_parser = subparsers.add_parser(
        "headless",
        help="Run extraction without the browser UI and optionally auto-accept/export explicitly",
    )
    headless_parser.add_argument("--config-path", required=True)
    headless_parser.add_argument("--table-path")
    headless_parser.add_argument("--schema-path")
    headless_parser.add_argument("--pdf-dir")
    headless_parser.add_argument(
        "--accept-all",
        action="store_true",
        help="Explicitly auto-accept all undecided reviewable proposals. Required for unattended review bypass.",
    )
    headless_parser.add_argument(
        "--export",
        action="store_true",
        help="Write an audited export after extraction. Requires explicit review or --accept-all.",
    )
    headless_parser.add_argument("--poll-interval", type=float, default=0.5)
    headless_parser.add_argument("--timeout-seconds", type=float)

    worker_parser = subparsers.add_parser("_run-worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("--run-id", required=True)
    worker_parser.add_argument("--config-path", required=True)
    worker_parser.add_argument("--table-path")
    worker_parser.add_argument("--schema-path")
    worker_parser.add_argument("--pdf-dir")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "preflight":
            exit_code, payload = run_preflight(
                config_path=args.config_path,
                table_path=args.table_path,
                schema_path=args.schema_path,
                pdf_dir=args.pdf_dir,
            )
            _print_json(payload)
            return exit_code

        if args.command == "start":
            exit_code, payload = run_start(
                config_path=args.config_path,
                table_path=args.table_path,
                schema_path=args.schema_path,
                pdf_dir=args.pdf_dir,
                wait=bool(args.wait),
                poll_interval=float(args.poll_interval),
                timeout_seconds=args.timeout_seconds,
            )
            _print_json(payload)
            return exit_code

        if args.command == "status":
            exit_code, payload = run_status(run_id=args.run_id, output_dir=args.output_dir)
            _print_json(payload)
            return exit_code

        if args.command == "wait":
            exit_code, payload = run_wait(
                run_id=args.run_id,
                output_dir=args.output_dir,
                poll_interval=float(args.poll_interval),
                timeout_seconds=args.timeout_seconds,
            )
            _print_json(payload)
            return exit_code

        if args.command == "headless":
            exit_code, payload = run_headless(
                config_path=args.config_path,
                table_path=args.table_path,
                schema_path=args.schema_path,
                pdf_dir=args.pdf_dir,
                accept_all=bool(args.accept_all),
                export=bool(args.export),
                poll_interval=float(args.poll_interval),
                timeout_seconds=args.timeout_seconds,
            )
            _print_json(payload)
            return exit_code

        if args.command == "_run-worker":
            asyncio.run(
                _run_worker(
                    run_id=args.run_id,
                    config_path=args.config_path,
                    table_path=args.table_path,
                    schema_path=args.schema_path,
                    pdf_dir=args.pdf_dir,
                )
            )
            return 0

        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        _print_json(
            {
                "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
                "status": "error",
                "is_terminal": True,
                "error_message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
