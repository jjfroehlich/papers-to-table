from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from .artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_reviewer_summary_path,
    get_run_json_path,
    get_run_summary_path,
    init_run_bundle,
    write_json,
)
from .config import RunConfig, check_readiness
from .ids import generate_run_id
from .ingest import (
    get_eligible_cells,
    load_schema,
    load_table,
    validate_metadata_columns,
    validate_schema_columns,
)
from .lifecycle import apply_transition
from .schemas import RunStatus

_active_runs: dict[str, asyncio.Task] = {}


def get_initial_run_data(
    run_id: str, config: RunConfig, config_path: Optional[str]
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "run_id": run_id,
        "status": RunStatus.created.value,
        "config_path": config_path,
        "table_path": config.table_path,
        "schema_path": config.schema_path,
        "pdf_dir": config.pdf_dir,
        "output_dir": config.output_dir,
        "verify_mode": config.verify_mode,
        "provider_token": config.provider.token,
        "provider_locality": config.provider.locality,
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
) -> None:
    """Main staged runner - runs as asyncio task."""
    run_json_path = get_run_json_path(output_dir, run_id)

    def save_run(data: dict) -> None:
        write_json(run_json_path, data)

    def update_stage(data: dict, stage: str) -> dict:
        data = dict(data)
        data["current_stage"] = stage
        return data

    run_data = get_initial_run_data(run_id, config, config_path)
    init_run_bundle(output_dir, run_id)
    save_run(run_data)

    try:
        # Stage: validating
        run_data = apply_transition(run_data, RunStatus.validating)
        run_data = update_stage(run_data, "validating")
        save_run(run_data)

        config_snap_path = get_config_snapshot_path(output_dir, run_id)
        write_json(config_snap_path, config.model_dump())

        input_summary_path = get_input_summary_path(output_dir, run_id)
        now = datetime.now(timezone.utc).isoformat()
        early_input_summary = {
            "run_id": run_id,
            "table_path": config.table_path,
            "schema_path": config.schema_path,
            "pdf_dir": config.pdf_dir,
            "output_dir": output_dir,
            "verify_mode": config.verify_mode,
            "table_rows": None,
            "schema_columns": None,
            "pdf_count": None,
            "recorded_at": now,
        }
        write_json(input_summary_path, early_input_summary)

        readiness = await check_readiness(config)
        if not readiness.ok:
            run_data = apply_transition(
                run_data,
                RunStatus.failed,
                error_message="; ".join(readiness.errors),
            )
            save_run(run_data)
            return

        # Stage: load_inputs
        run_data = apply_transition(run_data, RunStatus.running)
        run_data = update_stage(run_data, "load_inputs")
        save_run(run_data)

        df = load_table(config.table_path)

        meta_errors = validate_metadata_columns(df)
        if meta_errors:
            run_data = apply_transition(
                run_data,
                RunStatus.failed,
                error_message="; ".join(meta_errors),
            )
            save_run(run_data)
            return

        schema = load_schema(config.schema_path, config.table_path)
        schema_errors = validate_schema_columns(schema)
        if schema_errors:
            run_data = apply_transition(
                run_data,
                RunStatus.failed,
                error_message="; ".join(schema_errors),
            )
            save_run(run_data)
            return

        eligible = get_eligible_cells(df, schema, config.verify_mode)

        pdf_files = [f for f in os.listdir(config.pdf_dir) if f.lower().endswith(".pdf")]

        input_summary = {
            **early_input_summary,
            "table_rows": len(df),
            "schema_columns": len(schema),
            "pdf_count": len(pdf_files),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(input_summary_path, input_summary)

        run_data["total_rows"] = len(df)
        run_data["eligible_cells"] = len(eligible)
        save_run(run_data)

        # Stage: run_pipeline stub (Batch 2+ implements parsing/matching/extraction)
        run_data = update_stage(run_data, "run_pipeline")
        save_run(run_data)

        await asyncio.sleep(0)  # yield to event loop

        warnings = run_data.get("warnings", [])
        final_status = (
            RunStatus.completed_with_warnings if warnings else RunStatus.completed
        )
        run_data = apply_transition(run_data, final_status)
        run_data["current_stage"] = None
        save_run(run_data)

        run_summary_path = get_run_summary_path(output_dir, run_id)
        write_json(run_summary_path, run_data)

        reviewer_summary_path = get_reviewer_summary_path(output_dir, run_id)
        write_json(
            reviewer_summary_path,
            {
                "run_id": run_id,
                "total_proposals": 0,
                "accepted": 0,
                "accepted_with_edit": 0,
                "confirmed_no_data": 0,
                "rejected": 0,
                "pending": 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    except asyncio.CancelledError:
        run_data = dict(run_data)
        run_data["status"] = RunStatus.interrupted.value
        run_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        run_data["current_stage"] = None
        save_run(run_data)
        raise
    except Exception as e:
        try:
            run_data = apply_transition(
                run_data, RunStatus.failed, error_message=str(e)
            )
        except Exception:
            run_data = dict(run_data)
            run_data["status"] = RunStatus.failed.value
            run_data["error_message"] = str(e)
        run_data["current_stage"] = None
        save_run(run_data)


def launch_run(
    run_id: str,
    config: RunConfig,
    config_path: Optional[str],
    output_dir: str,
) -> None:
    """Launch a run as an asyncio background task."""
    task = asyncio.create_task(
        run_pipeline(run_id, config, config_path, output_dir)
    )
    _active_runs[run_id] = task
    task.add_done_callback(lambda t: _active_runs.pop(run_id, None))
