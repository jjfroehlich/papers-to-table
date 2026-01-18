from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_table_agent.config import RunConfig, RunPaths, validate_schema_columns
from paper_table_agent.graph.extraction import GroupContext, build_proposal_records, extract_group
from paper_table_agent.graph.matching import adjudicate_match, build_match_record, extract_header, shortlist_candidates
from paper_table_agent.graph.reporting import write_mapping_report
from paper_table_agent.io.locks import build_locks
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.llm.client import LlmClient, LlmConfig
from paper_table_agent.pdf.highlight import locate_quote
from paper_table_agent.pdf.ocr import run_ocr, should_trigger_ocr
from paper_table_agent.pdf.parser import compute_sha1, parse_pdf, save_parsed
from paper_table_agent.retrieval.chunking import build_chunks
from paper_table_agent.retrieval.index import build_index, save_index
from paper_table_agent.retrieval.retrieve import expand_with_neighbors, retrieve
from paper_table_agent.store.db import Store
from paper_table_agent.utils.logging import configure_logging, log_error


@dataclass
class PdfRecord:
    pdf_id: str
    path: Path
    sha1: str


def run_pipeline(config: RunConfig, run_paths: RunPaths, store: Store) -> None:
    logger, _ = configure_logging(run_paths.logs_dir)
    error_path = run_paths.logs_dir / "errors.jsonl"

    table = load_table(config.table_path)
    schema_specs = load_schema(config.table_path, config.schema_sheet_name)
    validate_schema_columns([spec.column_name for spec in schema_specs], table.dataframe.columns)
    grouped = group_columns(schema_specs)
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
    existing_pdfs = {row["pdf_id"]: row for row in store.list_pdfs()}
    for pdf in pdfs:
        store.insert_pdf(pdf.pdf_id, str(pdf.path), pdf.sha1)

    mock_payloads = None
    if config.provider.mock_mode and config.provider.mock_payloads_path:
        mock_payloads = json.loads(config.provider.mock_payloads_path.read_text(encoding="utf-8"))
    client = LlmClient(
        LlmConfig(
            base_url=config.provider.base_url,
            api_key=config.provider.api_key,
            model=config.provider.model_extract,
            mock_mode=config.provider.mock_mode,
            mock_payloads=mock_payloads,
        )
    )

    rows_data = [dict(row) for row in store.fetch_rows()]
    assigned_rows: dict[str, dict[str, Any]] = {}
    for pdf in pdfs:
        existing = existing_pdfs.get(pdf.pdf_id)
        if existing and existing["status"] == "processed":
            logger.info("skipping processed pdf %s", pdf.pdf_id)
            continue
        try:
            parsed = parse_pdf(pdf.path)
            parsed.pdf_id = pdf.pdf_id
            if config.ocr.enable_ocr and should_trigger_ocr(parsed.page_text, config.ocr.ocr_trigger_min_chars_per_page):
                parsed.page_text = run_ocr(pdf.path, run_paths.ocr_dir / pdf.pdf_id)
            save_parsed(parsed, run_paths.parsed_dir)
            store.update_pdf_status(pdf.pdf_id, "parsed", n_pages=parsed.n_pages)
        except Exception as exc:  # noqa: BLE001
            log_error(error_path, {"pdf_id": pdf.pdf_id, "error": str(exc)})
            store.update_pdf_status(pdf.pdf_id, "failed", error=str(exc))
            continue

        chunks = build_chunks(parsed.page_text)
        index = build_index(chunks)
        save_index(index, run_paths.retrieval_dir / pdf.pdf_id)

        header = extract_header(client, "\n".join(parsed.page_text[:2]))
        candidates = shortlist_candidates(header, rows_data, config.matching.top_k)
        adjudication = adjudicate_match(client, header, candidates)
        match_record = build_match_record(pdf.pdf_id, adjudication)
        if adjudication.row_id and adjudication.status == "matched":
            previous = assigned_rows.get(adjudication.row_id)
            if previous:
                if adjudication.confidence > previous["confidence"]:
                    store.update_match_status(previous["match_id"], "duplicate")
                    assigned_rows[adjudication.row_id] = {
                        "match_id": match_record["match_id"],
                        "confidence": adjudication.confidence,
                    }
                else:
                    match_record["status"] = "duplicate"
            else:
                assigned_rows[adjudication.row_id] = {
                    "match_id": match_record["match_id"],
                    "confidence": adjudication.confidence,
                }
        store.insert_match(match_record)

        if not adjudication.row_id:
            continue

        row_context = next((row for row in rows_data if row["row_id"] == adjudication.row_id), {})
        locked_columns = lock_map.get(adjudication.row_id, set())
        for group_name, specs in grouped.items():
            target_columns = [
                spec.column_name
                for spec in specs
                if spec.column_name not in locked_columns
            ]
            if not target_columns:
                continue
            group = GroupContext(
                name=group_name,
                columns=target_columns,
                schema={spec.column_name: spec.description for spec in specs if spec.column_name in target_columns},
            )
            query = f"{group_name}: {', '.join(group.columns)}"
            retrieved = retrieve(index, query, top_k=config.extraction.max_chunks)
            expanded = expand_with_neighbors(index, retrieved)
            chunk_payload = [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "score": chunk.score,
                }
                for chunk in expanded
            ]
            extraction = extract_group(client, row_context, group, chunk_payload, adjudication.status != "matched")
            proposals = build_proposal_records(pdf.pdf_id, adjudication.row_id, extraction)
            proposals = _resolve_evidence_locators(proposals, pdf.path)
            store.insert_proposals(proposals)

        store.update_pdf_status(pdf.pdf_id, "processed")
        logger.info("processed pdf %s", pdf.pdf_id)

    write_mapping_report(store, run_paths.exports_dir)


def _enumerate_pdfs(folder: Path) -> list[PdfRecord]:
    pdfs: list[PdfRecord] = []
    for path in folder.iterdir():
        if path.suffix.lower() != ".pdf":
            continue
        sha1 = compute_sha1(path)
        pdfs.append(PdfRecord(pdf_id=sha1, path=path, sha1=sha1))
    return pdfs


def _resolve_evidence_locators(proposals: list[dict[str, Any]], pdf_path: Path) -> list[dict[str, Any]]:
    for proposal in proposals:
        evidence_items = proposal.get("evidence") or []
        for evidence in evidence_items:
            quote = evidence.get("quote")
            page = evidence.get("page")
            if not quote or not page:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
                continue
            highlight = locate_quote(str(pdf_path), quote, int(page))
            evidence["rects"] = highlight.rects
            if not highlight.found:
                proposal.setdefault("flags", {})["needs_more_evidence"] = True
    return proposals
