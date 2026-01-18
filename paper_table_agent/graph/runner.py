from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_table_agent.config import RunConfig, RunPaths, validate_schema_columns
from paper_table_agent.graph.extraction import (
    GroupContext,
    build_error_records,
    build_proposal_records,
    build_verify_records,
    extract_group,
    verify_cells,
)
from paper_table_agent.graph.matching import (
    adjudicate_match,
    build_match_record,
    deterministic_match,
    extract_header,
    shortlist_candidates,
)
from paper_table_agent.graph.reporting import write_mapping_report
from paper_table_agent.io.examples import select_examples
from paper_table_agent.io.locks import build_locks
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.llm.client import LlmClient, LlmConfig, LlmJsonError
from paper_table_agent.pdf.highlight import locate_quote
from paper_table_agent.pdf.grobid import extract_grobid, save_grobid
from paper_table_agent.pdf.ocr import run_ocr, should_trigger_ocr
from paper_table_agent.pdf.parser import compute_sha1, parse_pdf, save_parsed
from paper_table_agent.retrieval.chunking import build_chunks
from paper_table_agent.retrieval.index import build_index, load_index_if_fresh, save_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.store.db import Store
from paper_table_agent.utils.logging import configure_logging, log_error


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
    retrieval_config: RetrievalConfig
    examples: dict[str, list[dict[str, Any]]]
    logger: Any
    error_path: Path


def run_pipeline(config: RunConfig, run_paths: RunPaths, store: Store) -> None:
    context, pdfs = _prepare_context(config, run_paths, store)
    existing_pdfs = {row["pdf_id"]: row for row in store.list_pdfs()}
    for pdf in pdfs:
        if _stop_requested(run_paths):
            context.logger.info("stop requested; ending run early")
            break
        if _process_pdf(context, pdf, existing_pdfs):
            context.logger.info("processed pdf %s", pdf.pdf_id)
    write_mapping_report(store, run_paths.exports_dir)
    (run_paths.run_dir / "COMPLETED").write_text("done", encoding="utf-8")


def _prepare_context(config: RunConfig, run_paths: RunPaths, store: Store) -> tuple[RunContext, list[PdfRecord]]:
    logger, _ = configure_logging(run_paths.logs_dir)
    error_path = run_paths.logs_dir / "errors.jsonl"

    table = load_table(config.table_path)
    schema_source = config.table_path
    if config.schema_mode == "separate" and config.schema_path:
        schema_source = config.schema_path
    schema_specs = load_schema(schema_source, config.schema_sheet_name)
    validate_schema_columns([spec.column_name for spec in schema_specs], table.dataframe.columns)
    grouped = group_columns(schema_specs)
    if config.extraction.groups:
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
            }
        )
    store.insert_rows(rows_payload)

    pdfs = _enumerate_pdfs(config.pdf_folder)
    for pdf in pdfs:
        store.insert_pdf(pdf.pdf_id, str(pdf.path), pdf.sha1)

    mock_payloads = None
    if config.provider.mock_mode and config.provider.mock_payloads_path:
        mock_payloads = json.loads(config.provider.mock_payloads_path.read_text(encoding="utf-8"))
    header_client = LlmClient(
        LlmConfig(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_header,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=config.provider.mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    match_client = LlmClient(
        LlmConfig(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_match,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=config.provider.mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    extract_client = LlmClient(
        LlmConfig(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_extract,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=config.provider.mock_mode,
            mock_payloads=mock_payloads,
        )
    )
    helper_client = LlmClient(
        LlmConfig(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_query_helper,
            max_prompt_chars=config.provider.max_prompt_chars,
            mock_mode=config.provider.mock_mode,
            mock_payloads=mock_payloads,
        )
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
        retrieval_config=_build_retrieval_config(config),
        examples=examples,
        logger=logger,
        error_path=error_path,
    )
    return context, pdfs


def _apply_group_override(
    grouped: dict[str, list[Any]],
    overrides: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    spec_map = {spec.column_name: spec for specs in grouped.values() for spec in specs}
    for group in overrides:
        name = group.get("name") or "ungrouped"
        columns = group.get("columns") or []
        specs = [spec_map[col] for col in columns if col in spec_map]
        if specs:
            result[name] = specs
    return result or grouped


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
            except Exception as exc:  # noqa: BLE001
                log_error(
                    context.error_path,
                    {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "grobid"},
                )
        if context.config.ocr.enable_ocr and should_trigger_ocr(
            parsed.page_text,
            context.config.ocr.ocr_trigger_min_chars_per_page,
        ):
            try:
                parsed.page_text = run_ocr(pdf.path, context.run_paths.ocr_dir / pdf.pdf_id)
                parse_source = "ocr"
            except RuntimeError as exc:
                log_error(context.error_path, {"pdf_id": pdf.pdf_id, "error": str(exc), "stage": "ocr"})
        save_parsed(parsed, context.run_paths.parsed_dir)
        store.update_pdf_status(pdf.pdf_id, "parsed", n_pages=parsed.n_pages, parse_source=parse_source)
    except Exception as exc:  # noqa: BLE001
        log_error(context.error_path, {"pdf_id": pdf.pdf_id, "error": str(exc)})
        store.update_pdf_status(pdf.pdf_id, "failed", error=str(exc))
        return False

    sections = grobid_result.sections if grobid_result else None
    chunks = build_chunks(parsed.page_text, sections=sections)
    index = load_index_if_fresh(
        context.run_paths.retrieval_dir / pdf.pdf_id,
        chunks,
        context.config.retrieval.embedding_backend,
    )
    if not index:
        index = build_index(chunks, embedding_backend=context.config.retrieval.embedding_backend)
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
        header = extract_header(context.header_client, header_text)
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
        return False

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
    if adjudication is None:
        try:
            adjudication = adjudicate_match(context.match_client, header, candidates)
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
            return True
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
        return True

    row_context = next((row for row in context.rows_data if row["row_id"] == adjudication.row_id), {})
    locked_columns = context.lock_map.get(adjudication.row_id, set())
    for group_name, specs in context.grouped.items():
        target_columns = [
            spec.column_name
            for spec in specs
            if spec.column_name not in locked_columns
        ]
        if not target_columns:
            continue
        target_specs = [spec for spec in specs if spec.column_name in target_columns]
        group = GroupContext(
            name=group_name,
            columns=target_columns,
            schema={spec.column_name: spec.description for spec in target_specs},
            examples={col: context.examples.get(col, []) for col in target_columns},
        )
        try:
            column_contexts = _retrieve_column_contexts(
                index,
                target_specs,
                context.retrieval_config,
                context.helper_client,
            )
            merged_context = _merge_column_contexts(column_contexts)
            extraction = extract_group(
                context.extract_client,
                row_context,
                group,
                column_contexts,
                adjudication.status != "matched",
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
            )
        proposals = _resolve_evidence_locators(
            proposals,
            pdf.path,
            context.run_paths.parsed_dir / f"{pdf.pdf_id}_tokens.jsonl",
            parse_source,
        )
        store.insert_proposals(proposals)

        if context.config.verify_mode:
            locked_values = {
                col: str(context.table.dataframe.at[int(adjudication.row_id), col])
                for col in locked_columns
                if col in context.table.dataframe.columns
            }
            if locked_values:
                try:
                    verify_results = verify_cells(context.extract_client, row_context, locked_values, merged_context)
                    verify_proposals = build_verify_records(
                        pdf.pdf_id,
                        adjudication.row_id,
                        verify_results,
                        locked_values,
                    )
                    store.insert_proposals(verify_proposals)
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

    store.update_pdf_status(pdf.pdf_id, "processed")
    return True


def _truncate_header_text(text: str, limit: int, logger: Any) -> str:
    if limit <= 0:
        return text
    if len(text) <= limit:
        return text
    logger.info("truncating header text from %s to %s chars", len(text), limit)
    return text[:limit]


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
    tokens_path: Path,
    parse_source: str,
) -> list[dict[str, Any]]:
    tokens = _load_tokens(tokens_path) if parse_source == "ocr" else []
    for proposal in proposals:
        evidence_items = proposal.get("evidence") or []
        for evidence in evidence_items:
            quote = evidence.get("quote")
            page = evidence.get("page")
            locator_hint = evidence.get("locator_hint")
            if not quote or not page:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
                continue
            highlight = locate_quote(str(pdf_path), quote, int(page), locator_hint=locator_hint, tokens=tokens)
            evidence["rects"] = highlight.rects
            if not highlight.found:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
    return proposals


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
            reranker_backend=retrieval.reranker_backend,
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
        reranker_backend=retrieval.reranker_backend,
    )


def _format_chunks(chunks: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "score": chunk.score,
            "bm25_score": chunk.bm25_score,
            "dense_score": chunk.dense_score,
        }
        for chunk in chunks
    ]


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


def _retrieve_column_contexts(
    index: Any,
    specs: list[Any],
    retrieval_config: RetrievalConfig,
    helper_client: LlmClient,
) -> dict[str, list[dict[str, Any]]]:
    contexts: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        query_parts = [spec.column_name]
        if spec.description:
            query_parts.append(spec.description)
        query = ": ".join(query_parts)
        context_result = retrieve_context(index, query, retrieval_config, helper_client=helper_client)
        contexts[spec.column_name] = _format_chunks(context_result.chunks)
    return contexts


def _retry_unclear_proposals(
    proposals: list[dict[str, Any]],
    context: RunContext,
    index: Any,
    row_context: dict[str, Any],
    group: GroupContext,
    specs: list[Any],
    mapping_dependent: bool,
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
    )
    retry_config = RetrievalConfig(
        **context.retrieval_config.__dict__,
        max_context_chunks=min(
            context.retrieval_config.max_context_chunks + context.config.extraction.retry_extra_chunks,
            context.config.extraction.max_chunks,
        ),
    )
    column_contexts = _retrieve_column_contexts(index, retry_specs, retry_config, context.helper_client)
    try:
        retry_result = extract_group(
            context.extract_client,
            row_context,
            retry_group,
            column_contexts,
            mapping_dependent,
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
