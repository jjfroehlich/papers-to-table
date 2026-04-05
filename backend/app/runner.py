from __future__ import annotations

import asyncio
import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

from .artifacts import (
    hash_file,
    hash_json_data,
    get_config_snapshot_path,
    get_input_summary_path,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
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
from .provider import ProviderError, initialize_provider
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
    prompt_identity = get_prompt_identity()
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
        "provider_vision_model_id": (
            config.provider.vision_model.model_id if config.provider.vision_model else None
        ),
        "structured_output_mode": None,
        "structured_output_fallback_used": False,
        "provider_readiness_reason": None,
        "provider_request_counts": {},
        "prompt_version": prompt_identity["prompt_version"],
        "prompt_hash": prompt_identity["prompt_hash"],
        "config_hash": None,
        "config_snapshot_path": None,
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

    def write_final_summaries(data: dict, proposals_generated: int = 0) -> None:
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
                "provider_vision_model_id": data.get("provider_vision_model_id"),
                "structured_output_mode": data.get("structured_output_mode"),
                "structured_output_fallback_used": bool(
                    data.get("structured_output_fallback_used", False)
                ),
                "provider_readiness_error": data.get("provider_readiness_error"),
                "provider_readiness_reason": data.get("provider_readiness_reason"),
                "prompt_version": data.get("prompt_version"),
                "prompt_hash": data.get("prompt_hash"),
                "config_hash": data.get("config_hash"),
                "config_snapshot_path": data.get("config_snapshot_path"),
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

    def sync_provider_request_counts(data: dict, provider_obj: object, run_dir: pathlib.Path) -> dict:
        """Persist provider request counters into run artifacts and run.json."""
        if provider_obj is None:
            return data
        get_counts = getattr(provider_obj, "get_request_counts", None)
        if not callable(get_counts):
            return data
        try:
            counts = get_counts() or {}
            data = dict(data)
            data["provider_request_counts"] = counts
            write_json(
                run_dir / "provider_request_counts.json",
                {
                    "run_id": run_id,
                    "provider_token": config.provider.token,
                    "counts": counts,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return data
        except Exception:
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
        save_run(run_data)

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
            "prompt_version": run_data["prompt_version"],
            "prompt_hash": run_data["prompt_hash"],
            "config_hash": run_data["config_hash"],
            "config_snapshot_path": run_data["config_snapshot_path"],
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
                    get_run_dir(output_dir, run_id) / "provider_mode.json",
                    {
                        "token": config.provider.token,
                        "locality": config.provider.locality,
                        "mode": readiness.provider_mode or "unknown",
                        "text_model_id": text_model_id,
                        "vision_model_id": vision_model_id,
                        "structured_output_mode": readiness.structured_output_mode,
                        "structured_output_fallback_used": bool(readiness.structured_output_fallback_used),
                        "readiness_reason": readiness.provider_readiness_reason,
                        "readiness_error": readiness.provider_readiness_error,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
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
        save_run(run_data)

        # Stage: initialize provider (T050, T052a)
        run_data = update_stage(run_data, "provider_init")
        save_run(run_data)

        provider = None
        provider_mode = None
        provider_init_error: Optional[str] = None

        try:
            provider, provider_mode = await initialize_provider(
                config.provider,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
            )
        except ProviderError as e:
            provider_init_error = str(e)
            provider_init_reason = getattr(e, "reason", None) or "provider_unreachable"

            warning_category = {
                "provider_unreachable": WC.provider_unreachable.value,
                "model_unavailable": WC.model_unavailable.value,
                "no_compatible_structured_mode": WC.structured_mode_capability_mismatch.value,
            }.get(provider_init_reason, WC.provider_unreachable.value)

            warning_prefix = {
                "provider_unreachable": "Provider unreachable",
                "model_unavailable": "Model unavailable",
                "no_compatible_structured_mode": "No compatible structured-output mode",
            }.get(provider_init_reason, "Provider unavailable")

            run_data["provider_mode"] = "unavailable"
            run_data["provider_readiness_error"] = provider_init_error
            run_data["provider_readiness_reason"] = provider_init_reason
            run_data["structured_output_mode"] = "none"
            run_data["structured_output_fallback_used"] = False
            write_json(
                run_dir / "provider_mode.json",
                {
                    "token": config.provider.token,
                    "locality": config.provider.locality,
                    "mode": "unavailable",
                    "text_model_id": text_model_id,
                    "vision_model_id": vision_model_id,
                    "structured_output_mode": "none",
                    "structured_output_fallback_used": False,
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
            run_data["structured_output_fallback_used"] = provider_mode.structured_output_fallback_used
            write_json(run_dir / "provider_mode.json", provider_mode.model_dump())
            caps = provider_mode.capabilities
            if caps and getattr(caps, "structured_output_mode", None) == "json_object":
                run_data.setdefault("warnings", []).append({
                    "category": WC.provider_degraded.value,
                    "message": (
                        "Provider is running in degraded structured-output mode (json_object fallback); "
                        "json_schema is unavailable for this model/runtime combination."
                    ),
                    "context": {
                        "provider": config.provider.token,
                        "structured_output_mode": "json_object",
                    },
                })
            run_data = sync_provider_request_counts(run_data, provider, run_dir)
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

                if diagnostics.fallback_used:
                    key = (pdf_id, "fallback")
                    if key not in parse_warning_messages:
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
                    run_data.setdefault("warnings", []).append({
                        "category": WC.partial_extraction.value,
                        "message": f"{pdf_id}: {gap}",
                        "context": {"pdf_id": pdf_id},
                    })
                    parse_warning_messages.add(key)
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
            df=style_profile_df,
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
                artifact_context=artifact_context,
                max_figures_for_review=max(1, config.figure_review.max_figures_per_paper),
            )

            proposals_generated += 1

        run_data["proposals_generated"] = proposals_generated
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
        run_data = sync_provider_request_counts(run_data, provider, run_dir)
        save_run(run_data)

        warnings = run_data.get("warnings", [])
        final_status = (
            RunStatus.completed_with_warnings if warnings else RunStatus.completed
        )
        run_data = apply_transition(run_data, final_status)
        run_data["current_stage"] = None
        run_data = sync_provider_request_counts(run_data, provider, run_dir)
        save_run(run_data)

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
                "structured_output_fallback_used": bool(
                    run_data.get("structured_output_fallback_used", False)
                ),
                "provider_readiness_error": run_data.get("provider_readiness_error"),
                "provider_readiness_reason": run_data.get("provider_readiness_reason"),
                "prompt_version": run_data.get("prompt_version"),
                "prompt_hash": run_data.get("prompt_hash"),
                "config_hash": run_data.get("config_hash"),
                "config_snapshot_path": run_data.get("config_snapshot_path"),
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

    except asyncio.CancelledError:
        run_data = dict(run_data)
        run_data["status"] = RunStatus.interrupted.value
        run_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        run_data["current_stage"] = None
        if "provider" in locals() and "run_dir" in locals():
            run_data = sync_provider_request_counts(run_data, provider, run_dir)
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
        if "provider" in locals() and "run_dir" in locals():
            run_data = sync_provider_request_counts(run_data, provider, run_dir)
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
