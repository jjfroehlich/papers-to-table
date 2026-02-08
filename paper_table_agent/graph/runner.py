from __future__ import annotations

import json
import uuid
import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import httpx
from rapidfuzz import fuzz
from paper_table_agent.config import (
    RunConfig,
    RunPaths,
    capture_run_config,
    load_prompt_versions,
    validate_schema_columns,
)
from paper_table_agent.graph.extraction import (
    GroupContext,
    build_error_records,
    build_chunk_lookup_from_list,
    build_proposal_records,
    build_extract_prompt_batches,
    build_verify_records,
    extract_group,
    verify_proposals,
    verify_cells,
)
from paper_table_agent.graph.context_planner import ContextPlan, plan_context
from paper_table_agent.graph.evidence_finder import find_evidence_for_proposals
from paper_table_agent.graph.evaluation import evaluate_run
from paper_table_agent.graph.matching import (
    adjudicate_match,
    build_match_record,
    deterministic_match,
    extract_header_with_repair,
    shortlist_candidates,
)
from paper_table_agent.graph.reporting import write_mapping_report, write_run_report
from paper_table_agent.io.examples import select_examples
from paper_table_agent.io.locks import build_locks
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.llm.client import (
    LlmClient,
    LlmConfig,
    LlmJsonError,
    estimate_tokens,
    get_capability_cache,
)
from paper_table_agent.llm.models import AdjudicationResult, ContextSummaryResult, PaperMemoryResult, QueryExpansionResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.llm.embeddings import (
    EmbeddingClient,
    EmbeddingConfig,
    HashEmbeddingClient,
    StubEmbeddingClient,
)
from paper_table_agent.pdf.highlight import (
    assess_highlight_rects,
    locate_quote,
    locate_quote_span,
    salvage_quote_from_tokens,
)
from paper_table_agent.pdf.grobid import extract_grobid, save_grobid
from paper_table_agent.pdf.ocr import run_ocr, should_trigger_ocr
from paper_table_agent.pdf.parser import compute_sha1, parse_pdf, save_parsed
from paper_table_agent.retrieval.chunking import build_chunks, to_dicts
from paper_table_agent.retrieval.index import build_index, load_index_if_fresh, save_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.store.db import Store
from paper_table_agent.utils.logging import configure_logging, log_error
from paper_table_agent.text.normalization import normalize_key
from paper_table_agent.text.normalization import normalize_for_matching
from paper_table_agent.text.normalization import normalize_chunk_id
from paper_table_agent.text.normalization import normalize_str_for_prompt


@dataclass
class PdfRecord:
    pdf_id: str
    path: Path
    sha1: str


@dataclass
class RunContext:
    config: RunConfig
    run_paths: RunPaths
    store: Store
    table: Any
    schema_specs: list[Any]
    grouped: dict[str, list[Any]]
    lock_map: dict[str, set[str]]
    rows_data: list[dict[str, Any]]
    assigned_rows: dict[str, dict[str, Any]]
    header_client: LlmClient
    match_client: LlmClient
    extract_client: LlmClient
    helper_client: LlmClient
    embedding_client: EmbeddingClient | None
    reranker_client: EmbeddingClient | None
    retrieval_config: RetrievalConfig
    examples: dict[str, list[dict[str, Any]]]
    logger: Any
    error_path: Path
    prompt_versions: dict[str, str] = field(default_factory=dict)
    audit_targets: dict[str, set[str]] = field(default_factory=dict)
    audit_stats: dict[str, Any] = field(default_factory=dict)
    retrieval_cache: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = field(default_factory=dict)


def _llm_error_metadata(exc: LlmJsonError) -> dict[str, Any]:
    return {
        "http_status": exc.http_status,
        "error_substring": exc.error_substring,
        "guided_json_active": exc.guided_json_active,
        "error_class": exc.error_class,
    }


def _disable_guided_json_for_run(context: RunContext, reason: dict[str, Any]) -> None:
    context.config.provider.guided_json_mode = "off"
    for client in (
        context.header_client,
        context.match_client,
        context.extract_client,
        context.helper_client,
    ):
        client.config.guided_json_mode = "off"
    context.store.record_event("warning", "health_check_guided_json_disabled", reason)
    context.logger.warning("disabling guided JSON for this run: %s", reason)


@dataclass
class DebugExtractionTracker:
    pdf_id: str
    chunks_indexed: int = 0
    retrieval_hits: dict[str, int] = field(default_factory=dict)
    retrieval_debug: dict[str, Any] = field(default_factory=dict)
    extraction_attempts: dict[str, int] = field(default_factory=dict)
    proposal_counts: dict[str, int] = field(
        default_factory=lambda: {
            "value_present": 0,
            "evidence_present": 0,
            "evidence_validation_failed": 0,
        }
    )
    failure_reasons: dict[str, int] = field(default_factory=dict)

    def record_retrieval_hits(self, column: str, count: int) -> None:
        current = self.retrieval_hits.get(column, 0)
        self.retrieval_hits[column] = max(current, count)

    def record_retrieval_debug(self, column: str, debug: dict[str, Any]) -> None:
        self.retrieval_debug[column] = debug

    def record_attempts(self, columns: list[str]) -> None:
        for column in columns:
            self.extraction_attempts[column] = self.extraction_attempts.get(column, 0) + 1

    def record_proposals(self, proposals: list[dict[str, Any]]) -> None:
        for proposal in proposals:
            if proposal.get("proposed_value") is not None:
                self.proposal_counts["value_present"] += 1
            evidence_items = proposal.get("evidence") or []
            if evidence_items:
                self.proposal_counts["evidence_present"] += 1
            flags = proposal.get("flags") or {}
            if flags.get("evidence_validation_errors"):
                self.proposal_counts["evidence_validation_failed"] += 1
            reason = flags.get("failure_reason")
            if reason:
                self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1

    def to_payload(self) -> dict[str, Any]:
        sorted_reasons = sorted(self.failure_reasons.items(), key=lambda item: item[1], reverse=True)
        top_reasons = [{"reason": reason, "count": count} for reason, count in sorted_reasons[:3]]
        payload = {
            "pdf_id": self.pdf_id,
            "chunks_indexed": self.chunks_indexed,
            "retrieval_hits_per_column": self.retrieval_hits,
            "extraction_attempts_per_column": self.extraction_attempts,
            "proposal_counts": self.proposal_counts,
            "top_failure_reasons": top_reasons,
        }
        if self.retrieval_debug:
            payload["retrieval_debug"] = self.retrieval_debug
        return payload


def run_pipeline(config: RunConfig, run_paths: RunPaths, store: Store) -> None:
    run_config_path = run_paths.run_dir / "run_config.json"
    if not run_config_path.exists():
        prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
        capture_run_config(config, run_paths, prompt_versions)
    context, pdfs = _prepare_context(config, run_paths, store)
    health_status = _run_health_checks(context)
    if health_status.get("status") == "failed":
        write_mapping_report(store, run_paths.exports_dir, write_reports=config.output.debug_reports)
        status = write_run_report(store, run_paths)
        if status == "failed":
            (run_paths.run_dir / "FAILED").write_text("failed", encoding="utf-8")
        return
    existing_pdfs = {row["pdf_id"]: row for row in store.list_pdfs()}
    for pdf in pdfs:
        if _stop_requested(run_paths):
            context.logger.info("stop requested; ending run early")
            break
        if _process_pdf(context, pdf, existing_pdfs):
            context.logger.info("processed pdf %s", pdf.pdf_id)
    write_mapping_report(store, run_paths.exports_dir, write_reports=config.output.debug_reports)
    status = write_run_report(store, run_paths)
    try:
        evaluate_run(
            run_dir=run_paths.run_dir,
            db_path=run_paths.db_path,
            table_path=config.table_path,
            schema_sheet_name=config.schema_sheet_name,
            pdf_folder=config.pdf_folder,
            output_dir=run_paths.exports_dir,
        )
    except Exception as exc:  # noqa: BLE001
        store.record_event("warning", "eval_failed", {"error": str(exc)})
    if status == "completed_with_errors":
        (run_paths.run_dir / "COMPLETED_WITH_ERRORS").write_text("done", encoding="utf-8")
    elif status == "completed_with_warnings":
        (run_paths.run_dir / "COMPLETED_WITH_WARNINGS").write_text("done", encoding="utf-8")
    elif status != "failed":
        (run_paths.run_dir / "COMPLETED").write_text("done", encoding="utf-8")


def _prepare_context(config: RunConfig, run_paths: RunPaths, store: Store) -> tuple[RunContext, list[PdfRecord]]:
    logger, _ = configure_logging(run_paths.logs_dir)
    error_path = run_paths.logs_dir / "errors.jsonl"

    table = load_table(config.table_path)
    schema_source = config.table_path
    if config.schema_mode == "separate" and config.schema_path:
        schema_source = config.schema_path
    schema_specs = load_schema(schema_source, config.schema_sheet_name)
    _align_schema_columns(schema_specs, table.dataframe.columns)
    validate_schema_columns([spec.column_name for spec in schema_specs], table.dataframe.columns)
    grouped = group_columns(schema_specs)
    grouped = _apply_group_override(grouped, config.extraction.groups)
    locks = build_locks(table.dataframe)
    store.insert_locks(locks)
    lock_map: dict[str, set[str]] = {}
    for lock in locks:
        lock_map.setdefault(lock["row_id"], set()).add(lock["column"])
    audit_targets, audit_stats = _build_audit_targets(
        table.dataframe,
        schema_specs,
        lock_map,
        config.audit,
    )
    if audit_stats:
        store.record_event("info", "audit_plan", audit_stats)
    rows_payload = []
    for row_index, row in table.dataframe.iterrows():
        rows_payload.append(
            {
                "row_id": str(row_index),
                "row_index": int(row_index),
                "title": str(row.get(config.title_col or "")) if config.title_col else "",
                "authors": str(row.get(config.authors_col or "")) if config.authors_col else "",
                "year": str(row.get(config.year_col or "")) if config.year_col else "",
                "doi": str(row.get(config.doi_col or "")) if config.doi_col else "",
            }
        )
    store.insert_rows(rows_payload)

    pdfs = _enumerate_pdfs(config.pdf_folder)
    for pdf in pdfs:
        store.insert_pdf(pdf.pdf_id, str(pdf.path), pdf.sha1)

    _ensure_retrieval_backends(config, logger, store)
    mock_mode = config.provider.mock_mode or config.provider.mode in {"mock", "stub"}
    mock_payloads = None
    if mock_mode and config.provider.mock_payloads_path:
        if config.provider.mock_payloads_path.is_dir():
            mock_payloads = {}
            for path in config.provider.mock_payloads_path.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    mock_payloads.update(payload)
        else:
            mock_payloads = json.loads(config.provider.mock_payloads_path.read_text(encoding="utf-8"))
    record_path = None
    payload_record_path = None
    if config.provider.record_requests:
        record_path = config.provider.record_path or (run_paths.logs_dir / "llm_records.jsonl")
    if config.provider.record_payloads:
        payload_record_path = config.provider.payload_record_path or (run_paths.logs_dir / "llm_payloads.jsonl")
    header_client = _build_llm_client(
        config.provider,
        model=config.provider.model_header,
        logger=logger,
        record_path=record_path,
        payload_record_path=payload_record_path,
        mock_mode=mock_mode,
        mock_payloads=mock_payloads,
    )
    match_client = _build_llm_client(
        config.provider,
        model=config.provider.model_match,
        logger=logger,
        record_path=record_path,
        payload_record_path=payload_record_path,
        mock_mode=mock_mode,
        mock_payloads=mock_payloads,
    )
    extract_client = _build_llm_client(
        config.provider,
        model=config.provider.model_extract,
        logger=logger,
        record_path=record_path,
        payload_record_path=payload_record_path,
        mock_mode=mock_mode,
        mock_payloads=mock_payloads,
    )
    helper_client = _build_llm_client(
        config.provider,
        model=config.provider.model_query_helper,
        logger=logger,
        record_path=record_path,
        payload_record_path=payload_record_path,
        mock_mode=mock_mode,
        mock_payloads=mock_payloads,
    )
    embedding_client = _build_embedding_client(
        config.provider.base_url,
        config.provider.api_key,
        config.retrieval.embedding_backend,
        config.retrieval.embedding_model,
    )
    reranker_client = None
    if config.retrieval.use_reranker:
        reranker_client = _build_embedding_client(
            config.provider.base_url,
            config.provider.api_key,
            config.retrieval.reranker_backend,
            config.retrieval.reranker_model,
        )

    rows_data = [dict(row) for row in store.fetch_rows()]
    examples = select_examples(
        table.dataframe,
        [spec.column_name for spec in schema_specs],
        config.extraction.examples_per_col,
    )

    context = RunContext(
        config=config,
        run_paths=run_paths,
        store=store,
        table=table,
        schema_specs=schema_specs,
        grouped=grouped,
        lock_map=lock_map,
        rows_data=rows_data,
        assigned_rows={},
        header_client=header_client,
        match_client=match_client,
        extract_client=extract_client,
        helper_client=helper_client,
        embedding_client=embedding_client,
        reranker_client=reranker_client,
        retrieval_config=_build_retrieval_config(config),
        examples=examples,
        logger=logger,
        error_path=error_path,
        prompt_versions=load_prompt_versions(Path("paper_table_agent/prompts")),
        audit_targets=audit_targets,
        audit_stats=audit_stats,
    )
    return context, pdfs


def _build_llm_client(
    provider: Any,
    *,
    model: str,
    logger: Any,
    record_path: Path | None,
    payload_record_path: Path | None,
    mock_mode: bool,
    mock_payloads: dict[str, Any] | None,
) -> LlmClient:
    return LlmClient(
        LlmConfig(
            mode=provider.mode,
            base_url=provider.base_url,
            api_key=provider.api_key,
            model=model,
            timeout_s=provider.timeout_s,
            read_timeout_s=provider.read_timeout_s,
            max_prompt_chars=provider.max_prompt_chars,
            max_prompt_tokens=provider.max_prompt_tokens,
            ctx_window_tokens_override=provider.ctx_window_tokens_override,
            mock_mode=mock_mode,
            mock_payloads=mock_payloads,
            guided_json_mode=provider.guided_json_mode,
            record_path=record_path,
            payload_record_path=payload_record_path,
            llm_debug=provider.llm_debug,
            logger=logger,
            measure_prompt_tokens=provider.measure_prompt_tokens,
        )
    )


def _record_llm_request(store: Store, stage: str, client: LlmClient) -> None:
    if not client.last_request_log:
        return
    store.record_event(
        "info",
        "llm_request_meta",
        {"stage": stage, "request": client.last_request_log},
    )


def _record_llm_call(store: Store, stage: str, payload: dict[str, Any] | None = None) -> None:
    event_payload = {"stage": stage}
    if payload:
        event_payload.update(payload)
    store.record_event("info", "llm_call", event_payload)


def _apply_group_override(
    grouped: dict[str, list[Any]],
    overrides: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    if not overrides:
        return grouped if grouped else {"all_columns": [spec for specs in grouped.values() for spec in specs]}
    result: dict[str, list[Any]] = {}
    spec_map = {spec.column_key or spec.column_name: spec for specs in grouped.values() for spec in specs}
    for group in overrides:
        name = group.get("name") or "ungrouped"
        columns = group.get("columns") or []
        specs = [spec_map.get(normalize_key(col) or col) for col in columns]
        specs = [spec for spec in specs if spec is not None]
        if specs:
            result[name] = specs
    if result:
        return result
    return grouped if grouped else {"all_columns": [spec for spec in spec_map.values()]}


def _build_audit_targets(
    dataframe: Any,
    schema_specs: list[Any],
    lock_map: dict[str, set[str]],
    audit_config: Any,
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    if not getattr(audit_config, "use_filled_cells_as_gold", False):
        return {}, {}
    schema_columns = [spec.column_name for spec in schema_specs]
    allowlist = {normalize_key(col) for col in (audit_config.columns_allowlist or [])}
    denylist = {normalize_key(col) for col in (audit_config.columns_denylist or [])}
    column_lookup = {normalize_key(col): col for col in schema_columns}
    allowed_columns = set(schema_columns)
    if allowlist:
        allowed_columns = {column_lookup[key] for key in allowlist if key in column_lookup}
    if denylist:
        allowed_columns = {col for col in allowed_columns if normalize_key(col) not in denylist}
    if not allowed_columns:
        return {}, {
            "enabled": True,
            "audited_cells_count": 0,
            "audited_columns_count": 0,
            "reason": "no_allowed_columns",
        }

    candidates: list[tuple[float, str, str]] = []
    total_locked = 0
    for row_id, locked_columns in lock_map.items():
        for column in locked_columns:
            total_locked += 1
            if column not in allowed_columns:
                continue
            score = _stable_sample_score(f"{row_id}::{column}")
            if audit_config.sample_rate is not None and audit_config.sample_rate < 1:
                if score > float(audit_config.sample_rate):
                    continue
            candidates.append((score, row_id, column))

    if audit_config.max_cells is not None and audit_config.max_cells > 0:
        candidates.sort(key=lambda item: item[0])
        candidates = candidates[: int(audit_config.max_cells)]
    else:
        candidates.sort(key=lambda item: (item[1], item[2]))

    audit_targets: dict[str, set[str]] = {}
    for _score, row_id, column in candidates:
        audit_targets.setdefault(row_id, set()).add(column)

    audited_columns = {column for _score, _row_id, column in candidates}
    stats = {
        "enabled": True,
        "total_locked_cells": total_locked,
        "eligible_cells": len(candidates),
        "audited_cells_count": sum(len(cols) for cols in audit_targets.values()),
        "audited_rows_count": len(audit_targets),
        "audited_columns_count": len(audited_columns),
        "sample_rate": audit_config.sample_rate,
        "max_cells": audit_config.max_cells,
        "columns_allowlist": list(allowed_columns),
        "columns_denylist": list(denylist),
    }
    return audit_targets, stats


def _stable_sample_score(key: str) -> float:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _apply_audit_flags(
    proposals: list[dict[str, Any]],
    audit_columns: set[str],
    gold_values: dict[str, str],
) -> list[dict[str, Any]]:
    if not audit_columns:
        return proposals
    for proposal in proposals:
        column = proposal.get("column")
        if column in audit_columns:
            flags = proposal.setdefault("flags", {})
            flags["proposal_kind"] = "audit"
            if column in gold_values:
                flags["audit_gold_value"] = gold_values[column]
    return proposals


def _locked_values_for_audit(context: RunContext, row_id: str, audit_columns: set[str]) -> dict[str, str]:
    if not audit_columns:
        return {}
    try:
        row_index = int(row_id)
    except (TypeError, ValueError):
        return {}
    values: dict[str, str] = {}
    for column in audit_columns:
        if column in context.table.dataframe.columns:
            value = context.table.dataframe.at[row_index, column]
            if value is not None:
                values[column] = str(value)
    return values


def _align_schema_columns(schema_specs: list[Any], table_columns: list[str]) -> None:
    column_map = {normalize_key(column): column for column in table_columns}
    for spec in schema_specs:
        raw_key = spec.column_key or spec.column_name
        key = normalize_key(raw_key)
        if key in column_map:
            spec.column_name = column_map[key]
            spec.column_key = key


def _process_pdf(context: RunContext, pdf: PdfRecord, existing_pdfs: dict[str, Any]) -> bool:
    store = context.store
    existing = existing_pdfs.get(pdf.pdf_id)
    if existing and existing["status"] == "processed":
        context.logger.info("skipping processed pdf %s", pdf.pdf_id)
        return False
    try:
        parsed = parse_pdf(pdf.path)
        parsed.pdf_id = pdf.pdf_id
        parse_source = "pymupdf"
        grobid_result = None
        if context.config.grobid.enable_grobid:
            try:
                grobid_result = extract_grobid(pdf.path, context.config.grobid)
                save_grobid(grobid_result, context.run_paths.parsed_dir, pdf.pdf_id)
                store.record_event(
                    "info",
                    "grobid_success",
                    {"pdf_id": pdf.pdf_id, "sections": len(grobid_result.sections)},
                )
            except Exception as exc:  # noqa: BLE001
                log_error(
                    context.error_path,
                    {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "grobid"},
                )
                store.record_event(
                    "warning",
                    "grobid_failed",
                    {"pdf_id": pdf.pdf_id, "error": str(exc)},
                )
        if context.config.ocr.enable_ocr and should_trigger_ocr(
            parsed.page_text,
            context.config.ocr,
        ):
            try:
                parsed.page_text = run_ocr(pdf.path, context.run_paths.ocr_dir / pdf.pdf_id)
                parse_source = "ocr"
                store.record_event(
                    "info",
                    "ocr_success",
                    {"pdf_id": pdf.pdf_id, "source": "unstructured"},
                )
            except RuntimeError as exc:
                log_error(context.error_path, {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "ocr"})
                store.record_event(
                    "warning",
                    "ocr_failed",
                    {"pdf_id": pdf.pdf_id, "error": str(exc)},
                )
        save_parsed(parsed, context.run_paths.parsed_dir)
        parse_metrics = _parse_sanity_metrics(parsed.page_text, parsed.tokens, context.config.ocr)
        parse_metrics["pdf_id"] = pdf.pdf_id
        parse_metrics["ocr_triggered"] = parse_source == "ocr"
        if getattr(parsed, "header_footer_stats", None):
            parse_metrics["header_footer"] = parsed.header_footer_stats
        store.record_event("info", "parse_sanity", parse_metrics)
        if parse_metrics.get("quality_warnings"):
            store.record_event(
                "warning",
                "parse_quality_warning",
                {
                    "pdf_id": pdf.pdf_id,
                    "warnings": parse_metrics.get("quality_warnings"),
                },
            )
        store.update_pdf_status(pdf.pdf_id, "parsed", n_pages=parsed.n_pages, parse_source=parse_source)
    except Exception as exc:  # noqa: BLE001
        log_error(context.error_path, {"pdf_id": pdf.pdf_id, "error": str(exc)})
        store.update_pdf_status(pdf.pdf_id, "failed", error=str(exc))
        return False

    sections = grobid_result.sections if grobid_result else None
    chunks = build_chunks(parsed.page_text, sections=sections, pdf_id=pdf.pdf_id)
    chunk_dicts = to_dicts(chunks)
    full_chunk_lookup = build_chunk_lookup_from_list(chunk_dicts)
    debug_tracker = DebugExtractionTracker(pdf_id=pdf.pdf_id, chunks_indexed=len(chunks))
    store.insert_retrieval_chunks(pdf.pdf_id, chunk_dicts)
    index = load_index_if_fresh(
        context.run_paths.retrieval_dir / pdf.pdf_id,
        chunks,
        context.config.retrieval.embedding_backend,
        context.config.retrieval.embedding_model,
    )
    if not index:
        try:
            index = build_index(
                chunks,
                embedding_backend=context.config.retrieval.embedding_backend,
                embedding_client=context.embedding_client,
                embedding_model=context.config.retrieval.embedding_model,
            )
        except ValueError as exc:
            _apply_embedding_fallback(context, str(exc))
            index = build_index(
                chunks,
                embedding_backend=context.config.retrieval.embedding_backend,
                embedding_client=context.embedding_client,
                embedding_model=context.config.retrieval.embedding_model,
            )
        save_index(index, context.run_paths.retrieval_dir / pdf.pdf_id)

    header_text = "\n".join(parsed.page_text[:2])
    if grobid_result:
        header_bits = [
            grobid_result.title or "",
            ", ".join(grobid_result.authors),
            grobid_result.abstract or "",
        ]
        header_text = "\n".join([header_text] + [bit for bit in header_bits if bit])
    header_text = _truncate_header_text(
        header_text,
        context.config.matching.header_max_chars,
        context.logger,
    )
    try:
        _record_llm_call(
            context.store,
            "match_header",
            {
                "pdf_id": pdf.pdf_id,
            },
        )
        header = extract_header_with_repair(
            context.header_client,
            header_text,
            str(pdf.path),
            pdf_id=pdf.pdf_id,
        )
        _record_llm_request(context.store, "match_header", context.header_client)
    except LlmJsonError as exc:
        log_error(
            context.error_path,
            {
                "pdf_id": pdf.pdf_id,
                "error": str(exc),
                "stage": "match_header",
                "response": exc.response,
                "validation_errors": exc.validation_errors,
                "repair_attempted": exc.repair_attempted,
                "http_status": exc.http_status,
                "error_substring": exc.error_substring,
                "guided_json_active": exc.guided_json_active,
            },
        )
        store.record_event(
            "error",
            "llm_json_error",
            {
                "pdf_id": pdf.pdf_id,
                "stage": "match_header",
                "error": str(exc),
                "response": exc.response,
                **_llm_error_metadata(exc),
            },
        )
        store.insert_match(
            {
                "match_id": str(uuid.uuid4()),
                "pdf_id": pdf.pdf_id,
                "row_id": None,
                "confidence": 0.0,
                "status": "unmatched",
                "evidence": [],
                "rationale": str(exc),
            }
        )
        store.update_pdf_status(pdf.pdf_id, "failed", error=str(exc))
        _finalize_debug_tracker(store, debug_tracker, context.config.output.debug_reports)
        return False
    store.insert_pdf_metadata(
        pdf.pdf_id,
        title=header.title,
        authors=header.authors,
        year=header.year,
        doi=header.doi,
        evidence=[item.model_dump(mode="json") for item in header.evidence],
        confidence=header.confidence,
    )

    candidates = shortlist_candidates(
        header,
        context.rows_data,
        context.config.matching.top_k,
        context.config.matching.year_tolerance,
    )
    store.insert_match_candidates(
        [
            {
                "pdf_id": pdf.pdf_id,
                "row_id": candidate.row_id,
                "score": candidate.score,
                "title": candidate.title,
                "authors": candidate.authors,
                "year": candidate.year,
                "rank": idx + 1,
                "source": "shortlist",
            }
            for idx, candidate in enumerate(candidates)
        ]
    )
    adjudication = deterministic_match(
        header,
        candidates,
        context.config.matching.confidence_threshold,
        context.config.matching.confidence_margin,
    )
    if adjudication is None or (
        adjudication.status in {"ambiguous", "unmatched"}
        and _should_attempt_llm_match(candidates, context.config.matching)
    ):
        if adjudication is None or adjudication.status in {"ambiguous", "unmatched"}:
            context.store.record_event(
                "info",
                "match_adjudication_attempted",
                {
                    "pdf_id": pdf.pdf_id,
                    "top_score": _top_candidate_score(candidates),
                    "margin": _top_score_margin(candidates),
                },
            )
        try:
            _record_llm_call(
                context.store,
                "match_adjudicate",
                {
                    "pdf_id": pdf.pdf_id,
                    "candidate_count": len(candidates),
                },
            )
            adjudication = adjudicate_match(context.match_client, header, candidates, pdf_id=pdf.pdf_id)
            _record_llm_request(context.store, "match_adjudicate", context.match_client)
        except LlmJsonError as exc:
            log_error(
                context.error_path,
                {
                    "pdf_id": pdf.pdf_id,
                    "error": str(exc),
                    "stage": "match_adjudicate",
                    "response": exc.response,
                    "validation_errors": exc.validation_errors,
                    "repair_attempted": exc.repair_attempted,
                    "http_status": exc.http_status,
                    "error_substring": exc.error_substring,
                    "guided_json_active": exc.guided_json_active,
                },
            )
            store.record_event(
                "error",
                "llm_json_error",
                {
                    "pdf_id": pdf.pdf_id,
                    "stage": "match_adjudicate",
                    "error": str(exc),
                    "response": exc.response,
                    **_llm_error_metadata(exc),
                },
            )
            store.insert_match(
                {
                    "match_id": str(uuid.uuid4()),
                    "pdf_id": pdf.pdf_id,
                    "row_id": None,
                    "confidence": 0.0,
                    "status": "unmatched",
                    "evidence": [item.model_dump(mode="json") for item in header.evidence],
                    "rationale": str(exc),
                }
            )
            store.update_pdf_status(pdf.pdf_id, "processed", error=str(exc))
            _finalize_debug_tracker(store, debug_tracker, context.config.output.debug_reports)
            return True
    elif adjudication is None:
        context.store.record_event(
            "info",
            "match_adjudication_skipped",
            {
                "pdf_id": pdf.pdf_id,
                "top_score": _top_candidate_score(candidates),
                "margin": _top_score_margin(candidates),
                "reason": "below_fallback_threshold",
            },
        )
        adjudication = AdjudicationResult(
            row_id=None,
            status="unmatched",
            top_candidates=[candidate.to_payload() for candidate in candidates],
            confidence=0.0,
            rationale="Below fallback threshold; LLM adjudication skipped",
            evidence=header.evidence,
        )
    elif adjudication.status == "unmatched":
        context.store.record_event(
            "info",
            "match_adjudication_skipped",
            {
                "pdf_id": pdf.pdf_id,
                "top_score": _top_candidate_score(candidates),
                "margin": _top_score_margin(candidates),
                "reason": "deterministic_unmatched",
            },
        )
    adjudication = _coerce_single_plausible(
        adjudication,
        candidates,
        context.config.matching.confidence_threshold,
        context.logger,
        store,
        pdf.pdf_id,
    )
    match_record = build_match_record(pdf.pdf_id, adjudication)
    if adjudication.row_id and adjudication.status == "matched":
        previous = context.assigned_rows.get(adjudication.row_id)
        if previous:
            if adjudication.confidence > previous["confidence"]:
                store.update_match_status(previous["match_id"], "duplicate")
                context.assigned_rows[adjudication.row_id] = {
                    "match_id": match_record["match_id"],
                    "confidence": adjudication.confidence,
                }
            else:
                match_record["status"] = "duplicate"
        else:
            context.assigned_rows[adjudication.row_id] = {
                "match_id": match_record["match_id"],
                "confidence": adjudication.confidence,
            }
    store.insert_match(match_record)
    if adjudication.top_candidates:
        store.insert_match_candidates(
            [
                {
                    "pdf_id": pdf.pdf_id,
                    "row_id": candidate.get("row_id"),
                    "score": candidate.get("score"),
                    "title": candidate.get("title"),
                    "authors": candidate.get("authors"),
                    "year": candidate.get("year"),
                    "rank": idx + 1,
                    "source": "llm",
                }
                for idx, candidate in enumerate(adjudication.top_candidates)
            ]
        )

    if not adjudication.row_id or adjudication.status != "matched":
        _finalize_debug_tracker(store, debug_tracker, context.config.output.debug_reports)
        return True

    row_context = next((row for row in context.rows_data if row["row_id"] == adjudication.row_id), {})
    locked_columns = context.lock_map.get(adjudication.row_id, set())
    audit_columns = context.audit_targets.get(adjudication.row_id, set())
    target_specs = [
        spec
        for spec in context.schema_specs
        if spec.column_name not in locked_columns or spec.column_name in audit_columns
    ]
    max_examples = min(1, context.config.extraction.examples_per_col)
    context_columns_payload = [
        {
            "col_id": idx + 1,
            "name": spec.column_name,
            "description": spec.description,
            "examples": context.examples.get(spec.column_name, [])[:max_examples],
        }
        for idx, spec in enumerate(target_specs)
    ]
    context_plan, context_payload = plan_context(
        pdf.pdf_id,
        parsed.page_text,
        context_columns_payload,
        row_context,
        context.extract_client,
        context.helper_client,
        context.config.extraction,
        context.run_paths.run_dir,
        call_recorder=lambda stage, payload: _record_llm_call(context.store, stage, payload),
    )
    context.store.record_event(
        "info",
        "context_plan",
        {
            "pdf_id": pdf.pdf_id,
            "mode": context_plan.mode,
            "included_sections": context_plan.included_sections,
            "token_estimate": context_plan.token_estimate,
            "ctx_window_tokens": context_plan.ctx_window_tokens,
            "ctx_window_chars": context_plan.ctx_window_chars,
            "ctx_window_source": context_plan.ctx_window_source,
            "ctx_window_reason": context_plan.ctx_window_reason,
            "column_batches": context_plan.column_batches,
            "memory_stats": context_plan.memory_stats,
            "context_path": str(context_plan.page_marked_text_path) if context_plan.page_marked_text_path else None,
        },
    )
    for group_name, specs in context.grouped.items():
        chunk_lookup: dict[str, str] = {}
        target_columns = [
            spec.column_name
            for spec in specs
            if spec.column_name not in locked_columns or spec.column_name in audit_columns
        ]
        if not target_columns:
            continue
        target_specs = [spec for spec in specs if spec.column_name in target_columns]
        columns_payload = []
        column_id_map: dict[int, str] = {}
        column_key_map: dict[str, str] = {}
        for idx, spec in enumerate(target_specs):
            col_id = idx + 1
            column_id_map[col_id] = spec.column_name
            column_key = spec.column_key or normalize_key(spec.column_name)
            column_key_map[column_key] = spec.column_name
            columns_payload.append(
                {
                    "col_id": col_id,
                    "name": spec.column_name,
                    "description": spec.description,
                    "examples": context.examples.get(spec.column_name, [])[:max_examples],
                }
            )
        group = GroupContext(
            name=group_name,
            columns=target_columns,
            schema={spec.column_name: spec.description for spec in target_specs},
            examples={col: context.examples.get(col, []) for col in target_columns},
            columns_payload=columns_payload,
            column_id_map=column_id_map,
            column_key_map=column_key_map,
        )
        try:
            store.record_event(
                "info",
                "extraction_invoked",
                {"pdf_id": pdf.pdf_id, "group": group_name, "columns": target_columns},
            )
            group_batches = _filter_context_batches(context_plan.column_batches, target_columns)
            if not group_batches:
                group_batches = [[column] for column in target_columns]
            column_contexts: dict[str, list[dict[str, Any]]] = {}
            for batch_columns in group_batches:
                batch_specs = [spec for spec in target_specs if spec.column_name in batch_columns]
                if not batch_specs:
                    continue
                batch_contexts = _retrieve_column_contexts(
                    index,
                    batch_specs,
                    context.retrieval_config,
                    context.helper_client,
                    context.embedding_client,
                    context.reranker_client,
                    row_context=row_context,
                    pdf_id=pdf.pdf_id,
                    row_id=adjudication.row_id,
                    examples_map=context.examples,
                    debug_tracker=debug_tracker,
                    store=context.store,
                    retrieval_cache=context.retrieval_cache,
                    batch_columns=batch_columns,
                )
                column_contexts.update(batch_contexts)
            merged_context = _merge_column_contexts(column_contexts)
            chunk_lookup = {
                str(chunk["chunk_id"]): {
                    "text": chunk.get("text"),
                    "text_raw": chunk.get("text_raw"),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                }
                for chunk in merged_context
            }
            proposals: list[dict[str, Any]] = []
            for batch_columns in group_batches:
                batch_specs = [spec for spec in target_specs if spec.column_name in batch_columns]
                batch_payloads = [
                    payload for payload in columns_payload if payload.get("name") in batch_columns
                ]
                batch_group = GroupContext(
                    name=group_name,
                    columns=batch_columns,
                    schema={spec.column_name: spec.description for spec in batch_specs},
                    examples={col: context.examples.get(col, []) for col in batch_columns},
                    columns_payload=batch_payloads,
                    column_id_map={
                        payload["col_id"]: payload.get("name")
                        for payload in batch_payloads
                        if payload.get("col_id") is not None
                    },
                    column_key_map={normalize_key(col): col for col in batch_columns},
                )
                batch_contexts = {col: column_contexts.get(col, []) for col in batch_columns}
                batch_chunks = _merge_column_contexts(batch_contexts) if context_plan.mode == "retrieval" else []
                prompt_batches = build_extract_prompt_batches(
                    context.extract_client,
                    row_context,
                    batch_group,
                    batch_chunks,
                    pdf_id=pdf.pdf_id,
                    context_mode=context_plan.mode,
                    context_payload=context_payload if context_plan.mode != "retrieval" else None,
                )
                if not prompt_batches:
                    prompt_batches = []
                batch_total = len(prompt_batches)
                for batch_idx, batch in enumerate(prompt_batches, start=1):
                    batch_columns = batch.group.columns
                    debug_tracker.record_attempts(batch_columns)
                    context.logger.info(
                        "extract_group batch %s/%s col_ids=%s",
                        batch_idx,
                        batch_total,
                        batch.col_ids,
                    )
                    context.store.record_event(
                        "info",
                        "extract_group_batch",
                        {
                            "pdf_id": pdf.pdf_id,
                            "row_id": adjudication.row_id,
                            "group": group.name,
                            "batch_idx": batch_idx,
                            "batch_total": batch_total,
                            "col_ids": batch.col_ids,
                            "columns": batch_columns,
                            "total_missing_columns": len(target_columns),
                            "batch_has_chunks": bool(batch.chunks),
                            "prompt_trimmed": batch.prompt_meta.get("prompt_trimmed"),
                            "prompt_budget_exceeded": batch.prompt_meta.get("prompt_budget_exceeded"),
                            "context_mode": context_plan.mode,
                        },
                    )
                    if batch.prompt_meta.get("prompt_trimmed"):
                        context.store.record_event(
                            "warning",
                            "prompt_trimmed",
                            {
                                "pdf_id": pdf.pdf_id,
                                "row_id": adjudication.row_id,
                                "group": group.name,
                                "trimmed_chunks": batch.prompt_meta.get("trimmed_chunks"),
                                "total_chunks": batch.prompt_meta.get("trimmed_total_chunks"),
                            },
                        )
                    _record_llm_call(
                        context.store,
                        "extract_group",
                        {
                            "pdf_id": pdf.pdf_id,
                            "row_id": adjudication.row_id,
                            "group": group.name,
                            "batch_idx": batch_idx,
                            "batch_total": batch_total,
                            "columns": batch_columns,
                            "context_mode": context_plan.mode,
                        },
                    )
                    extraction = extract_group(
                        context.extract_client,
                        row_context,
                        batch.group,
                        batch_contexts,
                        adjudication.status != "matched",
                        full_chunk_lookup=full_chunk_lookup if context_plan.mode == "retrieval" else None,
                        pdf_id=pdf.pdf_id,
                        context_mode=context_plan.mode,
                        context_payload=context_payload if context_plan.mode != "retrieval" else None,
                        page_text=parsed.page_text,
                        prompt_meta=batch.prompt_meta,
                        prompt_override=batch.prompt,
                        trimmed_chunks=batch.chunks,
                    )
                    raw_output = (context.extract_client.last_raw_response or "")[:2000]
                    prompt_version = context.prompt_versions.get("extract_column.md")
                    for proposal in extraction.proposals:
                        context.store.insert_extraction_attempt(
                            {
                                "pdf_id": pdf.pdf_id,
                                "row_id": adjudication.row_id,
                                "column": proposal.column,
                                "stage": "extraction",
                                "prompt_version": prompt_version,
                                "prompt_hash": batch.prompt_meta.get("prompt_hash"),
                                "prompt_chars": batch.prompt_meta.get("prompt_chars"),
                                "prompt_tokens": batch.prompt_meta.get("prompt_tokens"),
                                "prompt_trimmed": batch.prompt_meta.get("prompt_trimmed"),
                                "trimmed_chunks": batch.prompt_meta.get("trimmed_chunks"),
                                "trimmed_total_chunks": batch.prompt_meta.get("trimmed_total_chunks"),
                                "llm_request": context.extract_client.last_request_log,
                                "context_chunk_ids": [chunk.get("chunk_id") for chunk in merged_context],
                                "paper_memory_used": context_plan.mode == "memory",
                                "raw_output": raw_output,
                                "parsed_output": proposal.model_dump(mode="json"),
                                "validation_errors": proposal.flags.get("evidence_validation_errors"),
                                "validation_reason": proposal.flags.get("validation_reason"),
                                "failure_reason": proposal.flags.get("failure_reason"),
                                "needs_more_evidence": proposal.flags.get("needs_more_evidence"),
                            }
                        )
                    proposals.extend(build_proposal_records(pdf.pdf_id, adjudication.row_id, extraction))
            proposals = _retry_unclear_proposals(
                proposals,
                context,
                index,
                row_context,
                group,
                target_specs,
                adjudication.status != "matched",
                full_chunk_lookup=full_chunk_lookup,
                debug_tracker=debug_tracker,
                pdf_id=pdf.pdf_id,
                context_mode=context_plan.mode,
                context_payload=context_payload if context_plan.mode != "retrieval" else None,
            )
            proposals = _apply_audit_flags(
                proposals,
                audit_columns,
                gold_values=_locked_values_for_audit(context, adjudication.row_id, audit_columns),
            )
        except LlmJsonError as exc:
            error_type = "llm_http_error" if exc.http_status else "json_parse_error"
            log_error(
                context.error_path,
                {
                    "pdf_id": pdf.pdf_id,
                    "error": str(exc),
                    "stage": "extract_group",
                    "response": exc.response,
                    "validation_errors": exc.validation_errors,
                    "repair_attempted": exc.repair_attempted,
                    "http_status": exc.http_status,
                    "error_substring": exc.error_substring,
                    "guided_json_active": exc.guided_json_active,
                },
            )
            store.record_event(
                "error",
                "llm_json_error",
                {
                    "pdf_id": pdf.pdf_id,
                    "stage": "extract_group",
                    "error": str(exc),
                    "response": exc.response,
                    **_llm_error_metadata(exc),
                },
            )
            proposals = build_error_records(
                pdf.pdf_id,
                adjudication.row_id,
                group.columns,
                str(exc),
                adjudication.status != "matched",
                error_type=error_type,
                validation_errors=exc.validation_errors,
                raw_output=exc.response,
                repair_attempted=exc.repair_attempted,
                http_status=exc.http_status,
                error_substring=exc.error_substring,
                guided_json_active=exc.guided_json_active,
                error_class=exc.error_class,
            )
        _annotate_failure_reasons(proposals, debug_tracker.retrieval_hits)
        proposals = find_evidence_for_proposals(
            proposals,
            chunk_dicts,
            parsed.page_text,
            parsed.tokens,
            str(pdf.path),
            column_chunks=column_contexts,
        )
        for proposal in proposals:
            flags = proposal.get("flags") or {}
            if flags.get("evidence_finder_used"):
                context.store.insert_extraction_attempt(
                    {
                        "pdf_id": pdf.pdf_id,
                        "row_id": proposal.get("row_id"),
                        "column": proposal.get("column"),
                        "stage": "evidence_finder",
                        "evidence_quality": flags.get("evidence_quality"),
                        "evidence": proposal.get("evidence"),
                        "highlight_status": [
                            item.get("highlight_status") for item in (proposal.get("evidence") or [])
                        ],
                        "highlight_strategy": [
                            item.get("highlight_strategy") for item in (proposal.get("evidence") or [])
                        ],
                    }
                )
        proposals = _resolve_evidence_locators(
            proposals,
            pdf.path,
            parsed.tokens,
            parse_source,
            parsed.page_text,
            chunk_dicts,
        )
        try:
            proposals = verify_proposals(context.extract_client, proposals, pdf_id=pdf.pdf_id)
        except LlmJsonError as exc:
            log_error(
                context.error_path,
                {
                    "pdf_id": pdf.pdf_id,
                    "error": str(exc),
                    "stage": "verify_proposals",
                    "response": exc.response,
                    "validation_errors": exc.validation_errors,
                    "repair_attempted": exc.repair_attempted,
                    "http_status": exc.http_status,
                    "error_substring": exc.error_substring,
                    "guided_json_active": exc.guided_json_active,
                },
            )
            store.record_event(
                "error",
                "llm_json_error",
                {
                    "pdf_id": pdf.pdf_id,
                    "stage": "verify_proposals",
                    "error": str(exc),
                    "response": exc.response,
                    **_llm_error_metadata(exc),
                },
            )
            for proposal in proposals:
                flags = proposal.setdefault("flags", {})
                flags["verification_status"] = "unclear"
                flags["verification_needs_more_evidence"] = True
                flags["verification_rationale"] = "Verification failed; see logs."
                flags.setdefault("failure_reason", "verification_failed")
                if exc.http_status is not None:
                    flags["http_status"] = exc.http_status
                if exc.error_substring:
                    flags["error_substring"] = exc.error_substring
                if exc.guided_json_active is not None:
                    flags["guided_json_active"] = exc.guided_json_active
                if exc.error_class:
                    flags["error_class"] = exc.error_class
        debug_tracker.record_proposals(proposals)
        store.insert_proposals(proposals)

        if context.config.verify_mode:
            locked_values = {
                col: str(context.table.dataframe.at[int(adjudication.row_id), col])
                for col in locked_columns
                if col in context.table.dataframe.columns
            }
            if locked_values:
                try:
                    verify_results = verify_cells(
                        context.extract_client,
                        row_context,
                        locked_values,
                        merged_context,
                        pdf_id=pdf.pdf_id,
                    )
                    verify_records = build_verify_records(
                        pdf.pdf_id,
                        adjudication.row_id,
                        verify_results,
                        locked_values,
                        full_chunk_lookup,
                    )
                    _annotate_failure_reasons(verify_records, debug_tracker.retrieval_hits)
                    debug_tracker.record_proposals(verify_records)
                    store.insert_proposals(verify_records)
                except LlmJsonError as exc:
                    log_error(
                        context.error_path,
                        {
                            "pdf_id": pdf.pdf_id,
                            "error": str(exc),
                            "stage": "verify_cells",
                            "response": exc.response,
                            "validation_errors": exc.validation_errors,
                            "repair_attempted": exc.repair_attempted,
                            "http_status": exc.http_status,
                            "error_substring": exc.error_substring,
                            "guided_json_active": exc.guided_json_active,
                        },
                    )
                    store.record_event(
                        "error",
                        "llm_json_error",
                        {
                            "pdf_id": pdf.pdf_id,
                            "stage": "verify_cells",
                            "error": str(exc),
                            "response": exc.response,
                            **_llm_error_metadata(exc),
                        },
                    )

    include_debug = context.config.output.debug_reports or debug_tracker.proposal_counts["value_present"] == 0
    _finalize_debug_tracker(store, debug_tracker, include_debug)
    store.update_pdf_status(pdf.pdf_id, "processed")
    return True


def _truncate_header_text(text: str, limit: int, logger: Any) -> str:
    if limit <= 0:
        return text
    if len(text) <= limit:
        return text
    logger.info("truncating header text from %s to %s chars", len(text), limit)
    return text[:limit]


def _top_candidate_score(candidates: list[Any]) -> float:
    if not candidates:
        return 0.0
    return float(candidates[0].score)


def _top_score_margin(candidates: list[Any]) -> float:
    if len(candidates) < 2:
        return float(candidates[0].score) if candidates else 0.0
    return float(candidates[0].score - candidates[1].score)


def _should_attempt_llm_match(candidates: list[Any], config: Any) -> bool:
    if not candidates:
        return False
    top_score = _top_candidate_score(candidates)
    margin = _top_score_margin(candidates)
    if top_score >= config.fallback_min:
        return True
    if top_score >= config.fallback_threshold and margin >= config.fallback_margin:
        return True
    return False


def prepare_context(config: RunConfig, run_paths: RunPaths, store: Store) -> tuple[RunContext, list[PdfRecord]]:
    return _prepare_context(config, run_paths, store)


def process_pdf(context: RunContext, pdf: PdfRecord, existing_pdfs: dict[str, Any]) -> bool:
    return _process_pdf(context, pdf, existing_pdfs)


def _enumerate_pdfs(folder: Path) -> list[PdfRecord]:
    pdfs: list[PdfRecord] = []
    for path in folder.iterdir():
        if path.suffix.lower() != ".pdf":
            continue
        sha1 = compute_sha1(path)
        pdfs.append(PdfRecord(pdf_id=sha1, path=path, sha1=sha1))
    return pdfs


def _resolve_evidence_locators(
    proposals: list[dict[str, Any]],
    pdf_path: Path,
    tokens: list[dict[str, Any]],
    parse_source: str,
    page_text: list[str] | None,
    chunks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    chunk_lookup = {
        normalize_chunk_id(str(chunk.get("chunk_id") or "")): chunk
        for chunk in (chunks or [])
        if chunk.get("chunk_id")
    }
    for proposal in proposals:
        evidence_items = proposal.get("evidence") or []
        for evidence in evidence_items:
            evidence["pdf_id"] = proposal.get("pdf_id")
            _apply_anchor_id(evidence, chunk_lookup, page_text)
            _apply_source_ref(evidence, chunk_lookup)
            quote = _get_quote_text(evidence)
            page = evidence.get("page")
            locator_hint = evidence.get("locator_hint")
            if quote and not evidence.get("quote_text"):
                _set_quote_text(evidence, quote)
            if not evidence.get("source_ref"):
                if evidence.get("chunk_id"):
                    evidence["source_ref"] = f"chunk_id:{evidence.get('chunk_id')}"
                elif page:
                    evidence["source_ref"] = f"page:{page}"
            if not evidence.get("anchor_id"):
                if evidence.get("chunk_id"):
                    evidence["anchor_id"] = evidence.get("chunk_id")
                elif page:
                    evidence["anchor_id"] = f"page-{page}"
            if not quote or not page:
                if not page:
                    page = _page_from_chunk_lookup(evidence, chunk_lookup)
                    if page:
                        evidence["page"] = page
                if not page and page_text:
                    page = _find_best_page_for_quote(quote or locator_hint, page_text)
                    if page:
                        evidence["page"] = page
                if not quote or not page:
                    proposal.setdefault("flags", {})["needs_more_evidence"] = True
                    evidence["highlight_status"] = "missing_quote_or_page"
                    evidence["highlight_strategy"] = "missing"
                    continue
            if page_text and isinstance(page, int) and 0 < page <= len(page_text):
                stabilized = _stabilize_quote_for_page(quote, locator_hint, page_text, int(page))
                if stabilized:
                    quote, start_char, end_char, span_strategy = stabilized
                    if quote:
                        _set_quote_text(evidence, quote)
                    if start_char is not None:
                        evidence["quote_start"] = start_char
                    if end_char is not None:
                        evidence["quote_end"] = end_char
                    if span_strategy:
                        evidence["quote_span_strategy"] = span_strategy
            if evidence.get("rects"):
                continue
            allowed, reason = _quote_quality_floor(quote, evidence)
            if not allowed:
                evidence["rects"] = []
                evidence["highlight_status"] = "failed"
                evidence["highlight_strategy"] = "skipped_low_quality"
                evidence["highlight_rejection_reason"] = reason
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
                continue
            highlight = locate_quote(
                str(pdf_path),
                quote,
                int(page),
                locator_hint=locator_hint,
                tokens=tokens,
                allow_fuzzy=evidence.get("quote_start") is None,
            )
            rects = highlight.rects
            strategy = highlight.strategy
            match_score = highlight.match_score
            if not rects and tokens:
                salvage_quote, salvage_rect, salvage_strategy, salvage_score = salvage_quote_from_tokens(
                    quote or locator_hint or "",
                    int(page),
                    tokens,
                )
                if salvage_quote and salvage_rect:
                    _set_quote_text(evidence, salvage_quote)
                    rects = [salvage_rect]
                    strategy = salvage_strategy
                    match_score = salvage_score
            accept, rejection_reason = assess_highlight_rects(
                quote,
                rects,
                highlight.page_height,
                match_score,
            )
            evidence["highlight_match_score"] = match_score
            if not accept:
                evidence["rects"] = []
                evidence["highlight_status"] = "failed"
                evidence["highlight_strategy"] = strategy
                evidence["highlight_rejection_reason"] = rejection_reason
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
                continue
            evidence["rects"] = rects
            evidence["highlight_status"] = "highlighted" if rects else "not_found"
            evidence["highlight_strategy"] = strategy
            if not rects:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
    return proposals


def _page_from_chunk_lookup(evidence: dict[str, Any], chunk_lookup: dict[str, dict[str, Any]]) -> int | None:
    chunk_id = normalize_chunk_id(str(evidence.get("chunk_id") or ""))
    if chunk_id and chunk_id in chunk_lookup:
        page = chunk_lookup[chunk_id].get("page_start")
        return int(page) if page is not None else None
    chunk_idx = evidence.get("chunk_idx")
    if chunk_idx is not None:
        for chunk in chunk_lookup.values():
            if chunk.get("chunk_idx") == chunk_idx:
                page = chunk.get("page_start")
                return int(page) if page is not None else None
    return None


def _apply_source_ref(evidence: dict[str, Any], chunk_lookup: dict[str, dict[str, Any]]) -> None:
    source_ref = str(evidence.get("source_ref") or "").strip()
    if not source_ref:
        return
    if source_ref.startswith("page:"):
        try:
            evidence["page"] = int(source_ref.split(":", 1)[1])
        except ValueError:
            return
        return
    if source_ref.startswith("chunk_id:"):
        evidence["chunk_id"] = source_ref.split(":", 1)[1]
        return
    if source_ref.startswith("chunk:"):
        evidence["chunk_id"] = source_ref.split(":", 1)[1]
        return
    if source_ref in chunk_lookup:
        evidence["chunk_id"] = source_ref


def _get_quote_text(evidence: dict[str, Any]) -> str:
    return str(evidence.get("quote_text") or evidence.get("quote") or evidence.get("quote_raw") or "").strip()


def _set_quote_text(evidence: dict[str, Any], quote: str) -> None:
    evidence["quote"] = quote
    evidence["quote_text"] = quote


def _apply_anchor_id(
    evidence: dict[str, Any],
    chunk_lookup: dict[str, dict[str, Any]],
    page_text: list[str] | None,
) -> None:
    anchor_id = str(evidence.get("anchor_id") or "").strip()
    if not anchor_id:
        return
    if anchor_id.startswith("page-"):
        try:
            page = int(anchor_id.split("-", 1)[1])
        except ValueError:
            return
        evidence.setdefault("page", page)
        if page_text and not _get_quote_text(evidence):
            if 0 < page <= len(page_text):
                _set_quote_text(evidence, page_text[page - 1][:240])
        return
    if anchor_id in chunk_lookup:
        chunk = chunk_lookup[anchor_id]
        evidence.setdefault("chunk_id", anchor_id)
        if chunk.get("page_start") and not evidence.get("page"):
            evidence["page"] = chunk.get("page_start")


def _find_best_page_for_quote(quote: str | None, page_text: list[str]) -> int | None:
    if not quote:
        return None
    best_page = None
    best_score = 0
    for idx, text in enumerate(page_text):
        score = fuzz.partial_ratio(quote, text)
        if score > best_score:
            best_score = score
            best_page = idx + 1
    if best_score < 60:
        normalized_quote = normalize_for_matching(quote)
        if not normalized_quote:
            return None
        for idx, text in enumerate(page_text):
            if normalized_quote in normalize_for_matching(text):
                return idx + 1
        return None
    return best_page


def _quote_quality_floor(quote: str, evidence: dict[str, Any]) -> tuple[bool, str | None]:
    if not quote:
        return False, "missing_quote"
    cleaned = quote.strip()
    if len(cleaned) < 20 or len(cleaned.split()) < 5:
        return False, "quote_too_short"
    alnum = sum(1 for char in cleaned if char.isalnum())
    if alnum / max(len(cleaned), 1) < 0.3:
        return False, "quote_low_alnum"
    if _evidence_needs_numeric(evidence) and not any(char.isdigit() for char in cleaned):
        return False, "quote_missing_numeric"
    return True, None


def _stabilize_quote_for_page(
    quote: str | None,
    locator_hint: str | None,
    page_text: list[str],
    page: int,
    *,
    max_len: int = 240,
) -> tuple[str | None, int | None, int | None, str | None] | None:
    if not page_text or page <= 0 or page > len(page_text):
        return None
    text = page_text[page - 1]
    span = locate_quote_span(text, quote or "") if quote else None
    if not span and locator_hint:
        span = locate_quote_span(text, locator_hint)
    if not span:
        if quote and len(quote) > max_len:
            clipped = quote[:max_len].strip()
            return clipped, None, None, None
        return None
    start, end, strategy, _score = span
    clipped_quote, new_start, new_end = _clip_quote_span(text, start, end, max_len)
    if new_start == 0 and locator_hint and locator_hint != (quote or ""):
        alt_span = locate_quote_span(text, locator_hint)
        if alt_span:
            alt_start, alt_end, alt_strategy, _ = alt_span
            alt_quote, alt_start, alt_end = _clip_quote_span(text, alt_start, alt_end, max_len)
            if alt_start > 0:
                return alt_quote, alt_start, alt_end, alt_strategy
    return clipped_quote, new_start, new_end, strategy


def _clip_quote_span(text: str, start: int, end: int, max_len: int) -> tuple[str, int, int]:
    if end <= start:
        snippet = text[start : min(len(text), start + max_len)].strip()
        return snippet, start, min(len(text), start + len(snippet))
    if end - start <= max_len:
        snippet = text[start:end].strip()
        return snippet, start, start + len(snippet)
    new_start = start
    new_end = min(len(text), start + max_len)
    snippet = text[new_start:new_end].strip()
    return snippet, new_start, new_start + len(snippet)


def _evidence_needs_numeric(evidence: dict[str, Any]) -> bool:
    quote = str(evidence.get("quote") or "")
    if any(char.isdigit() for char in quote):
        return False
    locator_hint = str(evidence.get("locator_hint") or "").lower()
    numeric_tokens = ("percent", "%", "rate", "ratio", "dose", "mg", "ml", "kg", "count", "score")
    return any(token in locator_hint for token in numeric_tokens)


def _ensure_retrieval_backends(config: RunConfig, logger: Any, store: Store) -> None:
    if config.retrieval.embedding_backend == "lmstudio" and not config.retrieval.embedding_model:
        logger.warning("embedding backend set to lmstudio without a model; falling back to tfidf")
        store.record_event(
            "warning",
            "embedding_fallback",
            {"backend": "lmstudio", "reason": "missing_model", "fallback_mode": "bm25_only"},
        )
        config.retrieval.embedding_backend = "tfidf"
        config.retrieval.use_dense = False
        config.retrieval.use_reranker = False
    if config.retrieval.use_reranker and config.retrieval.reranker_backend == "lmstudio" and not config.retrieval.reranker_model:
        logger.warning("reranker backend set to lmstudio without a model; disabling reranker")
        store.record_event(
            "warning",
            "reranker_fallback",
            {"backend": "lmstudio", "reason": "missing_model"},
        )
        config.retrieval.use_reranker = False
        config.retrieval.reranker_backend = "tfidf"


def _run_health_checks(context: RunContext) -> dict[str, Any]:
    results: dict[str, Any] = {"status": "ok", "errors": []}
    config = context.config
    if config.provider.mode in {"stub", "mock"} or config.provider.mock_mode:
        _record_retrieval_backend(context)
        return results

    errors: list[dict[str, Any]] = []
    headers = {}
    if config.provider.api_key:
        headers["Authorization"] = f"Bearer {config.provider.api_key}"
    models_endpoint = f"{config.provider.base_url}/models"
    model_names = {
        config.provider.model_header,
        config.provider.model_match,
        config.provider.model_extract,
        config.provider.model_query_helper,
    }
    try:
        response = httpx.get(models_endpoint, headers=headers, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        available = {item.get("id") for item in data if isinstance(item, dict)}
        missing = [model for model in model_names if model and model not in available]
        if missing:
            errors.append({"type": "missing_models", "missing": missing})
    except Exception as exc:  # noqa: BLE001
        errors.append({"type": "models_endpoint_failed", "error": str(exc)})

    try:
        health_client = LlmClient(
            LlmConfig(
                mode=config.provider.mode,
                base_url=config.provider.base_url,
                api_key=config.provider.api_key,
                model=config.provider.model_header,
                timeout_s=config.provider.timeout_s,
                read_timeout_s=config.provider.read_timeout_s,
                max_prompt_chars=config.provider.max_prompt_chars,
                max_prompt_tokens=config.provider.max_prompt_tokens,
                guided_json_mode=config.provider.guided_json_mode,
                payload_record_path=(
                    config.provider.payload_record_path
                    if config.provider.record_payloads
                    else None
                ),
                llm_debug=config.provider.llm_debug,
                logger=context.logger,
            )
        )
        prompt = render_prompt("query_expand.md", query="health check")
        _record_llm_call(
            context.store,
            "health_check",
            {
                "model": config.provider.model_header,
            },
        )
        health_client.complete_json(prompt, QueryExpansionResult)
    except Exception as exc:  # noqa: BLE001
        errors.append({"type": "llm_completion_failed", "error": str(exc)})

    _probe_llm_capabilities(context)

    if config.retrieval.use_dense and config.retrieval.embedding_backend != "tfidf":
        if context.embedding_client is None:
            errors.append({"type": "embedding_client_missing"})
            _apply_embedding_fallback(context, "missing_client")
        else:
            try:
                context.embedding_client.embed_texts(["health check"])
            except Exception as exc:  # noqa: BLE001
                _apply_embedding_fallback(context, str(exc))
    if config.retrieval.use_reranker and config.retrieval.reranker_backend != "tfidf":
        if context.reranker_client is None:
            errors.append({"type": "reranker_client_missing"})
            _apply_reranker_fallback(context, "missing_client")
        else:
            try:
                context.reranker_client.embed_texts(["health check"])
            except Exception as exc:  # noqa: BLE001
                _apply_reranker_fallback(context, str(exc))

    _record_retrieval_backend(context)

    if errors:
        results["status"] = "failed"
        results["errors"] = errors
        context.store.record_event("error", "health_check_failed", results)
        context.logger.error("health check failed: %s", errors)
    else:
        context.store.record_event("info", "health_check_passed", results)
    return results


def _probe_llm_capabilities(context: RunContext) -> None:
    config = context.config
    model_map = {
        "header": ("model_header", config.provider.model_header),
        "match": ("model_match", config.provider.model_match),
        "extract": ("model_extract", config.provider.model_extract),
        "helper": ("model_query_helper", config.provider.model_query_helper),
    }
    for label, (field_name, model) in model_map.items():
        if not model:
            continue
        probe_client = _build_llm_client(
            config.provider,
            model=model,
            logger=context.logger,
            record_path=None,
            payload_record_path=(
                config.provider.payload_record_path
                if config.provider.record_payloads
                else None
            ),
            mock_mode=False,
            mock_payloads=None,
        )
        backend_probe = probe_client.probe_backend()
        if not backend_probe.get("ok", False):
            context.store.record_event(
                "warning",
                "llm_backend_incompatible",
                {"model": model, "label": label, **backend_probe},
            )
            _apply_fallback_model(context, label, field_name, backend_probe)
            continue
        try:
            results = probe_client.probe_json_capabilities(QueryExpansionResult)
        except Exception as exc:  # noqa: BLE001
            context.store.record_event(
                "warning",
                "llm_capability_probe_failed",
                {"model": model, "label": label, "error": str(exc)},
            )
            continue
        ctx_window_probe = probe_client.probe_context_window()
        cached = get_capability_cache(probe_client.config)
        payload: dict[str, Any] = {"model": model, "label": label}
        backend_caps = {
            key: cached.get(key)
            for key in (
                "supports_response_format_json_schema",
                "supports_grammar_constraints",
                "supports_regex_patterns",
            )
            if key in cached
        }
        if backend_caps:
            payload["constraints_off"] = any(value is False for value in backend_caps.values())
        if results:
            payload.update(results)
            payload["cached"] = False
        elif cached:
            payload.update(cached)
            payload["cached"] = True
        else:
            continue
        if ctx_window_probe:
            payload.update(ctx_window_probe)
        if backend_caps:
            payload.update(backend_caps)
        context.store.record_event("info", "llm_capabilities", payload)


def _apply_fallback_model(
    context: RunContext,
    label: str,
    field_name: str,
    backend_probe: dict[str, Any],
) -> None:
    provider = context.config.provider
    if not provider.fallback_enabled:
        return
    fallback_model = getattr(provider, f"fallback_{field_name}", None)
    if not fallback_model:
        return
    fallback_base_url = provider.fallback_base_url or provider.base_url
    fallback_api_key = provider.fallback_api_key or provider.api_key
    fallback_provider = provider.model_copy()
    fallback_provider.base_url = fallback_base_url
    fallback_provider.api_key = fallback_api_key
    setattr(fallback_provider, field_name, fallback_model)
    replacement = _build_llm_client(
        fallback_provider,
        model=fallback_model,
        logger=context.logger,
        record_path=provider.record_path if provider.record_requests else None,
        payload_record_path=provider.payload_record_path if provider.record_payloads else None,
        mock_mode=False,
        mock_payloads=None,
    )
    if label == "header":
        context.header_client = replacement
    elif label == "match":
        context.match_client = replacement
    elif label == "extract":
        context.extract_client = replacement
    elif label == "helper":
        context.helper_client = replacement
    context.store.record_event(
        "warning",
        "llm_fallback_applied",
        {
            "label": label,
            "fallback_model": fallback_model,
            "fallback_base_url": fallback_base_url,
            "backend_probe": backend_probe,
        },
    )


def _apply_embedding_fallback(context: RunContext, reason: str) -> None:
    context.logger.warning("embedding health check failed; falling back to tfidf: %s", reason)
    context.store.record_event(
        "warning",
        "embedding_fallback",
        {"backend": context.config.retrieval.embedding_backend, "reason": reason, "fallback_mode": "bm25_only"},
    )
    context.config.retrieval.embedding_backend = "tfidf"
    context.config.retrieval.use_dense = False
    context.config.retrieval.use_reranker = False
    context.retrieval_config.embedding_backend = "tfidf"
    context.retrieval_config.use_dense = False
    context.retrieval_config.use_reranker = False
    context.embedding_client = None
    context.reranker_client = None


def _apply_reranker_fallback(context: RunContext, reason: str) -> None:
    context.logger.warning("reranker health check failed; disabling reranker: %s", reason)
    context.store.record_event(
        "warning",
        "reranker_fallback",
        {"backend": context.config.retrieval.reranker_backend, "reason": reason},
    )
    context.config.retrieval.use_reranker = False
    context.retrieval_config.use_reranker = False
    context.reranker_client = None


def _record_retrieval_backend(context: RunContext) -> None:
    context.store.record_event(
        "info",
        "retrieval_backend",
        {
            "embedding_backend": context.config.retrieval.embedding_backend,
            "embedding_model": context.config.retrieval.embedding_model,
            "use_dense": context.config.retrieval.use_dense,
            "use_reranker": context.config.retrieval.use_reranker,
            "reranker_backend": context.config.retrieval.reranker_backend,
            "reranker_model": context.config.retrieval.reranker_model,
        },
    )


def _coerce_single_plausible(
    adjudication: Any,
    candidates: list[Any],
    threshold: float,
    logger: Any,
    store: Store,
    pdf_id: str,
) -> Any:
    plausible = [candidate for candidate in candidates if candidate.score >= threshold]
    if len(plausible) == 1 and adjudication.status in {"ambiguous", "unmatched"}:
        winner = plausible[0]
        logger.warning("coercing ambiguous match to single plausible candidate for pdf %s", pdf_id)
        store.record_event(
            "warning",
            "match_coerced_single_candidate",
            {"pdf_id": pdf_id, "row_id": winner.row_id, "score": winner.score},
        )
        return type(adjudication)(
            row_id=winner.row_id,
            status="matched",
            top_candidates=adjudication.top_candidates or [candidate.to_payload() for candidate in candidates],
            confidence=max(adjudication.confidence, winner.score),
            rationale="Single plausible candidate coerced to matched",
            evidence=adjudication.evidence,
        )
    return adjudication


def _build_retrieval_config(config: RunConfig) -> RetrievalConfig:
    retrieval = config.retrieval
    max_chunks = min(retrieval.max_context_chunks, config.extraction.max_chunks)
    if config.fast_mode:
        return RetrievalConfig(
            top_k=min(8, retrieval.top_k),
            rerank_k=min(8, retrieval.rerank_k),
            max_context_chunks=min(10, max_chunks),
            max_context_tokens=min(1200, retrieval.max_context_tokens),
            context_window=retrieval.context_window,
            include_section_chunks=retrieval.include_section_chunks,
            section_chunk_limit=retrieval.section_chunk_limit,
            summary_enabled=retrieval.summary_enabled,
            summary_max_chunks=retrieval.summary_max_chunks,
            summary_max_tokens=retrieval.summary_max_tokens,
            query_variants=0,
            use_query_expansion=False,
            use_hyde=False,
            rrf_k=retrieval.rrf_k,
            use_reranker=retrieval.use_reranker,
            use_dense=retrieval.use_dense,
            embedding_backend=retrieval.embedding_backend,
            embedding_model=retrieval.embedding_model,
            reranker_backend=retrieval.reranker_backend,
            reranker_model=retrieval.reranker_model,
        )
    if config.max_success_mode:
        return RetrievalConfig(
            top_k=max(retrieval.top_k, 24),
            rerank_k=max(retrieval.rerank_k, 24),
            max_context_chunks=min(max(retrieval.max_context_chunks, 24), config.extraction.max_chunks),
            max_context_tokens=max(retrieval.max_context_tokens, 2400),
            context_window=retrieval.context_window,
            include_section_chunks=retrieval.include_section_chunks,
            section_chunk_limit=retrieval.section_chunk_limit,
            summary_enabled=retrieval.summary_enabled,
            summary_max_chunks=retrieval.summary_max_chunks,
            summary_max_tokens=retrieval.summary_max_tokens,
            query_variants=max(retrieval.query_variants, 6),
            use_query_expansion=True,
            use_hyde=True,
            rrf_k=retrieval.rrf_k,
            use_reranker=retrieval.use_reranker,
            use_dense=retrieval.use_dense,
            embedding_backend=retrieval.embedding_backend,
            embedding_model=retrieval.embedding_model,
            reranker_backend=retrieval.reranker_backend,
            reranker_model=retrieval.reranker_model,
        )
    return RetrievalConfig(
        top_k=retrieval.top_k,
        rerank_k=retrieval.rerank_k,
        max_context_chunks=max_chunks,
        max_context_tokens=retrieval.max_context_tokens,
        context_window=retrieval.context_window,
        include_section_chunks=retrieval.include_section_chunks,
        section_chunk_limit=retrieval.section_chunk_limit,
        summary_enabled=retrieval.summary_enabled,
        summary_max_chunks=retrieval.summary_max_chunks,
        summary_max_tokens=retrieval.summary_max_tokens,
        query_variants=retrieval.query_variants,
        use_query_expansion=retrieval.use_query_expansion,
        use_hyde=retrieval.use_hyde,
        rrf_k=retrieval.rrf_k,
        use_reranker=retrieval.use_reranker,
        use_dense=retrieval.use_dense,
        embedding_backend=retrieval.embedding_backend,
        embedding_model=retrieval.embedding_model,
        reranker_backend=retrieval.reranker_backend,
        reranker_model=retrieval.reranker_model,
    )


def _format_chunks(chunks: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_pk": getattr(chunk, "chunk_pk", None),
            "chunk_idx": chunk.chunk_idx,
            "text": chunk.text,
            "text_raw": getattr(chunk, "text_raw", None),
            "text_norm": getattr(chunk, "text_norm", None),
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_type": getattr(chunk, "chunk_type", None),
            "score": chunk.score,
            "bm25_score": chunk.bm25_score,
            "dense_score": chunk.dense_score,
        }
        for chunk in chunks
    ]


def _annotate_failure_reasons(
    proposals: list[dict[str, Any]],
    retrieval_hits: dict[str, int],
) -> None:
    for proposal in proposals:
        flags = proposal.setdefault("flags", {})
        if flags.get("failure_reason"):
            continue
        status = proposal.get("status") or ""
        proposed_value = proposal.get("proposed_value")
        evidence_items = proposal.get("evidence") or []
        column = proposal.get("column") or ""
        if flags.get("error"):
            flags["failure_reason"] = flags.get("error_type", "llm_error")
            continue
        if flags.get("evidence_validation_errors"):
            flags["failure_reason"] = "evidence_validation_failed"
            continue
        if proposed_value is not None and not evidence_items:
            flags["failure_reason"] = "evidence_missing"
            continue
        if proposed_value is None and not evidence_items:
            hits = retrieval_hits.get(column, 0)
            if hits == 0:
                flags["failure_reason"] = "retrieval_no_chunks"
            elif status in {"no_evidence", "unclear", "not_found"}:
                flags["failure_reason"] = status
            else:
                flags["failure_reason"] = "no_value"


def _finalize_debug_tracker(store: Store, tracker: DebugExtractionTracker, include_debug: bool) -> None:
    payload = tracker.to_payload()
    if not include_debug:
        payload.pop("retrieval_debug", None)
    store.insert_debug_extraction(tracker.pdf_id, payload)


def _merge_column_contexts(chunks_by_column: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunks in chunks_by_column.values():
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id"))
            if chunk_id in seen:
                continue
            merged.append(chunk)
            seen.add(chunk_id)
    return merged


def _needs_retrieval_retry(context_result: Any) -> bool:
    chunks = context_result.chunks
    if not chunks:
        return True
    top_chunk = chunks[0]
    if top_chunk.score < 0.05:
        return True
    if len(top_chunk.text.split()) < 6:
        return True
    return False


def _retrieve_column_contexts(
    index: Any,
    specs: list[Any],
    retrieval_config: RetrievalConfig,
    helper_client: LlmClient,
    embedder: EmbeddingClient | None,
    reranker_embedder: EmbeddingClient | None,
    row_context: dict[str, Any] | None = None,
    pdf_id: str | None = None,
    row_id: str | None = None,
    examples_map: dict[str, list[dict[str, Any]]] | None = None,
    debug_tracker: DebugExtractionTracker | None = None,
    store: Store | None = None,
    retrieval_cache: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] | None = None,
    batch_columns: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    contexts: dict[str, list[dict[str, Any]]] = {}
    if not specs:
        return contexts
    column_names = [spec.column_name for spec in specs]
    cache_key = None
    if retrieval_cache is not None and pdf_id:
        cache_key = (pdf_id, tuple(sorted(batch_columns or column_names)))
        if cache_key in retrieval_cache:
            cached = retrieval_cache[cache_key]
            for spec in specs:
                contexts[spec.column_name] = cached
                if debug_tracker is not None:
                    debug_tracker.record_retrieval_hits(spec.column_name, len(cached))
                    debug_tracker.record_retrieval_debug(
                        spec.column_name,
                        {"cache_hit": True, "query_mode": "batch", "columns": column_names},
                    )
            return contexts

    all_metadata_only = all(_is_metadata_only(spec) for spec in specs)
    effective_config = retrieval_config
    if all_metadata_only:
        effective_config = _override_retrieval_config(retrieval_config, use_query_expansion=False, use_hyde=False)

    query = (
        _build_batch_query(specs, row_context, examples_map)
        if len(specs) > 1
        else _build_column_query(specs[0], row_context, examples_map)
    )
    context_result = retrieve_context(
        index,
        query,
        effective_config,
        helper_client=helper_client,
        embedder=embedder,
        reranker_embedder=reranker_embedder,
        call_recorder=(
            lambda stage, payload: _record_llm_call(
                store,
                stage,
                {
                    "pdf_id": pdf_id,
                    "row_id": row_id,
                    "columns": column_names,
                    "query": query,
                    **payload,
                },
            )
            if store is not None
            else None
        ),
    )
    if _needs_retrieval_retry(context_result):
        retry_query = _build_retry_query(specs, row_context, examples_map)
        context_result = retrieve_context(
            index,
            retry_query,
            effective_config,
            helper_client=helper_client,
            embedder=embedder,
            reranker_embedder=reranker_embedder,
            call_recorder=(
                lambda stage, payload: _record_llm_call(
                    store,
                    stage,
                    {
                        "pdf_id": pdf_id,
                        "row_id": row_id,
                        "columns": column_names,
                        "query": retry_query,
                        **payload,
                    },
                )
                if store is not None
                else None
            ),
        )
        if store is not None:
            store.record_event(
                "info",
                "retrieval_retry",
                {"columns": column_names, "query": retry_query},
            )
    formatted_chunks = _format_chunks(context_result.chunks)
    if retrieval_cache is not None and cache_key is not None:
        retrieval_cache[cache_key] = formatted_chunks
    for spec in specs:
        contexts[spec.column_name] = formatted_chunks
        if debug_tracker is not None:
            debug_tracker.record_retrieval_hits(spec.column_name, len(context_result.chunks))
            debug_tracker.record_retrieval_debug(
                spec.column_name,
                {
                    **context_result.debug,
                    "query_mode": "batch" if len(specs) > 1 else "column",
                    "batch_columns": column_names if len(specs) > 1 else None,
                    "metadata_only": _is_metadata_only(spec),
                },
            )
        if store is not None and pdf_id and row_id:
            store.insert_extraction_attempt(
                {
                    "pdf_id": pdf_id,
                    "row_id": row_id,
                    "column": spec.column_name,
                    "query": query,
                    "retrieval_debug": context_result.debug,
                    "retrieved_chunk_ids": [chunk.get("chunk_id") for chunk in formatted_chunks],
                }
            )
        if store is not None and context_result.debug.get("fallbacks"):
            store.record_event(
                "warning",
                "retrieval_fallback",
                {
                    "column": spec.column_name,
                    "fallbacks": context_result.debug.get("fallbacks"),
                    "backend": context_result.debug.get("backend"),
                },
            )
    return contexts


def _build_context_summary(
    context: RunContext,
    chunks: list[dict[str, Any]],
    pdf_id: str,
) -> str:
    retrieval_config = context.retrieval_config
    if not retrieval_config.summary_enabled:
        return ""
    if context.helper_client.config.mode in {"stub", "mock"} or context.helper_client.config.mock_mode:
        return ""
    summary_chunks = _select_summary_chunks(chunks, retrieval_config)
    if not summary_chunks:
        return ""
    prompt = render_prompt(
        "summarize_sections.md",
        _prompt_meta={"pdf_id": pdf_id, "prompt_name": "summarize_sections"},
        chunks=json.dumps(summary_chunks, indent=2),
    )
    try:
        _record_llm_call(
            context.store,
            "context_summary",
            {
                "pdf_id": pdf_id,
                "chunk_count": len(summary_chunks),
            },
        )
        result = context.helper_client.complete_json(prompt, ContextSummaryResult)
    except LlmJsonError as exc:
        context.store.record_event(
            "warning",
            "context_summary_failed",
            {
                "pdf_id": pdf_id,
                "error": str(exc),
                "http_status": exc.http_status,
                "error_substring": exc.error_substring,
            },
        )
        return ""
    summary = (result.summary or "").strip()
    if summary:
        context.store.record_event(
            "info",
            "context_summary_generated",
            {"pdf_id": pdf_id, "summary_chars": len(summary), "key_points": len(result.key_points)},
        )
    return summary


def _select_summary_chunks(
    chunks: list[dict[str, Any]],
    retrieval_config: RetrievalConfig,
) -> list[dict[str, Any]]:
    section_chunks = [chunk for chunk in chunks if chunk.get("chunk_type") == "section"]
    page_chunks = [chunk for chunk in chunks if chunk.get("chunk_type") == "page"]
    candidates = section_chunks or page_chunks or chunks
    selected: list[dict[str, Any]] = []
    total_tokens = 0
    for chunk in candidates:
        if len(selected) >= retrieval_config.summary_max_chunks:
            break
        text = str(chunk.get("text") or "")
        if not text.strip():
            continue
        tokens = estimate_tokens(text)
        if total_tokens + tokens > retrieval_config.summary_max_tokens:
            break
        selected.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "text": text,
            }
        )
        total_tokens += tokens
    return selected


def _build_document_anchors(
    page_text: list[str],
    extraction_config: Any,
) -> list[dict[str, Any]] | None:
    if not extraction_config.whole_text_enabled:
        return None
    anchors: list[dict[str, Any]] = []
    total_tokens = 0
    for page_idx, text in enumerate(page_text, start=1):
        if not text.strip():
            continue
        tokens = estimate_tokens(text)
        if total_tokens + tokens > extraction_config.whole_text_max_tokens:
            return None
        anchors.append(
            {
                "anchor_id": f"page-{page_idx}",
                "page": page_idx,
                "text": text,
            }
        )
        total_tokens += tokens
    return anchors


def _write_document_anchors(parsed_dir: Path, pdf_id: str, anchors: list[dict[str, Any]]) -> None:
    if not anchors:
        return
    path = parsed_dir / f"{pdf_id}_anchors.json"
    path.write_text(json.dumps(anchors, indent=2), encoding="utf-8")


def _build_paper_memory(
    context: RunContext,
    page_text: list[str],
    pdf_id: str,
) -> str:
    if not context.config.extraction.paper_memory_enabled:
        return ""
    anchors: list[dict[str, Any]] = []
    total_tokens = 0
    for page_idx, text in enumerate(page_text, start=1):
        if not text.strip():
            continue
        tokens = estimate_tokens(text)
        if total_tokens + tokens > context.config.extraction.paper_memory_max_tokens:
            break
        anchors.append({"anchor_id": f"page-{page_idx}", "page": page_idx, "text": text})
        total_tokens += tokens
    if not anchors:
        return ""
    prompt = render_prompt(
        "paper_memory.md",
        _prompt_meta={"pdf_id": pdf_id, "prompt_name": "paper_memory"},
        document_anchors=json.dumps(anchors, indent=2),
    )
    try:
        _record_llm_call(
            context.store,
            "paper_memory",
            {
                "pdf_id": pdf_id,
                "anchor_count": len(anchors),
            },
        )
        result = context.helper_client.complete_json(prompt, PaperMemoryResult)
    except LlmJsonError as exc:
        context.store.record_event(
            "warning",
            "paper_memory_failed",
            {"pdf_id": pdf_id, "error": str(exc), "error_class": exc.error_class},
        )
        return ""
    payload = {"summary": result.summary, "notes": result.notes}
    context.store.record_event(
        "info",
        "paper_memory_generated",
        {"pdf_id": pdf_id, "notes": len(result.notes)},
    )
    return json.dumps(payload, indent=2)


def _is_metadata_only(spec: Any) -> bool:
    if getattr(spec, "metadata_only", None) is True:
        return True
    in_paper = getattr(spec, "in_paper", None)
    if in_paper is False:
        return True
    source = str(getattr(spec, "source", "") or "").casefold()
    if source and any(token in source for token in ("metadata", "not in paper", "not_in_paper", "external")):
        return True
    priority = str(getattr(spec, "priority", "") or "").casefold()
    if priority and any(token in priority for token in ("metadata", "not in paper", "not_in_paper")):
        return True
    return False


def _override_retrieval_config(
    retrieval_config: RetrievalConfig,
    *,
    use_query_expansion: bool,
    use_hyde: bool,
) -> RetrievalConfig:
    return replace(
        retrieval_config,
        use_query_expansion=use_query_expansion,
        use_hyde=use_hyde,
    )


def _build_batch_query(
    specs: list[Any],
    row_context: dict[str, Any] | None,
    examples_map: dict[str, list[dict[str, Any]]] | None,
) -> str:
    row_bits = []
    if row_context:
        for key in ("title", "authors", "year"):
            value = normalize_str_for_prompt(row_context.get(key))
            if value:
                row_bits.append(value)
    parts: list[str] = []
    for spec in specs:
        examples = examples_map.get(spec.column_name, []) if examples_map else []
        example_values = [
            value
            for value in (normalize_str_for_prompt(example.get("value")) for example in examples)
            if value
        ]
        spec_bits = [
            spec.column_name,
            spec.description or "",
            f"examples: {', '.join(example_values[:2])}" if example_values else "",
        ]
        parts.append(" ".join(bit for bit in spec_bits if bit))
    if row_bits:
        parts.append(f"row: {' | '.join(row_bits)}")
    query = " ".join(part for part in parts if part).strip()
    return query[:1200].strip()


def _build_retry_query(
    specs: list[Any],
    row_context: dict[str, Any] | None,
    examples_map: dict[str, list[dict[str, Any]]] | None,
) -> str:
    retry = _build_batch_query(specs, row_context, examples_map)
    suffix = "results methods abstract conclusion"
    if suffix not in retry:
        retry = f"{retry} {suffix}".strip()
    return retry


def _build_column_query(
    spec: Any,
    row_context: dict[str, Any] | None,
    examples_map: dict[str, list[dict[str, Any]]] | None,
) -> str:
    examples = examples_map.get(spec.column_name, []) if examples_map else []
    example_values = [
        value
        for value in (normalize_str_for_prompt(example.get("value")) for example in examples)
        if value
    ]
    row_bits = []
    if row_context:
        for key in ("title", "authors", "year"):
            value = normalize_str_for_prompt(row_context.get(key))
            if value:
                row_bits.append(value)
    query_parts = [
        spec.column_name,
        spec.description or "",
        f"examples: {', '.join(example_values[:3])}" if example_values else "",
        f"row: {' | '.join(row_bits)}" if row_bits else "",
    ]
    return " ".join(part for part in query_parts if part).strip()


def _build_embedding_client(
    base_url: str,
    api_key: str | None,
    backend: str,
    model: str | None,
) -> EmbeddingClient | None:
    if backend == "tfidf":
        return None
    if backend == "stub":
        return StubEmbeddingClient()
    if backend == "hash":
        return HashEmbeddingClient()
    if backend != "lmstudio":
        raise ValueError(f"Unsupported embedding backend: {backend}")
    if not model:
        raise ValueError("Embedding model must be set for LM Studio backend.")
    return EmbeddingClient(
        EmbeddingConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
    )


def _retry_unclear_proposals(
    proposals: list[dict[str, Any]],
    context: RunContext,
    index: Any,
    row_context: dict[str, Any],
    group: GroupContext,
    specs: list[Any],
    mapping_dependent: bool,
    full_chunk_lookup: dict[str, dict[str, Any]] | None = None,
    debug_tracker: DebugExtractionTracker | None = None,
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
) -> list[dict[str, Any]]:
    if not context.config.extraction.retry_on_unclear:
        return proposals
    retry_columns = [
        proposal["column"]
        for proposal in proposals
        if proposal.get("status") in {"unclear", "no_evidence", "not_found"}
        or proposal.get("flags", {}).get("needs_more_evidence")
        or proposal.get("flags", {}).get("needs_more_context")
    ]
    retry_columns = [col for col in retry_columns if col in group.columns]
    if not retry_columns:
        return proposals
    retry_specs = [spec for spec in specs if spec.column_name in retry_columns]
    retry_group = GroupContext(
        name=group.name,
        columns=retry_columns,
        schema={spec.column_name: spec.description for spec in retry_specs},
        examples={col: context.examples.get(col, [])[:1] for col in retry_columns},
        columns_payload=[
            {
                "col_id": idx + 1,
                "name": spec.column_name,
                "description": spec.description,
                "examples": context.examples.get(spec.column_name, [])[:1],
            }
            for idx, spec in enumerate(retry_specs)
        ],
        column_id_map={idx + 1: spec.column_name for idx, spec in enumerate(retry_specs)},
        column_key_map={
            (spec.column_key or normalize_key(spec.column_name)): spec.column_name for spec in retry_specs
        },
    )
    retry_payload = dict(context.retrieval_config.__dict__)
    retry_payload["max_context_chunks"] = min(
        context.retrieval_config.max_context_chunks + context.config.extraction.retry_extra_chunks,
        context.config.extraction.max_chunks,
    )
    retry_config = RetrievalConfig(**retry_payload)
    context.store.record_event(
        "info",
        "retry_extraction",
        {"columns": retry_columns, "extra_chunks": context.config.extraction.retry_extra_chunks},
    )
    if debug_tracker is not None:
        debug_tracker.record_attempts(retry_columns)
    context.logger.info("retrying extraction for columns: %s", ", ".join(retry_columns))
    column_contexts = _retrieve_column_contexts(
        index,
        retry_specs,
        retry_config,
        context.helper_client,
        context.embedding_client,
        context.reranker_client,
        row_context=row_context,
        pdf_id=pdf_id,
        row_id=row_context.get("row_id") if row_context else None,
        examples_map=context.examples,
        debug_tracker=debug_tracker,
        store=context.store,
    )
    try:
        retry_result = extract_group(
            context.extract_client,
            row_context,
            retry_group,
            column_contexts,
            mapping_dependent,
            full_chunk_lookup=full_chunk_lookup,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
            page_text=None,
        )
    except LlmJsonError:
        return proposals
    retry_row_id = None
    if row_context:
        retry_row_id = row_context.get("row_id")
    retry_records = build_proposal_records(pdf_id or "retry", retry_row_id or "retry", retry_result)
    retry_by_column = {proposal["column"]: proposal for proposal in retry_records}
    merged: list[dict[str, Any]] = []
    for proposal in proposals:
        column = proposal["column"]
        if column in retry_by_column:
            replacement = retry_by_column[column]
            replacement["pdf_id"] = proposal["pdf_id"]
            replacement["row_id"] = proposal["row_id"]
            for evidence in replacement.get("evidence") or []:
                evidence["pdf_id"] = proposal["pdf_id"]
            merged.append(replacement)
        else:
            merged.append(proposal)
    return merged


def _load_tokens(tokens_path: Path) -> list[dict[str, Any]]:
    if not tokens_path.exists():
        return []
    tokens: list[dict[str, Any]] = []
    for line in tokens_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        tokens.append(json.loads(line))
    return tokens


def _filter_context_batches(batches: list[list[str]], columns: list[str]) -> list[list[str]]:
    if not batches:
        return []
    return [batch for batch in batches if any(column in batch for column in columns)]


def _stop_requested(run_paths: RunPaths) -> bool:
    return (run_paths.run_dir / "STOP").exists() or (run_paths.run_dir / "PAUSE").exists()


def _parse_sanity_metrics(
    page_text: list[str],
    tokens: list[dict[str, Any]],
    ocr_config: Any,
) -> dict[str, Any]:
    total_chars = sum(len(text.strip()) for text in page_text)
    total_tokens = len(tokens)
    whitespace_chars = sum(sum(1 for char in text if char.isspace()) for text in page_text)
    token_lengths = [len(token.get("text") or "") for token in tokens if token.get("text")]
    avg_token_length = sum(token_lengths) / max(len(token_lengths), 1)
    whitespace_ratio = whitespace_chars / max(sum(len(text) for text in page_text), 1)
    sparse_pages = [
        idx + 1
        for idx, text in enumerate(page_text)
        if len(text.strip()) < ocr_config.ocr_trigger_min_chars_per_page
    ]
    quality_warnings: list[str] = []
    if whitespace_ratio < ocr_config.whitespace_ratio_min:
        quality_warnings.append("low_whitespace_ratio")
    if avg_token_length > ocr_config.avg_token_length_max:
        quality_warnings.append("avg_token_length_high")
    return {
        "n_pages": len(page_text),
        "total_chars_text": total_chars,
        "total_tokens": total_tokens,
        "avg_token_length": round(avg_token_length, 2),
        "whitespace_ratio": round(whitespace_ratio, 4),
        "sparse_pages_count": len(sparse_pages),
        "sparse_pages": sparse_pages,
        "quality_warnings": quality_warnings,
    }
