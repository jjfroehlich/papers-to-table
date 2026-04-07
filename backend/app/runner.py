from __future__ import annotations

import asyncio
import json
import os
import pathlib
from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from .artifacts import (
    get_artifact_summary_path,
    hash_file,
    hash_json_data,
    get_config_snapshot_path,
    get_input_summary_path,
    get_provider_diagnostics_path,
    get_provider_model_management_path,
    get_provider_mode_path,
    get_provider_probe_path,
    get_provider_request_counts_path,
    get_provider_trace_path,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_stats_path,
    get_run_summary_path,
    init_run_bundle,
    write_json,
)
from .config import RunConfig, check_readiness, get_run_mode
from .extraction import (
    extract_cell,
    get_prompt_identity,
    load_proposals,
)
from .ids import generate_cell_id, generate_row_id, generate_run_id
from .ingest import (
    create_masked_working_dataframe,
    get_eligible_cells,
    load_schema,
    load_table,
    persist_masked_working_copy,
    persist_table_snapshot,
    validate_metadata_columns,
    validate_schema_columns,
)
from .lifecycle import apply_transition
from .matching import MatchResult, persist_match_artifacts, run_matching
from .parsing import parse_pdf
from .provider import ProviderError, _canonical_structured_output_reason, initialize_provider
from .retrieval import run_retrieval_for_cell
from .schemas import MatchOutcome, RunStatus, SupportLabel, WarningCategory
from .style_profiles import run_style_profiles_stage

_active_runs: dict[str, asyncio.Task] = {}
_active_runs_lock: asyncio.Lock | None = None


def _relative_run_path(run_dir: pathlib.Path, artifact_path: pathlib.Path) -> str:
    return str(artifact_path.resolve().relative_to(run_dir.resolve())).replace("\\", "/")


def _get_lock() -> asyncio.Lock:
    global _active_runs_lock
    if _active_runs_lock is None:
        _active_runs_lock = asyncio.Lock()
    return _active_runs_lock


def get_initial_run_data(
    run_id: str,
    config: RunConfig,
    config_path: Optional[str],
    resolved_inputs: Optional[dict[str, object]] = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    run_mode = get_run_mode(config)
    prompt_identity = get_prompt_identity(
        prompt_bundle_name=config.prompt.bundle,
        prompt_bundle_path=config.prompt.bundle_path,
    )
    return {
        "run_id": run_id,
        "status": RunStatus.created.value,
        "config_path": config_path,
        "table_path": config.table_path,
        "schema_path": config.schema_path,
        "pdf_dir": config.pdf_dir,
        "resolved_inputs": resolved_inputs or {
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
        },
        "output_dir": config.output_dir,
        "verify_mode": config.verify_mode,
        "eval_mode": config.eval_mode,
        "run_mode": run_mode,
        "provider_token": config.provider.token,
        "provider_locality": config.provider.locality,
        "provider_mode": "unknown",
        "provider_text_model_id": config.provider.text_model.model_id,
        "provider_text_working_context_budget": config.provider.text_model.working_context_budget,
        "provider_text_load_context_length": config.provider.text_model.required_load_context_length,
        "provider_vision_model_id": (
            config.provider.vision_model.model_id if config.provider.vision_model else None
        ),
        "provider_vision_load_context_length": (
            config.provider.vision_model.load_context_length if config.provider.vision_model else None
        ),
        "structured_output_mode": None,
        "structured_output_reason": None,
        "structured_output_fallback_used": False,
        "vision_structured_output_mode": None,
        "vision_structured_output_reason": None,
        "provider_readiness_reason": None,
        "provider_request_counts": {},
        "retrieval_mode": config.retrieval.mode,
        "prompt_bundle_name": config.prompt.bundle,
        "prompt_bundle_config_path": config.prompt.bundle_path,
        "prompt_version": prompt_identity["prompt_version"],
        "prompt_hash": prompt_identity["prompt_hash"],
        "prompt_bundle_id": prompt_identity["prompt_bundle_id"],
        "prompt_bundle_version": prompt_identity.get("prompt_bundle_version"),
        "prompt_bundle_path": prompt_identity["prompt_bundle_path"],
        "prompt_manifest_hash": prompt_identity["prompt_manifest_hash"],
        "prompt_bundle_hash": prompt_identity["prompt_bundle_hash"],
        "prompt_keys_used": prompt_identity.get("prompt_keys_used", []),
        "prompt_files": prompt_identity.get("prompt_files", {}),
        "config_hash": None,
        "config_snapshot_path": None,
        "run_stats_path": None,
        "provider_diagnostics_path": None,
        "provider_probe_path": None,
        "provider_model_management_path": None,
        "artifact_summary_path": None,
        "schema_hash": None,
        "schema_version": None,
        "parser_identity": config.parser.backend,
        "parser_version": None,
        "eval_artifacts": None,
        "provider_readiness_error": None,
        "started_at": None,
        "completed_at": None,
        "current_stage": None,
        "total_rows": 0,
        "eligible_cells": 0,
        "proposals_generated": 0,
        "proposals_reviewed": 0,
        "warnings": [],
        "error_message": None,
        "created_at": now,
    }


async def run_pipeline(
    run_id: str,
    config: RunConfig,
    config_path: Optional[str],
    output_dir: str,
    resolved_inputs: Optional[dict[str, object]] = None,
) -> None:
    """Main staged runner - runs as asyncio task."""
    prompt_identity = get_prompt_identity(
        prompt_bundle_name=config.prompt.bundle,
        prompt_bundle_path=config.prompt.bundle_path,
    )
    run_json_path = get_run_json_path(output_dir, run_id)
    run_stats_path = get_run_stats_path(output_dir, run_id)
    stats_started_at = datetime.now(timezone.utc).isoformat()
    run_started_perf = perf_counter()
    run_stats: dict[str, object] = {
        "run_id": run_id,
        "retrieval_mode": config.retrieval.mode,
        "provider_token": config.provider.token,
        "prompt_hash": prompt_identity["prompt_hash"],
        "prompt_bundle_id": prompt_identity["prompt_bundle_id"],
        "prompt_bundle_version": prompt_identity.get("prompt_bundle_version"),
        "prompt_bundle_path": prompt_identity["prompt_bundle_path"],
        "prompt_manifest_hash": prompt_identity["prompt_manifest_hash"],
        "prompt_bundle_hash": prompt_identity["prompt_bundle_hash"],
        "prompt_keys_used": prompt_identity.get("prompt_keys_used", []),
        "prompt_files": prompt_identity.get("prompt_files", {}),
        "per_run": {
            "started_at": stats_started_at,
            "completed_at": None,
            "run_total_ms": None,
            "stage_ms": {},
        },
        "per_pdf": {},
        "per_cell": [],
        "counters": {
            "provider_request_counts": {},
            "parse_errors": 0,
            "parse_warnings": 0,
            "matched_pdfs": 0,
            "eligible_cells": 0,
            "processed_cells": 0,
            "recall_rescue_cells": 0,
            "whole_document_cells": 0,
            "needs_more_evidence_cells": 0,
            "figure_review_cells": 0,
            "figure_review_triggered_cells": 0,
            "figure_review_hit_cells": 0,
            "figure_review_useful_cells": 0,
            "figure_review_rescue_cells": 0,
            "figure_review_hits_total": 0,
        },
        "recorded_at": stats_started_at,
    }
    stage_state = {"current": None, "started": None}

    def save_run(data: dict) -> None:
        write_json(run_json_path, data)

    def save_run_stats() -> None:
        run_stats["recorded_at"] = datetime.now(timezone.utc).isoformat()
        write_json(run_stats_path, run_stats)

    def _finalize_active_stage() -> None:
        current_stage = stage_state.get("current")
        started = stage_state.get("started")
        if current_stage is None or started is None:
            return
        stage_ms = (perf_counter() - started) * 1000.0
        run_stats["per_run"]["stage_ms"][current_stage] = round(
            run_stats["per_run"]["stage_ms"].get(current_stage, 0.0) + stage_ms,
            3,
        )
        stage_state["current"] = None
        stage_state["started"] = None

    def ensure_pdf_stats(pdf_id: str) -> dict:
        per_pdf = run_stats.setdefault("per_pdf", {})
        if pdf_id not in per_pdf:
            per_pdf[pdf_id] = {
                "parse_pdf_ms": 0.0,
                "retrieval_prep_ms": 0.0,
                "retrieval_query_ms": 0.0,
                "retrieval_calls": 0,
                "chunk_build_count": 0,
                "idf_build_count": 0,
                "chunk_count_total": 0,
                "chunk_count_by_type": {},
                "cells_processed": 0,
            }
        return per_pdf[pdf_id]

    def update_stage(data: dict, stage: str) -> dict:
        _finalize_active_stage()
        stage_state["current"] = stage
        stage_state["started"] = perf_counter()
        data = dict(data)
        data["current_stage"] = stage
        return data

    def fail_run(data: dict, error_message: str) -> dict:
        _finalize_active_stage()
        data = apply_transition(data, RunStatus.failed, error_message=error_message)
        data["current_stage"] = None
        return data

    def write_final_summaries(data: dict, proposals_generated: int = 0) -> None:
        _finalize_active_stage()
        if run_stats["per_run"].get("completed_at") is None:
            run_stats["per_run"]["completed_at"] = data.get("completed_at") or datetime.now(timezone.utc).isoformat()
        if run_stats["per_run"].get("run_total_ms") is None:
            run_stats["per_run"]["run_total_ms"] = round((perf_counter() - run_started_perf) * 1000.0, 3)
        save_run_stats()
        write_json(get_run_summary_path(output_dir, run_id), data)
        write_json(
            get_reviewer_summary_path(output_dir, run_id),
            {
                "run_id": run_id,
                "verify_mode": bool(data.get("verify_mode", False)),
                "eval_mode": bool(data.get("eval_mode", False)),
                "run_mode": data.get("run_mode", "normal"),
                "provider_token": data.get("provider_token"),
                "provider_locality": data.get("provider_locality"),
                "provider_mode": data.get("provider_mode"),
                "provider_text_model_id": data.get("provider_text_model_id"),
                "provider_text_working_context_budget": data.get("provider_text_working_context_budget"),
                "provider_text_load_context_length": data.get("provider_text_load_context_length"),
                "provider_vision_model_id": data.get("provider_vision_model_id"),
                "provider_vision_load_context_length": data.get("provider_vision_load_context_length"),
                "structured_output_mode": data.get("structured_output_mode"),
                "structured_output_reason": data.get("structured_output_reason"),
                "structured_output_fallback_used": bool(
                    data.get("structured_output_fallback_used", False)
                ),
                "vision_structured_output_mode": data.get("vision_structured_output_mode"),
                "vision_structured_output_reason": data.get("vision_structured_output_reason"),
                "provider_readiness_error": data.get("provider_readiness_error"),
                "provider_readiness_reason": data.get("provider_readiness_reason"),
                "provider_model_management_path": data.get("provider_model_management_path"),
                "retrieval_mode": data.get("retrieval_mode"),
                "prompt_version": data.get("prompt_version"),
                "prompt_hash": data.get("prompt_hash"),
                "prompt_bundle_id": data.get("prompt_bundle_id"),
                "prompt_bundle_version": data.get("prompt_bundle_version"),
                "prompt_bundle_path": data.get("prompt_bundle_path"),
                "prompt_manifest_hash": data.get("prompt_manifest_hash"),
                "prompt_bundle_hash": data.get("prompt_bundle_hash"),
                "prompt_keys_used": data.get("prompt_keys_used", []),
                "prompt_files": data.get("prompt_files"),
                "config_hash": data.get("config_hash"),
                "config_snapshot_path": data.get("config_snapshot_path"),
                "run_stats_path": data.get("run_stats_path"),
                "schema_hash": data.get("schema_hash"),
                "schema_version": data.get("schema_version"),
                "parser_identity": data.get("parser_identity"),
                "parser_version": data.get("parser_version"),
                "eval_artifacts": data.get("eval_artifacts"),
                "total_proposals": proposals_generated,
                "reviewed": 0,
                "accepted": 0,
                "accepted_with_edit": 0,
                "confirmed_no_data": 0,
                "rejected": 0,
                "pending": proposals_generated,
                "actionable_total_proposals": proposals_generated,
                "actionable_reviewed": 0,
                "actionable_pending": proposals_generated,
                "diagnostic_only_total_proposals": 0,
                "explicitly_accepted": 0,
                "explicitly_rejected": 0,
                "confirmed_absent": 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        data = persist_artifact_summary(data, run_dir)
        save_run(data)
        write_json(get_run_summary_path(output_dir, run_id), data)

    def _count_artifact_files(path: pathlib.Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for item in path.rglob("*") if item.is_file())

    def _proposal_metadata_coverage(proposals: list) -> dict:
        total = len(proposals)
        return {
            "total_proposals": total,
            "prompt_hash_present": sum(bool(p.prompt_hash) for p in proposals),
            "config_snapshot_path_present": sum(bool(p.config_snapshot_path) for p in proposals),
            "schema_hash_present": sum(bool(p.schema_hash) for p in proposals),
            "parser_identity_present": sum(bool(p.parser_identity) for p in proposals),
            "provider_diagnostics_present": sum(bool(p.provider_diagnostics) for p in proposals),
            "retrieval_diagnostics_present": sum(bool(p.retrieval_diagnostics) for p in proposals),
            "figure_review_diagnostics_present": sum(bool(p.figure_review_diagnostics) for p in proposals),
            "gold_table_snapshot_path_present": sum(bool(p.gold_table_snapshot_path) for p in proposals),
            "masked_working_table_path_present": sum(bool(p.masked_working_table_path) for p in proposals),
        }

    def persist_artifact_summary(data: dict, run_dir: pathlib.Path) -> dict:
        proposals = load_proposals(run_dir)
        artifact_path = get_artifact_summary_path(output_dir, run_id)
        proposal_coverage = _proposal_metadata_coverage(proposals)
        eval_expected = bool(data.get("eval_mode", False))
        user_facing_files = {
            "config_snapshot": "config.snapshot.json",
            "input_summary": "inputs/input_summary.json",
            "provider_mode": "summaries/provider_mode.json",
            "match_summary": "matching/match_summary.json",
            "proposals_jsonl": "proposals/proposals.jsonl",
            "proposal_index": "proposals/proposal_index.json",
            "run_summary": "summaries/run_summary.json",
            "reviewer_summary": "summaries/reviewer_summary.json",
            "artifact_summary": "summaries/artifact_summary.json",
        }
        diagnostics_files = {
            "run_stats": "diagnostics/run_stats.json",
            "provider_request_counts": "diagnostics/provider_request_counts.json",
            "provider_diagnostics": "diagnostics/provider_diagnostics.json",
            "provider_probe": "diagnostics/provider_probe.json",
            "provider_model_management": "diagnostics/provider_model_management.json",
            "provider_trace": "diagnostics/provider_trace.jsonl",
        }
        files = {}
        missing_expected: list[str] = []
        for label, relative_path in {**user_facing_files, **diagnostics_files}.items():
            target = run_dir / relative_path
            present = target.exists()
            files[label] = {"path": relative_path, "present": present}
            if label not in {"proposals_jsonl", "proposal_index", "match_summary", "provider_trace"} and not present:
                missing_expected.append(relative_path)

        gold_path = run_dir / "inputs" / f"gold_table{pathlib.Path(config.table_path).suffix}"
        masked_path = run_dir / "inputs" / f"masked_working_table{pathlib.Path(config.table_path).suffix}"
        eval_parity = {
            "expected": eval_expected,
            "eval_artifacts_present": bool(data.get("eval_artifacts")),
            "gold_table_snapshot_present": gold_path.exists(),
            "masked_working_table_present": masked_path.exists(),
            "proposal_gold_metadata_complete": None if not proposals else proposal_coverage["gold_table_snapshot_path_present"] == len(proposals),
            "proposal_masked_metadata_complete": None if not proposals else proposal_coverage["masked_working_table_path_present"] == len(proposals),
        }
        if eval_expected and not eval_parity["gold_table_snapshot_present"]:
            missing_expected.append(str(gold_path.relative_to(run_dir)).replace("\\", "/"))
        if eval_expected and not eval_parity["masked_working_table_present"]:
            missing_expected.append(str(masked_path.relative_to(run_dir)).replace("\\", "/"))

        summary = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
            "sections": {
                "user_facing": sorted(user_facing_files.values()),
                "diagnostics": sorted(diagnostics_files.values()),
            },
            "directories": {
                "parsed": {"path": "parsed", "file_count": _count_artifact_files(run_dir / "parsed")},
                "retrieval": {"path": "retrieval", "file_count": _count_artifact_files(run_dir / "retrieval")},
                "proposals": {"path": "proposals", "file_count": _count_artifact_files(run_dir / "proposals")},
                "evidence": {"path": "evidence", "file_count": _count_artifact_files(run_dir / "evidence")},
                "review": {"path": "review", "file_count": _count_artifact_files(run_dir / "review")},
                "diagnostics": {"path": "diagnostics", "file_count": _count_artifact_files(run_dir / "diagnostics")},
                "exports": {"path": "exports", "file_count": _count_artifact_files(run_dir / "exports")},
            },
            "proposal_metadata_coverage": proposal_coverage,
            "eval_artifact_parity": eval_parity,
            "missing_expected_artifacts": sorted(set(missing_expected)),
        }
        write_json(artifact_path, summary)
        data = dict(data)
        data["artifact_summary_path"] = _relative_run_path(run_dir, artifact_path)
        return data

    def sync_provider_artifacts(
        data: dict,
        provider_obj: object,
        run_dir: pathlib.Path,
        provider_error_details: Optional[dict[str, object]] = None,
    ) -> dict:
        """Persist provider request counters and diagnostics into run artifacts and run.json."""
        data = dict(data)
        counts: dict[str, int] = {}
        if provider_obj is not None:
            get_counts = getattr(provider_obj, "get_request_counts", None)
            if callable(get_counts):
                try:
                    counts = get_counts() or {}
                except Exception:
                    counts = {}
        try:
            data["provider_request_counts"] = counts
            run_stats["counters"]["provider_request_counts"] = counts
            counts_path = get_provider_request_counts_path(output_dir, run_id)
            write_json(
                counts_path,
                {
                    "run_id": run_id,
                    "provider_token": config.provider.token,
                    "counts": counts,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass

        diagnostics = {
            "run_id": run_id,
            "provider_token": config.provider.token,
            "provider_mode": data.get("provider_mode"),
            "structured_output_mode": data.get("structured_output_mode"),
            "structured_output_reason": data.get("structured_output_reason"),
            "provider_readiness_reason": data.get("provider_readiness_reason"),
            "provider_readiness_error": data.get("provider_readiness_error"),
            "attempt_count": 0,
            "total_duration_ms": 0.0,
            "by_outcome": {},
            "by_request_kind": {},
            "last_error": None,
            "attempts": [],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if provider_obj is not None:
            get_diagnostics = getattr(provider_obj, "get_diagnostics", None)
            if callable(get_diagnostics):
                try:
                    diagnostics.update(get_diagnostics() or {})
                except Exception:
                    pass
        provider_diag_path = get_provider_diagnostics_path(output_dir, run_id)
        write_json(provider_diag_path, diagnostics)
        data["provider_diagnostics_path"] = _relative_run_path(run_dir, provider_diag_path)

        probe_report = {
            "provider": config.provider.token,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if provider_obj is not None:
            get_probe_report = getattr(provider_obj, "get_probe_report", None)
            if callable(get_probe_report):
                try:
                    probe_report.update(get_probe_report() or {})
                except Exception:
                    pass
        provider_probe_path = get_provider_probe_path(output_dir, run_id)
        write_json(provider_probe_path, probe_report)
        data["provider_probe_path"] = _relative_run_path(run_dir, provider_probe_path)

        model_management_report = {
            "provider": config.provider.token,
            "base_url": config.provider.base_url,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "text_model": None,
            "vision_model": None,
        }
        if provider_error_details and isinstance(provider_error_details.get("model_management"), dict):
            model_management_report.update(provider_error_details["model_management"])
        elif provider_obj is not None:
            get_model_management_report = getattr(provider_obj, "get_model_management_report", None)
            if callable(get_model_management_report):
                try:
                    model_management_report.update(get_model_management_report() or {})
                except Exception:
                    pass
        provider_model_management_path = get_provider_model_management_path(output_dir, run_id)
        write_json(provider_model_management_path, model_management_report)
        data["provider_model_management_path"] = _relative_run_path(
            run_dir,
            provider_model_management_path,
        )

        trace_records: list[dict] = []
        if provider_obj is not None:
            get_trace_records = getattr(provider_obj, "get_trace_records", None)
            if callable(get_trace_records):
                try:
                    trace_records = get_trace_records() or []
                except Exception:
                    trace_records = []
        trace_path = get_provider_trace_path(output_dir, run_id)
        if trace_records:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with open(trace_path, "w", encoding="utf-8") as handle:
                for record in trace_records:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return data

    run_data = get_initial_run_data(run_id, config, config_path, resolved_inputs=resolved_inputs)
    init_run_bundle(output_dir, run_id)
    save_run(run_data)

    try:
        from .schemas import WarningCategory as WC

        # Stage: validating
        run_data = apply_transition(run_data, RunStatus.validating)
        run_data = update_stage(run_data, "validating")
        save_run(run_data)

        run_dir = get_run_dir(output_dir, run_id)
        config_snap_path = get_config_snapshot_path(output_dir, run_id)
        config_snapshot = config.model_dump()
        write_json(config_snap_path, config_snapshot)
        run_data["config_hash"] = hash_json_data(config_snapshot)
        run_data["config_snapshot_path"] = _relative_run_path(run_dir, config_snap_path)
        run_data["run_stats_path"] = _relative_run_path(run_dir, run_stats_path)
        save_run(run_data)
        save_run_stats()

        input_summary_path = get_input_summary_path(output_dir, run_id)
        now = datetime.now(timezone.utc).isoformat()
        early_input_summary = {
            "run_id": run_id,
            "table_path": config.table_path,
            "schema_path": config.schema_path,
            "pdf_dir": config.pdf_dir,
            "resolved_inputs": run_data.get("resolved_inputs"),
            "output_dir": output_dir,
            "verify_mode": config.verify_mode,
            "eval_mode": config.eval_mode,
            "run_mode": run_data["run_mode"],
            "retrieval_mode": run_data["retrieval_mode"],
            "prompt_version": run_data["prompt_version"],
            "prompt_hash": run_data["prompt_hash"],
            "prompt_bundle_id": run_data.get("prompt_bundle_id"),
            "prompt_bundle_version": run_data.get("prompt_bundle_version"),
            "prompt_bundle_path": run_data.get("prompt_bundle_path"),
            "prompt_manifest_hash": run_data.get("prompt_manifest_hash"),
            "prompt_bundle_hash": run_data.get("prompt_bundle_hash"),
            "prompt_keys_used": run_data.get("prompt_keys_used", []),
            "prompt_files": run_data.get("prompt_files", {}),
            "config_hash": run_data["config_hash"],
            "config_snapshot_path": run_data["config_snapshot_path"],
            "run_stats_path": run_data.get("run_stats_path"),
            "schema_hash": None,
            "schema_version": None,
            "parser_identity": config.parser.backend,
            "parser_version": None,
            "eval_artifacts": None,
            "table_rows": None,
            "schema_columns": None,
            "pdf_count": None,
            "recorded_at": now,
        }
        write_json(input_summary_path, early_input_summary)

        text_model_id = config.provider.text_model.model_id
        vision_model_id = (
            config.provider.vision_model.model_id
            if config.provider.vision_model
            else None
        )

        readiness = await check_readiness(config)
        if not readiness.ok:
            if readiness.provider_mode:
                run_data["provider_mode"] = readiness.provider_mode
            if readiness.provider_readiness_error:
                run_data["provider_readiness_error"] = readiness.provider_readiness_error
            if readiness.provider_readiness_reason:
                run_data["provider_readiness_reason"] = readiness.provider_readiness_reason
            if readiness.structured_output_mode is not None:
                run_data["structured_output_mode"] = readiness.structured_output_mode
                run_data["structured_output_fallback_used"] = bool(
                    readiness.structured_output_fallback_used
                )
                write_json(
                    get_provider_mode_path(output_dir, run_id),
                    {
                        "token": config.provider.token,
                        "locality": config.provider.locality,
                        "mode": readiness.provider_mode or "unknown",
                        "text_model_id": text_model_id,
                        "vision_model_id": vision_model_id,
                        "structured_output_mode": readiness.structured_output_mode,
                        "structured_output_reason": None,
                        "structured_output_fallback_used": bool(readiness.structured_output_fallback_used),
                        "vision_structured_output_mode": None,
                        "vision_structured_output_reason": None,
                        "readiness_reason": readiness.provider_readiness_reason,
                        "readiness_error": readiness.provider_readiness_error,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            run_data = sync_provider_artifacts(run_data, None, run_dir)
            run_data = fail_run(run_data, "; ".join(readiness.errors))
            save_run(run_data)
            write_final_summaries(run_data)
            return

        # Stage: load_inputs
        run_data = apply_transition(run_data, RunStatus.running)
        run_data = update_stage(run_data, "load_inputs")
        save_run(run_data)

        df = load_table(config.table_path)

        meta_errors = validate_metadata_columns(df)
        if meta_errors:
            run_data = fail_run(run_data, "; ".join(meta_errors))
            save_run(run_data)
            write_final_summaries(run_data)
            return

        schema = load_schema(config.schema_path, config.table_path)
        schema_errors = validate_schema_columns(schema)
        if schema_errors:
            run_data = fail_run(run_data, "; ".join(schema_errors))
            save_run(run_data)
            write_final_summaries(run_data)
            return

        schema_hash = hash_json_data(schema)
        run_data["schema_hash"] = schema_hash
        early_input_summary["schema_hash"] = schema_hash
        input_summary_base = {
            **early_input_summary,
            "schema_hash": schema_hash,
        }

        eligible = get_eligible_cells(
            df,
            schema,
            verify_mode=config.verify_mode,
            eval_mode=config.eval_mode,
        )
        extraction_df = df
        style_profile_df = df

        if config.eval_mode:
            gold_snapshot_path = run_dir / "inputs" / f"gold_table{pathlib.Path(config.table_path).suffix}"
            masked_path = run_dir / "inputs" / f"masked_working_table{pathlib.Path(config.table_path).suffix}"
            persist_table_snapshot(config.table_path, str(gold_snapshot_path))
            masked_df, masking_summary = create_masked_working_dataframe(df, schema)
            persist_masked_working_copy(config.table_path, str(masked_path), schema, masked_df)
            extraction_df = masked_df
            style_profile_df = masked_df
            run_data["eval_artifacts"] = {
                "gold_table": {
                    "source_reference": config.table_path,
                    "content_hash": hash_file(config.table_path),
                    "snapshot_path": _relative_run_path(run_dir, gold_snapshot_path),
                },
                "masked_working_table": {
                    "path": _relative_run_path(run_dir, masked_path),
                    "content_hash": hash_file(masked_path),
                },
                **masking_summary,
            }
            input_summary_base["eval_artifacts"] = run_data["eval_artifacts"]
        else:
            input_summary_base["eval_artifacts"] = None

        pdf_files = [f for f in os.listdir(config.pdf_dir) if f.lower().endswith(".pdf")]

        input_summary = {
            **input_summary_base,
            "table_rows": len(df),
            "schema_columns": len(schema),
            "pdf_count": len(pdf_files),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(input_summary_path, input_summary)

        run_data["total_rows"] = len(df)
        run_data["eligible_cells"] = len(eligible)
        run_stats["counters"]["eligible_cells"] = len(eligible)
        save_run(run_data)

        # Stage: initialize provider (T050, T052a)
        run_data = update_stage(run_data, "provider_init")
        save_run(run_data)

        provider = None
        provider_mode = None
        provider_init_error: Optional[str] = None
        provider_init_details: Optional[dict[str, object]] = None

        try:
            provider, provider_mode = await initialize_provider(
                config.provider,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                diagnostics_config=config.diagnostics,
            )
        except ProviderError as e:
            provider_init_error = str(e)
            provider_init_reason = getattr(e, "reason", None) or "provider_unreachable"
            provider_init_details = getattr(e, "details", None)

            warning_category = {
                "provider_unreachable": WC.provider_unreachable.value,
                "model_unavailable": WC.model_unavailable.value,
                "model_load_failed": WC.model_unavailable.value,
                "no_compatible_structured_mode": WC.structured_mode_capability_mismatch.value,
                "structured_backend_incompatible": WC.structured_mode_capability_mismatch.value,
            }.get(provider_init_reason, WC.provider_unreachable.value)

            warning_prefix = {
                "provider_unreachable": "Provider unreachable",
                "model_unavailable": "Model unavailable",
                "model_load_failed": "Model load failed",
                "no_compatible_structured_mode": "No compatible structured-output mode",
                "structured_backend_incompatible": "Structured-output backend incompatibility",
            }.get(provider_init_reason, "Provider unavailable")

            run_data["provider_mode"] = "unavailable"
            run_data["provider_readiness_error"] = provider_init_error
            run_data["provider_readiness_reason"] = provider_init_reason
            run_data["structured_output_mode"] = "none"
            run_data["structured_output_reason"] = None
            run_data["structured_output_fallback_used"] = False
            run_data["vision_structured_output_mode"] = None
            run_data["vision_structured_output_reason"] = None
            write_json(
                get_provider_mode_path(output_dir, run_id),
                {
                    "token": config.provider.token,
                    "locality": config.provider.locality,
                    "mode": "unavailable",
                    "text_model_id": text_model_id,
                    "vision_model_id": vision_model_id,
                    "structured_output_mode": "none",
                    "structured_output_reason": None,
                    "structured_output_fallback_used": False,
                    "vision_structured_output_mode": None,
                    "vision_structured_output_reason": None,
                        "model_management": (
                            provider_init_details.get("model_management")
                            if isinstance(provider_init_details, dict)
                            else None
                        ),
                    "readiness_reason": provider_init_reason,
                    "readiness_error": provider_init_error,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            run_data.setdefault("warnings", []).append({
                "category": warning_category,
                "message": f"{warning_prefix}: {provider_init_error}",
                "context": {
                    "provider": config.provider.token,
                    "readiness_reason": provider_init_reason,
                },
            })
            save_run(run_data)

        if provider is None:
            run_data = sync_provider_artifacts(
                run_data,
                None,
                run_dir,
                provider_error_details=provider_init_details,
            )
            run_data = fail_run(
                run_data,
                provider_init_error or "Provider unavailable during initialization",
            )
            save_run(run_data)
            write_final_summaries(run_data)
            return

        # Persist provider mode in run artifacts (T052a)
        if provider_mode:
            run_data["provider_mode"] = provider_mode.mode
            run_data["provider_locality"] = provider_mode.locality
            run_data["provider_readiness_error"] = provider_mode.readiness_error
            run_data["provider_readiness_reason"] = provider_mode.readiness_reason
            run_data["structured_output_mode"] = provider_mode.structured_output_mode
            run_data["structured_output_reason"] = provider_mode.structured_output_reason
            run_data["structured_output_fallback_used"] = provider_mode.structured_output_fallback_used
            run_data["vision_structured_output_mode"] = provider_mode.vision_structured_output_mode
            run_data["vision_structured_output_reason"] = provider_mode.vision_structured_output_reason
            write_json(get_provider_mode_path(output_dir, run_id), provider_mode.model_dump())
            caps = provider_mode.capabilities
            if caps and getattr(caps, "structured_output_mode", None) == "json_object":
                run_data.setdefault("warnings", []).append({
                    "category": WC.provider_degraded.value,
                    "message": (
                        "Provider is running in degraded structured-output mode (json_object fallback); "
                        + (
                            "LM Studio rejected structured-output grammar/regex constraints for this request shape."
                            if getattr(caps, "structured_output_reason", None) == "structured_backend_incompatible"
                            else "json_schema is unavailable for this model/runtime combination."
                        )
                    ),
                    "context": {
                        "provider": config.provider.token,
                        "structured_output_mode": "json_object",
                        "structured_output_reason": getattr(caps, "structured_output_reason", None),
                        "structured_output_error": getattr(caps, "structured_output_error", None),
                    },
                })
            elif caps and getattr(caps, "structured_output_mode", None) == "none":
                run_data.setdefault("warnings", []).append({
                    "category": WC.provider_degraded.value,
                    "message": (
                        "Provider is running in degraded prompt-only JSON mode; "
                        + (
                            "LM Studio rejected structured-output grammar/regex constraints for this request shape."
                            if getattr(caps, "structured_output_reason", None) == "structured_backend_incompatible"
                            else "json_schema/json_object are unavailable for this model/runtime combination."
                        )
                    ),
                    "context": {
                        "provider": config.provider.token,
                        "structured_output_mode": "none",
                        "structured_output_reason": getattr(caps, "structured_output_reason", None),
                        "structured_output_error": getattr(caps, "structured_output_error", None),
                    },
                })
            if (
                caps
                and config.figure_review.enabled
                and config.figure_review.skip_when_prompt_only_degraded
                and getattr(caps, "vision_structured_output_mode", None) == "none"
            ):
                run_data.setdefault("warnings", []).append({
                    "category": WC.provider_degraded.value,
                    "message": (
                        "Figure review will be suppressed for this run because the configured vision path only supports "
                        "prompt-only JSON mode."
                    ),
                    "context": {
                        "provider": config.provider.token,
                        "vision_structured_output_mode": "none",
                        "vision_structured_output_reason": getattr(caps, "vision_structured_output_reason", None),
                        "vision_structured_output_error": getattr(caps, "vision_structured_output_error", None),
                    },
                })
            run_data = sync_provider_artifacts(run_data, provider, run_dir)
            save_run(run_data)

        # Stage: parse
        run_data = update_stage(run_data, "parse")
        save_run(run_data)

        parsed_docs: list[dict] = []
        parse_errors: list[str] = []
        parse_warning_messages: set[tuple[str, str]] = set()

        for pdf_file in pdf_files:
            pdf_path = os.path.join(config.pdf_dir, pdf_file)
            pdf_id = pathlib.Path(pdf_file).stem
            pdf_stats = ensure_pdf_stats(pdf_id)
            await asyncio.sleep(0)  # yield to event loop between PDFs
            try:
                parse_started = perf_counter()
                doc, diagnostics, _page_paths = parse_pdf(
                    pdf_path=pdf_path,
                    pdf_id=pdf_id,
                    configured_parser=config.parser.backend,
                    allow_basic_fallback=config.parser.allow_basic_fallback,
                    ocr_enabled=config.parser.ocr_enabled,
                    ocr_language=config.parser.ocr_language,
                    run_dir=run_dir,
                    generate_pages=True,
                )
                pdf_stats["parse_pdf_ms"] = round((perf_counter() - parse_started) * 1000.0, 3)
                parsed_docs.append(doc.model_dump())

                if diagnostics.fallback_used:
                    key = (pdf_id, "fallback")
                    if key not in parse_warning_messages:
                        run_stats["counters"]["parse_warnings"] += 1
                        run_data.setdefault("warnings", []).append({
                            "category": WC.partial_extraction.value,
                            "message": (
                                f"Parser fallback used for {pdf_id}: "
                                f"{diagnostics.actual_parser_used} replaced {diagnostics.configured_parser}."
                            ),
                            "context": {
                                "pdf_id": pdf_id,
                                "configured_parser": diagnostics.configured_parser,
                                "actual_parser_used": diagnostics.actual_parser_used,
                            },
                        })
                        parse_warning_messages.add(key)

                if diagnostics.ocr_used:
                    key = (pdf_id, "ocr")
                    if key not in parse_warning_messages:
                        run_stats["counters"]["parse_warnings"] += 1
                        run_data.setdefault("warnings", []).append({
                            "category": WC.partial_extraction.value,
                            "message": f"OCR fallback used for {pdf_id}.",
                            "context": {
                                "pdf_id": pdf_id,
                                "ocr_reason": diagnostics.ocr_reason,
                            },
                        })
                        parse_warning_messages.add(key)

                for warning in diagnostics.parse_warnings:
                    key = (pdf_id, warning)
                    if key in parse_warning_messages:
                        continue
                    run_stats["counters"]["parse_warnings"] += 1
                    run_data.setdefault("warnings", []).append({
                        "category": WC.partial_extraction.value,
                        "message": f"{pdf_id}: {warning}",
                        "context": {"pdf_id": pdf_id},
                    })
                    parse_warning_messages.add(key)

                for gap in diagnostics.major_extraction_gaps:
                    key = (pdf_id, gap)
                    if key in parse_warning_messages:
                        continue
                    run_stats["counters"]["parse_warnings"] += 1
                    run_data.setdefault("warnings", []).append({
                        "category": WC.partial_extraction.value,
                        "message": f"{pdf_id}: {gap}",
                        "context": {"pdf_id": pdf_id},
                    })
                    parse_warning_messages.add(key)
            except Exception as e:
                run_stats["counters"]["parse_errors"] += 1
                parse_errors.append(f"{pdf_file}: {e}")

        if parse_errors:
            for err in parse_errors:
                run_data.setdefault("warnings", []).append({
                    "category": WarningCategory.partial_extraction.value,
                    "message": f"Parse error: {err}",
                    "context": None,
                })
            save_run(run_data)

        # Stage: match
        run_data = update_stage(run_data, "match")
        save_run(run_data)

        match_results = run_matching(
            pdf_docs=parsed_docs,
            df=df,
            ambiguity_threshold=config.matching.ambiguity_threshold,
        )
        persist_match_artifacts(run_dir, run_id, match_results)

        for mr in match_results:
            if mr.outcome == MatchOutcome.unmatched:
                run_data.setdefault("warnings", []).append({
                    "category": WC.unmatched_pdf.value,
                    "message": f"PDF not matched to any table row: {mr.pdf_id}",
                    "context": {"pdf_id": mr.pdf_id},
                })
            elif mr.outcome == MatchOutcome.ambiguous:
                run_data.setdefault("warnings", []).append({
                    "category": WC.ambiguous_match.value,
                    "message": f"PDF match ambiguous: {mr.pdf_id}",
                    "context": {"pdf_id": mr.pdf_id},
                })
            elif mr.outcome == MatchOutcome.duplicate_row_conflict:
                run_data.setdefault("warnings", []).append({
                    "category": WC.duplicate_row_conflict.value,
                    "message": f"Duplicate row conflict: {mr.pdf_id}",
                    "context": {
                        "pdf_id": mr.pdf_id,
                        "row_index": mr.matched_row_index,
                        "conflict_pdf_ids": mr.conflict_pdf_ids,
                    },
                })
            elif mr.outcome == MatchOutcome.matched:
                run_stats["counters"]["matched_pdfs"] += 1
        save_run(run_data)

        # Stage: style profiles (T041-T044)
        run_data = update_stage(run_data, "style_profiles")
        save_run(run_data)

        # Pass provider for LLM-assisted profiling when available
        style_profiles = await run_style_profiles_stage(
            run_dir=run_dir,
            df=style_profile_df,
            schema=schema,
            provider=provider,  # None → heuristic fallback
            model_id=text_model_id if provider is not None else None,
            prompt_bundle_name=config.prompt.bundle,
            prompt_bundle_path=run_data.get("prompt_bundle_path") or config.prompt.bundle_path,
        )

        # Stage: extraction (T057)
        run_data = update_stage(run_data, "extraction")
        save_run(run_data)

        # Build a lookup: matched_row_index → match_result
        matched: dict[int, MatchResult] = {}
        for mr in match_results:
            if mr.outcome == MatchOutcome.matched and mr.matched_row_index is not None:
                matched[mr.matched_row_index] = mr

        proposals_generated = 0

        # Build doc dict lookup: pdf_id → parsed_doc dict
        doc_by_pdf_id: dict[str, dict] = {}
        for doc in parsed_docs:
            doc_by_pdf_id[doc["pdf_id"]] = doc

        # Build column description lookup
        schema_by_column = {c["column_name"]: c for c in schema}
        missing_doc_warnings: set[str] = set()

        # Process eligible cells only for rows with a usable PDF match.
        for cell in eligible:
            row_idx = cell.get("row_index", 0)
            col_name = cell["column_name"]
            col_def = schema_by_column.get(col_name, {})
            col_desc = col_def.get("description", "")

            match_result = matched.get(row_idx)
            if not match_result or match_result.blocked:
                continue

            pdf_id = match_result.pdf_id
            doc_dict = doc_by_pdf_id.get(pdf_id)
            if doc_dict is None:
                if pdf_id not in missing_doc_warnings:
                    run_data.setdefault("warnings", []).append({
                        "category": WC.partial_extraction.value,
                        "message": f"Parsed document not found for matched PDF: {pdf_id}",
                        "context": {"pdf_id": pdf_id},
                    })
                    missing_doc_warnings.add(pdf_id)
                    save_run(run_data)
                continue

            if row_idx >= len(extraction_df):
                run_data.setdefault("warnings", []).append({
                    "category": WC.partial_extraction.value,
                    "message": (
                        f"Eligible cell row index {row_idx} is outside the staged extraction table."
                    ),
                    "context": {"row_index": row_idx, "column_name": col_name},
                })
                save_run(run_data)
                continue

            row_dict = extraction_df.iloc[row_idx].to_dict()
            row_id = generate_row_id(row_idx, str(row_dict.get("Title", "")))
            cell_id = generate_cell_id(row_id, col_name)
            existing_value = cell.get("current_value")
            artifact_context = {
                "run_mode": run_data["run_mode"],
                "retrieval_mode": run_data["retrieval_mode"],
                "prompt_bundle_name": config.prompt.bundle,
                "prompt_bundle_path": run_data.get("prompt_bundle_path") or config.prompt.bundle_path,
                "prompt_version": run_data["prompt_version"],
                "prompt_hash": run_data["prompt_hash"],
                "schema_hash": run_data["schema_hash"],
                "schema_version": run_data.get("schema_version"),
                "config_hash": run_data["config_hash"],
                "config_snapshot_path": run_data["config_snapshot_path"],
                "parser_identity": doc_dict.get("parser_used") or run_data.get("parser_identity"),
                "parser_version": None,
                "gold_table_source_reference": (
                    run_data.get("eval_artifacts", {})
                    .get("gold_table", {})
                    .get("source_reference")
                    if run_data.get("eval_artifacts")
                    else None
                ),
                "gold_table_hash": (
                    run_data.get("eval_artifacts", {})
                    .get("gold_table", {})
                    .get("content_hash")
                    if run_data.get("eval_artifacts")
                    else None
                ),
                "gold_table_snapshot_path": (
                    run_data.get("eval_artifacts", {})
                    .get("gold_table", {})
                    .get("snapshot_path")
                    if run_data.get("eval_artifacts")
                    else None
                ),
                "masked_working_table_path": (
                    run_data.get("eval_artifacts", {})
                    .get("masked_working_table", {})
                    .get("path")
                    if run_data.get("eval_artifacts")
                    else None
                ),
                "masked_working_table_hash": (
                    run_data.get("eval_artifacts", {})
                    .get("masked_working_table", {})
                    .get("content_hash")
                    if run_data.get("eval_artifacts")
                    else None
                ),
            }

            retrieval = run_retrieval_for_cell(
                run_id=run_id,
                pdf_id=pdf_id,
                column_name=col_name,
                column_description=col_desc,
                doc_dict=doc_dict,
                run_dir=run_dir,
                top_k=config.retrieval.top_k,
                retrieval_mode=config.retrieval.mode,
            )

            retrieval_stats = {}
            pdf_stats = ensure_pdf_stats(pdf_id)
            retrieval_mode = config.retrieval.mode
            retrieval_request_mode = "baseline"
            retrieval_policy: dict[str, object] = {}
            if retrieval is not None:
                retrieval_mode = getattr(retrieval, "mode", retrieval_mode)
                retrieval_request_mode = getattr(retrieval, "request_mode", retrieval_request_mode)
                retrieval_policy = dict(getattr(retrieval, "policy", {}) or {})
                retrieval_stats = getattr(retrieval, "stats", {}) if isinstance(getattr(retrieval, "stats", {}), dict) else {}
                pdf_stats["retrieval_calls"] += 1
                pdf_stats["retrieval_prep_ms"] = round(
                    pdf_stats["retrieval_prep_ms"]
                    + float(retrieval_stats.get("chunk_build_ms", 0.0) or 0.0)
                    + float(retrieval_stats.get("idf_build_ms", 0.0) or 0.0),
                    3,
                )
                pdf_stats["retrieval_query_ms"] = round(
                    pdf_stats["retrieval_query_ms"] + float(retrieval_stats.get("total_ms", 0.0) or 0.0),
                    3,
                )
                pdf_stats["chunk_build_count"] += int(retrieval_stats.get("chunk_build_count", 0) or 0)
                pdf_stats["idf_build_count"] += int(retrieval_stats.get("idf_build_count", 0) or 0)
                if not pdf_stats.get("chunk_count_total"):
                    pdf_stats["chunk_count_total"] = int(retrieval_stats.get("chunk_count_total", 0) or 0)
                    pdf_stats["chunk_count_by_type"] = dict(retrieval_stats.get("chunk_count_by_type", {}) or {})

            style_profile = style_profiles.get(col_name)
            cell_stats: dict[str, object] = {
                "cell_id": cell_id,
                "pdf_id": pdf_id,
                "row_index": row_idx,
                "column_name": col_name,
                "retrieval_mode": retrieval_mode,
                "retrieval_request_mode": retrieval_request_mode,
                "retrieval_policy": retrieval_policy,
                "retrieval_query_ms": float(retrieval_stats.get("total_ms", 0.0) or 0.0),
                "retrieval_prep_ms": round(
                    float(retrieval_stats.get("chunk_build_ms", 0.0) or 0.0)
                    + float(retrieval_stats.get("idf_build_ms", 0.0) or 0.0),
                    3,
                ),
                "chunk_count_total": int(retrieval_stats.get("chunk_count_total", 0) or 0),
                "chunk_count_by_type": dict(retrieval_stats.get("chunk_count_by_type", {}) or {}),
            }

            await asyncio.sleep(0)  # yield between cells

            proposal = await extract_cell(
                run_id=run_id,
                pdf_id=pdf_id,
                row_id=row_id,
                cell_id=cell_id,
                column_name=col_name,
                column_description=col_desc,
                row_context=row_dict,
                doc_dict=doc_dict,
                run_dir=run_dir,
                provider=provider,
                text_model_id=text_model_id,
                retrieval=retrieval,
                style_profile=style_profile,
                field_type=col_def.get("field_type"),
                allowed_values=col_def.get("allowed_values"),
                caps=provider_mode.capabilities if provider_mode else None,
                vision_model_id=vision_model_id if config.figure_review.enabled else None,
                is_verify_mode=config.verify_mode,
                existing_value=existing_value if config.verify_mode else None,
                recall_rescue_enabled=config.retrieval.recall_rescue_enabled,
                whole_document_mode=config.retrieval.whole_document_mode,
                whole_document_max_chars=config.retrieval.whole_document_max_chars,
                provider_mode_str=provider_mode.mode if provider_mode else "unknown",
                artifact_context=artifact_context,
                max_figures_for_review=max(1, config.figure_review.max_figures_per_paper),
                skip_figure_review_when_prompt_only_degraded=(
                    config.figure_review.skip_when_prompt_only_degraded
                ),
                stats_sink=cell_stats,
            )

            proposals_generated += 1
            run_stats["counters"]["processed_cells"] += 1
            if cell_stats.get("recall_rescue_used"):
                run_stats["counters"]["recall_rescue_cells"] += 1
            if cell_stats.get("whole_document_used"):
                run_stats["counters"]["whole_document_cells"] += 1
            if cell_stats.get("needs_more_evidence"):
                run_stats["counters"]["needs_more_evidence_cells"] += 1
            if cell_stats.get("figure_review_triggered"):
                run_stats["counters"]["figure_review_triggered_cells"] += 1
            if cell_stats.get("figure_review_calls"):
                run_stats["counters"]["figure_review_cells"] += 1
            if cell_stats.get("figure_hits_count"):
                run_stats["counters"]["figure_review_hit_cells"] += 1
                run_stats["counters"]["figure_review_hits_total"] += int(cell_stats.get("figure_hits_count", 0) or 0)
            if cell_stats.get("figure_review_useful"):
                run_stats["counters"]["figure_review_useful_cells"] += 1
            if cell_stats.get("figure_review_rescued"):
                run_stats["counters"]["figure_review_rescue_cells"] += 1
            pdf_stats["cells_processed"] += 1
            cell_stats["proposal_id"] = proposal.proposal_id
            run_stats["per_cell"].append(cell_stats)

        runtime_caps = getattr(provider, "_capabilities", None)
        if provider_mode and runtime_caps is not None:
            provider_mode.capabilities = runtime_caps
            provider_mode.structured_output_mode = runtime_caps.structured_output_mode
            provider_mode.structured_output_reason = _canonical_structured_output_reason(
                runtime_caps.structured_output_mode,
                getattr(runtime_caps, "structured_output_reason", None),
            )
            provider_mode.structured_output_fallback_used = runtime_caps.structured_output_mode in ("json_object", "none")
            provider_mode.vision_structured_output_mode = runtime_caps.vision_structured_output_mode
            provider_mode.vision_structured_output_reason = _canonical_structured_output_reason(
                runtime_caps.vision_structured_output_mode,
                getattr(runtime_caps, "vision_structured_output_reason", None),
            )
            run_data["structured_output_mode"] = runtime_caps.structured_output_mode
            run_data["structured_output_reason"] = provider_mode.structured_output_reason
            run_data["structured_output_fallback_used"] = runtime_caps.structured_output_mode in ("json_object", "none")
            run_data["vision_structured_output_mode"] = provider_mode.vision_structured_output_mode
            run_data["vision_structured_output_reason"] = provider_mode.vision_structured_output_reason
            write_json(get_provider_mode_path(output_dir, run_id), provider_mode.model_dump())

        run_data["proposals_generated"] = proposals_generated
        run_stats["counters"]["proposals_generated"] = proposals_generated
        figure_review_total_ms = round(
            sum(float(cell.get("figure_review_ms", 0.0) or 0.0) for cell in run_stats["per_cell"]),
            3,
        )
        triggered_cells = int(run_stats["counters"].get("figure_review_triggered_cells", 0) or 0)
        run_stats["per_run"]["figure_review_roi"] = {
            "triggered_cells": triggered_cells,
            "reviewed_cells": int(run_stats["counters"].get("figure_review_cells", 0) or 0),
            "hit_cells": int(run_stats["counters"].get("figure_review_hit_cells", 0) or 0),
            "useful_cells": int(run_stats["counters"].get("figure_review_useful_cells", 0) or 0),
            "rescue_cells": int(run_stats["counters"].get("figure_review_rescue_cells", 0) or 0),
            "hits_total": int(run_stats["counters"].get("figure_review_hits_total", 0) or 0),
            "total_ms": figure_review_total_ms,
            "avg_ms_per_triggered_cell": round(figure_review_total_ms / triggered_cells, 3) if triggered_cells else 0.0,
        }
        proposals = load_proposals(run_dir)
        fallback_count = sum("fallback_evidence_used" in proposal.warning_flags for proposal in proposals)
        weak_count = sum(proposal.support == SupportLabel.weak_evidence for proposal in proposals)
        if fallback_count:
            run_data.setdefault("warnings", []).append({
                "category": WC.fallback_evidence_used.value,
                "message": f"{fallback_count} proposal(s) require evidence fallback review.",
                "context": {"count": fallback_count},
            })
        if weak_count:
            run_data.setdefault("warnings", []).append({
                "category": WC.weak_evidence.value,
                "message": f"{weak_count} proposal(s) have weak evidence.",
                "context": {"count": weak_count},
            })
        run_data = sync_provider_artifacts(run_data, provider, run_dir)
        save_run(run_data)

        warnings = run_data.get("warnings", [])
        final_status = (
            RunStatus.completed_with_warnings if warnings else RunStatus.completed
        )
        _finalize_active_stage()
        run_data = apply_transition(run_data, final_status)
        run_data["current_stage"] = None
        run_stats["per_run"]["completed_at"] = run_data.get("completed_at")
        run_stats["per_run"]["run_total_ms"] = round((perf_counter() - run_started_perf) * 1000.0, 3)
        run_data = sync_provider_artifacts(run_data, provider, run_dir)
        save_run(run_data)
        save_run_stats()

        run_summary_path = get_run_summary_path(output_dir, run_id)
        write_json(run_summary_path, run_data)

        reviewer_summary_path = get_reviewer_summary_path(output_dir, run_id)
        write_json(
            reviewer_summary_path,
            {
                "run_id": run_id,
                "verify_mode": bool(run_data.get("verify_mode", False)),
                "eval_mode": bool(run_data.get("eval_mode", False)),
                "run_mode": run_data.get("run_mode", "normal"),
                "provider_token": run_data.get("provider_token"),
                "provider_locality": run_data.get("provider_locality"),
                "provider_mode": run_data.get("provider_mode"),
                "provider_text_model_id": run_data.get("provider_text_model_id"),
                "provider_vision_model_id": run_data.get("provider_vision_model_id"),
                "structured_output_mode": run_data.get("structured_output_mode"),
                "structured_output_reason": run_data.get("structured_output_reason"),
                "structured_output_fallback_used": bool(
                    run_data.get("structured_output_fallback_used", False)
                ),
                "vision_structured_output_mode": run_data.get("vision_structured_output_mode"),
                "vision_structured_output_reason": run_data.get("vision_structured_output_reason"),
                "provider_readiness_error": run_data.get("provider_readiness_error"),
                "provider_readiness_reason": run_data.get("provider_readiness_reason"),
                "retrieval_mode": run_data.get("retrieval_mode"),
                "prompt_version": run_data.get("prompt_version"),
                "prompt_hash": run_data.get("prompt_hash"),
                "prompt_bundle_id": run_data.get("prompt_bundle_id"),
                "prompt_bundle_version": run_data.get("prompt_bundle_version"),
                "prompt_bundle_path": run_data.get("prompt_bundle_path"),
                "prompt_manifest_hash": run_data.get("prompt_manifest_hash"),
                "prompt_bundle_hash": run_data.get("prompt_bundle_hash"),
                "prompt_keys_used": run_data.get("prompt_keys_used", []),
                "prompt_files": run_data.get("prompt_files"),
                "config_hash": run_data.get("config_hash"),
                "config_snapshot_path": run_data.get("config_snapshot_path"),
                "run_stats_path": run_data.get("run_stats_path"),
                "schema_hash": run_data.get("schema_hash"),
                "schema_version": run_data.get("schema_version"),
                "parser_identity": run_data.get("parser_identity"),
                "parser_version": run_data.get("parser_version"),
                "eval_artifacts": run_data.get("eval_artifacts"),
                "total_proposals": proposals_generated,
                "reviewed": 0,
                "accepted": 0,
                "accepted_with_edit": 0,
                "confirmed_no_data": 0,
                "rejected": 0,
                "pending": proposals_generated,
                "actionable_total_proposals": proposals_generated,
                "actionable_reviewed": 0,
                "actionable_pending": proposals_generated,
                "diagnostic_only_total_proposals": 0,
                "explicitly_accepted": 0,
                "explicitly_rejected": 0,
                "confirmed_absent": 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        run_data = persist_artifact_summary(run_data, run_dir)
        save_run(run_data)
        write_json(run_summary_path, run_data)

    except asyncio.CancelledError:
        _finalize_active_stage()
        run_data = dict(run_data)
        run_data["status"] = RunStatus.interrupted.value
        run_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        run_data["current_stage"] = None
        run_stats["per_run"]["completed_at"] = run_data["completed_at"]
        run_stats["per_run"]["run_total_ms"] = round((perf_counter() - run_started_perf) * 1000.0, 3)
        if "run_dir" in locals():
            run_data = sync_provider_artifacts(run_data, locals().get("provider"), run_dir)
        save_run(run_data)
        save_run_stats()
        raise
    except Exception as e:
        _finalize_active_stage()
        try:
            run_data = apply_transition(
                run_data, RunStatus.failed, error_message=str(e)
            )
        except Exception:
            run_data = dict(run_data)
            run_data["status"] = RunStatus.failed.value
            run_data["error_message"] = str(e)
        run_data["current_stage"] = None
        run_stats["per_run"]["completed_at"] = run_data.get("completed_at") or datetime.now(timezone.utc).isoformat()
        run_stats["per_run"]["run_total_ms"] = round((perf_counter() - run_started_perf) * 1000.0, 3)
        if "run_dir" in locals():
            run_data = sync_provider_artifacts(run_data, locals().get("provider"), run_dir)
        save_run(run_data)
        write_final_summaries(run_data, run_data.get("proposals_generated", 0))


def launch_run(
    run_id: str,
    config: RunConfig,
    config_path: Optional[str],
    output_dir: str,
    resolved_inputs: Optional[dict[str, object]] = None,
) -> None:
    """Launch a run as an asyncio background task."""

    async def _register_and_run() -> None:
        lock = _get_lock()
        async with lock:
            task = asyncio.current_task()
            _active_runs[run_id] = task  # type: ignore[assignment]
        try:
            await run_pipeline(
                run_id,
                config,
                config_path,
                output_dir,
                resolved_inputs=resolved_inputs,
            )
        finally:
            async with lock:
                _active_runs.pop(run_id, None)

    asyncio.create_task(_register_and_run())


async def abort_run(run_id: str) -> bool:
    """Cancel an active run task if it exists."""
    lock = _get_lock()
    async with lock:
        task = _active_runs.get(run_id)
        if task is None:
            return False
        task.cancel()
        return True
