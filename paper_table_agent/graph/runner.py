from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
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
    build_verify_records,
    extract_group,
    verify_proposals,
    verify_cells,
)
from paper_table_agent.graph.evidence_finder import find_evidence_for_proposals
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
from paper_table_agent.llm.client import LlmClient, LlmConfig, LlmJsonError
from paper_table_agent.llm.models import AdjudicationResult, QueryExpansionResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.llm.embeddings import (
    EmbeddingClient,
    EmbeddingConfig,
    HashEmbeddingClient,
    StubEmbeddingClient,
)
from paper_table_agent.pdf.highlight import locate_quote
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
    header_client = LlmClient(
        LlmConfig(
            mode=config.provider.mode,
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_header,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    match_client = LlmClient(
        LlmConfig(
            mode=config.provider.mode,
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_match,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    extract_client = LlmClient(
        LlmConfig(
            mode=config.provider.mode,
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_extract,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    helper_client = LlmClient(
        LlmConfig(
            mode=config.provider.mode,
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_query_helper,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=mock_mode,
            mock_payloads=mock_payloads,
        )
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
    )
    return context, pdfs


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
    chunks = build_chunks(parsed.page_text, sections=sections)
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
        header = extract_header_with_repair(
            context.header_client,
            header_text,
            str(pdf.path),
            pdf_id=pdf.pdf_id,
        )
    except LlmJsonError as exc:
        log_error(
            context.error_path,
            {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "match_header", "response": exc.response},
        )
        store.record_event(
            "error",
            "llm_json_error",
            {"pdf_id": pdf.pdf_id, "stage": "match_header", "error": str(exc), "response": exc.response},
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
            adjudication = adjudicate_match(context.match_client, header, candidates, pdf_id=pdf.pdf_id)
        except LlmJsonError as exc:
            log_error(
                context.error_path,
                {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "match_adjudicate", "response": exc.response},
            )
            store.record_event(
                "error",
                "llm_json_error",
                {"pdf_id": pdf.pdf_id, "stage": "match_adjudicate", "error": str(exc), "response": exc.response},
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
    for group_name, specs in context.grouped.items():
        chunk_lookup: dict[str, str] = {}
        target_columns = [
            spec.column_name
            for spec in specs
            if spec.column_name not in locked_columns
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
                    "examples": context.examples.get(spec.column_name, []),
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
            debug_tracker.record_attempts(target_columns)
            column_contexts = _retrieve_column_contexts(
                index,
                target_specs,
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
            )
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
            prompt_meta: dict[str, Any] = {}
            extraction = extract_group(
                context.extract_client,
                row_context,
                group,
                column_contexts,
                adjudication.status != "matched",
                full_chunk_lookup=full_chunk_lookup,
                pdf_id=pdf.pdf_id,
                prompt_meta=prompt_meta,
            )
            raw_output = (context.extract_client.last_raw_response or "")[:2000]
            prompt_version = context.prompt_versions.get("extract_group.md")
            for proposal in extraction.proposals:
                context.store.insert_extraction_attempt(
                    {
                        "pdf_id": pdf.pdf_id,
                        "row_id": adjudication.row_id,
                        "column": proposal.column,
                        "stage": "extraction",
                        "prompt_version": prompt_version,
                        "prompt_hash": prompt_meta.get("prompt_hash"),
                        "prompt_chars": prompt_meta.get("prompt_chars"),
                        "raw_output": raw_output,
                        "parsed_output": proposal.model_dump(mode="json"),
                        "validation_errors": proposal.flags.get("evidence_validation_errors"),
                        "validation_reason": proposal.flags.get("validation_reason"),
                        "failure_reason": proposal.flags.get("failure_reason"),
                        "needs_more_evidence": proposal.flags.get("needs_more_evidence"),
                    }
                )
            proposals = build_proposal_records(pdf.pdf_id, adjudication.row_id, extraction)
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
            )
        except LlmJsonError as exc:
            log_error(
                context.error_path,
                {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "extract_group", "response": exc.response},
            )
            store.record_event(
                "error",
                "llm_json_error",
                {
                    "pdf_id": pdf.pdf_id,
                    "stage": "extract_group",
                    "error": str(exc),
                    "response": exc.response,
                },
            )
            proposals = build_error_records(
                pdf.pdf_id,
                adjudication.row_id,
                group.columns,
                str(exc),
                adjudication.status != "matched",
                error_type="llm_json_error",
                validation_errors=exc.validation_errors,
                raw_output=exc.response,
                repair_attempted=exc.repair_attempted,
            )
        _annotate_failure_reasons(proposals, debug_tracker.retrieval_hits)
        proposals = find_evidence_for_proposals(
            proposals,
            chunk_dicts,
            parsed.page_text,
            parsed.tokens,
            str(pdf.path),
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
                },
            )
            for proposal in proposals:
                flags = proposal.setdefault("flags", {})
                flags["verification_status"] = "unclear"
                flags["verification_needs_more_evidence"] = True
                flags["verification_rationale"] = "Verification failed; see logs."
                flags.setdefault("failure_reason", "verification_failed")
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
        normalize_key(str(chunk.get("chunk_id") or "")): chunk
        for chunk in (chunks or [])
        if chunk.get("chunk_id")
    }
    for proposal in proposals:
        evidence_items = proposal.get("evidence") or []
        for evidence in evidence_items:
            quote = evidence.get("quote_raw") or evidence.get("quote")
            page = evidence.get("page")
            locator_hint = evidence.get("locator_hint")
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
            if evidence.get("rects"):
                continue
            highlight = locate_quote(str(pdf_path), quote, int(page), locator_hint=locator_hint, tokens=tokens)
            evidence["rects"] = highlight.rects
            evidence["highlight_status"] = "highlighted" if highlight.found else "not_found"
            evidence["highlight_strategy"] = highlight.strategy
            if not highlight.found:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
    return proposals


def _page_from_chunk_lookup(evidence: dict[str, Any], chunk_lookup: dict[str, dict[str, Any]]) -> int | None:
    chunk_id = normalize_key(str(evidence.get("chunk_id") or ""))
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
                max_prompt_chars=config.provider.max_prompt_chars,
            )
        )
        prompt = render_prompt("query_expand.md", query="health check")
        health_client.complete_json(prompt, QueryExpansionResult)
    except Exception as exc:  # noqa: BLE001
        errors.append({"type": "llm_completion_failed", "error": str(exc)})

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
) -> dict[str, list[dict[str, Any]]]:
    contexts: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        query = _build_column_query(spec, row_context, examples_map)
        context_result = retrieve_context(
            index,
            query,
            retrieval_config,
            helper_client=helper_client,
            embedder=embedder,
            reranker_embedder=reranker_embedder,
        )
        if _needs_retrieval_retry(context_result):
            examples = examples_map.get(spec.column_name, []) if examples_map else []
            anchors = ", ".join(example.get("value") for example in examples if example.get("value"))
            retry_query = " ".join(
                part
                for part in [
                    spec.column_name,
                    spec.description,
                    f"Examples: {anchors}" if anchors else "",
                    "results methods abstract conclusion",
                ]
                if part
            )
            context_result = retrieve_context(
                index,
                retry_query,
                retrieval_config,
                helper_client=helper_client,
                embedder=embedder,
                reranker_embedder=reranker_embedder,
            )
            if store is not None:
                store.record_event(
                    "info",
                    "retrieval_retry",
                    {"column": spec.column_name, "query": retry_query},
                )
        formatted_chunks = _format_chunks(context_result.chunks)
        contexts[spec.column_name] = formatted_chunks
        if debug_tracker is not None:
            debug_tracker.record_retrieval_hits(spec.column_name, len(context_result.chunks))
            debug_tracker.record_retrieval_debug(spec.column_name, context_result.debug)
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


def _build_column_query(
    spec: Any,
    row_context: dict[str, Any] | None,
    examples_map: dict[str, list[dict[str, Any]]] | None,
) -> str:
    examples = examples_map.get(spec.column_name, []) if examples_map else []
    example_values = [example.get("value") for example in examples if example.get("value")]
    row_bits = []
    if row_context:
        for key in ("title", "authors", "year"):
            value = row_context.get(key)
            if value:
                row_bits.append(str(value))
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
) -> list[dict[str, Any]]:
    if not context.config.extraction.retry_on_unclear:
        return proposals
    retry_columns = [
        proposal["column"]
        for proposal in proposals
        if proposal.get("status") in {"unclear", "no_evidence", "not_found"}
        or proposal.get("flags", {}).get("needs_more_evidence")
    ]
    retry_columns = [col for col in retry_columns if col in group.columns]
    if not retry_columns:
        return proposals
    retry_specs = [spec for spec in specs if spec.column_name in retry_columns]
    retry_group = GroupContext(
        name=group.name,
        columns=retry_columns,
        schema={spec.column_name: spec.description for spec in retry_specs},
        examples={col: context.examples.get(col, []) for col in retry_columns},
        columns_payload=[
            {
                "col_id": idx + 1,
                "name": spec.column_name,
                "description": spec.description,
                "examples": context.examples.get(spec.column_name, []),
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
        )
    except LlmJsonError:
        return proposals
    retry_records = build_proposal_records("retry", "retry", retry_result)
    retry_by_column = {proposal["column"]: proposal for proposal in retry_records}
    merged: list[dict[str, Any]] = []
    for proposal in proposals:
        column = proposal["column"]
        if column in retry_by_column:
            replacement = retry_by_column[column]
            replacement["pdf_id"] = proposal["pdf_id"]
            replacement["row_id"] = proposal["row_id"]
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
