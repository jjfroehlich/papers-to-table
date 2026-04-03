from __future__ import annotations

import asyncio
import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

from .artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    init_run_bundle,
    write_json,
)
from .config import RunConfig, check_readiness
from .extraction import (
    extract_cell,
)
from .ids import generate_cell_id, generate_row_id, generate_run_id
from .ingest import (
    get_eligible_cells,
    load_schema,
    load_table,
    validate_metadata_columns,
    validate_schema_columns,
)
from .lifecycle import apply_transition
from .matching import MatchResult, persist_match_artifacts, run_matching
from .parsing import parse_pdf
from .provider import ProviderError, initialize_provider
from .retrieval import run_retrieval_for_cell
from .schemas import MatchOutcome, RunStatus, WarningCategory
from .style_profiles import run_style_profiles_stage

_active_runs: dict[str, asyncio.Task] = {}
_active_runs_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _active_runs_lock
    if _active_runs_lock is None:
        _active_runs_lock = asyncio.Lock()
    return _active_runs_lock


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

    def fail_run(data: dict, error_message: str) -> dict:
        data = apply_transition(data, RunStatus.failed, error_message=error_message)
        data["current_stage"] = None
        return data

    run_data = get_initial_run_data(run_id, config, config_path)
    init_run_bundle(output_dir, run_id)
    save_run(run_data)

    try:
        from .schemas import WarningCategory as WC

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
            run_data = fail_run(run_data, "; ".join(readiness.errors))
            save_run(run_data)
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
            return

        schema = load_schema(config.schema_path, config.table_path)
        schema_errors = validate_schema_columns(schema)
        if schema_errors:
            run_data = fail_run(run_data, "; ".join(schema_errors))
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

        run_dir = get_run_dir(output_dir, run_id)

        # Stage: initialize provider (T050, T052a)
        run_data = update_stage(run_data, "provider_init")
        save_run(run_data)

        provider = None
        provider_mode = None
        provider_init_error: Optional[str] = None
        text_model_id = config.provider.text_model.model_id
        vision_model_id = (
            config.provider.vision_model.model_id
            if config.provider.vision_model
            else None
        )

        try:
            provider, provider_mode = await initialize_provider(
                config.provider,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
            )
        except ProviderError as e:
            provider_init_error = str(e)
            run_data.setdefault("warnings", []).append({
                "category": WC.provider_unreachable.value,
                "message": f"Provider unavailable: {provider_init_error}",
                "context": {"provider": config.provider.token},
            })
            save_run(run_data)

        if provider is None:
            run_data = fail_run(
                run_data,
                provider_init_error or "Provider unavailable during initialization",
            )
            save_run(run_data)
            return

        # Persist provider mode in run artifacts (T052a)
        if provider_mode:
            write_json(run_dir / "provider_mode.json", provider_mode.model_dump())

        # Stage: parse
        run_data = update_stage(run_data, "parse")
        save_run(run_data)

        parsed_docs: list[dict] = []
        parse_errors: list[str] = []

        for pdf_file in pdf_files:
            pdf_path = os.path.join(config.pdf_dir, pdf_file)
            pdf_id = pathlib.Path(pdf_file).stem
            await asyncio.sleep(0)  # yield to event loop between PDFs
            try:
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
                parsed_docs.append(doc.model_dump())
            except Exception as e:
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
        save_run(run_data)

        # Stage: style profiles (T041-T044)
        run_data = update_stage(run_data, "style_profiles")
        save_run(run_data)

        # Pass provider for LLM-assisted profiling when available
        style_profiles = await run_style_profiles_stage(
            run_dir=run_dir,
            df=df,
            schema=schema,
            provider=provider,  # None → heuristic fallback
            model_id=text_model_id if provider is not None else None,
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

            row_dict = df.iloc[row_idx].to_dict() if row_idx < len(df) else {}
            row_id = generate_row_id(row_idx, str(row_dict.get("Title", "")))
            cell_id = generate_cell_id(row_id, col_name)
            existing_value = cell.get("current_value")

            retrieval = run_retrieval_for_cell(
                run_id=run_id,
                pdf_id=pdf_id,
                column_name=col_name,
                column_description=col_desc,
                doc_dict=doc_dict,
                run_dir=run_dir,
                top_k=config.retrieval.top_k,
            )

            style_profile = style_profiles.get(col_name)

            await asyncio.sleep(0)  # yield between cells

            await extract_cell(
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
            )

            proposals_generated += 1

        run_data["proposals_generated"] = proposals_generated
        save_run(run_data)

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
                "total_proposals": proposals_generated,
                "accepted": 0,
                "accepted_with_edit": 0,
                "confirmed_no_data": 0,
                "rejected": 0,
                "pending": proposals_generated,
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

    async def _register_and_run() -> None:
        lock = _get_lock()
        async with lock:
            task = asyncio.current_task()
            _active_runs[run_id] = task  # type: ignore[assignment]
        try:
            await run_pipeline(run_id, config, config_path, output_dir)
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
