#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "papers_to_table_agent_review_data.v1"
PROPOSAL_SCHEMA_VERSION = "papers_to_table_agent_proposal.v1"
EVIDENCE_SCHEMA_VERSION = "papers_to_table_agent_evidence.v1"
INTERNAL_COLUMNS = {"row_id", "row_index"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "::".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}: {exc.msg}") from exc
    return rows


def table_path_for_run(run_dir: Path) -> Path:
    candidates = [
        run_dir / "tables" / "draft_table.csv",
        run_dir / "inputs" / "seed_table.csv",
        run_dir / "inputs" / "source_table.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No table found. Expected one of tables/draft_table.csv, "
        "inputs/seed_table.csv, or inputs/source_table.csv."
    )


def normalize_schema(schema_payload: Any, table_columns: list[str]) -> list[dict[str, Any]]:
    if isinstance(schema_payload, dict):
        columns = schema_payload.get("columns", [])
        if isinstance(columns, dict):
            iterable = [{"column_name": name, **(value or {})} for name, value in columns.items()]
        elif isinstance(columns, list):
            iterable = columns
        else:
            iterable = []
    elif isinstance(schema_payload, list):
        iterable = schema_payload
    else:
        iterable = []

    normalized: list[dict[str, Any]] = []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        name = str(item.get("column_name") or item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "column_name": name,
                "description": str(item.get("description") or "").strip(),
                "format": item.get("format") or item.get("field_type") or item.get("type"),
                "guidance": item.get("guidance") or item.get("extraction_guidance"),
            }
        )

    if normalized:
        return normalized
    return [{"column_name": column, "description": "", "format": None, "guidance": None} for column in table_columns if column not in INTERNAL_COLUMNS]


def load_schema(run_dir: Path, table_columns: list[str]) -> list[dict[str, Any]]:
    path = run_dir / "inputs" / "schema.json"
    return normalize_schema(read_json(path, []), table_columns)


def load_evidence_notes(run_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(run_dir / "evidence" / "evidence_notes.json", [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        notes: list[dict[str, Any]] = []
        for key, value in payload.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("cell_key", key)
                notes.append(item)
        return notes
    return []


def row_id_for(row: dict[str, str], row_index: int) -> str:
    if row.get("row_id"):
        return str(row["row_id"]).strip()
    return stable_id("row", row_index, row_label_for(row, row_index))


def row_label_for(row: dict[str, str], row_index: int) -> str:
    for key in ("Title", "title", "Paper", "paper", "source_pdf", "PDF", "pdf"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return f"row {row_index + 1}"


def note_matches(note: dict[str, Any], *, row_id: str, row_index: int, column_name: str, row_label: str) -> bool:
    note_column = str(note.get("column_name") or note.get("column") or "").strip()
    if note_column and note_column != column_name:
        return False
    if str(note.get("row_id") or "").strip() == row_id:
        return True
    if str(note.get("row_label") or "").strip() == row_label:
        return True
    if str(note.get("row_index") or "").strip() == str(row_index):
        return True
    cell_key = str(note.get("cell_key") or "").strip()
    return cell_key in {f"{row_id}::{column_name}", f"{row_index}::{column_name}", f"{row_label}::{column_name}"}


def find_note(notes: list[dict[str, Any]], *, row_id: str, row_index: int, column_name: str, row_label: str) -> dict[str, Any]:
    for note in notes:
        if note_matches(note, row_id=row_id, row_index=row_index, column_name=column_name, row_label=row_label):
            return note
    return {}


def note_text(note: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = note.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_from_table(run_dir: Path, table_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rows, fieldnames = read_csv(table_path)
    schema = load_schema(run_dir, fieldnames)
    target_columns = [item["column_name"] for item in schema if item["column_name"] in fieldnames and item["column_name"] not in INTERNAL_COLUMNS]
    if not target_columns:
        target_columns = [column for column in fieldnames if column not in INTERNAL_COLUMNS]

    notes = load_evidence_notes(run_dir)
    run_id = run_dir.name
    generated_at = utc_now()

    review_rows: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    omitted_blank_cells = 0

    for row_index, row in enumerate(rows):
        row_id = row_id_for(row, row_index)
        row_label = row_label_for(row, row_index)
        review_rows.append(
            {
                "row_id": row_id,
                "row_index": row_index,
                "row_label": row_label,
                "values": row,
            }
        )
        for column_name in target_columns:
            value = str(row.get(column_name, "") or "").strip()
            if not value:
                omitted_blank_cells += 1
                continue
            cell_id = stable_id("cell", row_id, column_name)
            proposal_id = stable_id("prop", run_id, cell_id, value)
            note = find_note(notes, row_id=row_id, row_index=row_index, column_name=column_name, row_label=row_label)
            rationale = note_text(note, "rationale", "reasoning", "note")
            caveat = note_text(note, "caveat", "warning")
            confidence = note.get("confidence")
            needs_review = bool(note.get("needs_review", False) or caveat)
            source_pdf = note_text(note, "source_pdf", "pdf", "pdf_path")
            raw_text = note_text(note, "raw_text", "quote", "evidence")
            caption = note_text(note, "caption")
            reasoning = note_text(note, "reasoning") or rationale
            evidence_for_item: list[dict[str, Any]] = []

            if raw_text or caption or reasoning or source_pdf or note.get("page_number") is not None:
                evidence_id = stable_id("ev", proposal_id, source_pdf, note.get("page_number"), raw_text, caption, reasoning)
                source_type = str(note.get("source_type") or ("direct_quote" if raw_text else "inferred_reasoning"))
                pdf_id = str(note.get("pdf_id") or (stable_id("pdf", source_pdf) if source_pdf else ""))
                evidence_record = {
                    "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                    "evidence_id": evidence_id,
                    "proposal_id": proposal_id,
                    "run_id": run_id,
                    "row_id": row_id,
                    "column_name": column_name,
                    "pdf_id": pdf_id,
                    "source_pdf": source_pdf,
                    "source_type": source_type,
                    "page_number": note.get("page_number"),
                    "source_location": note.get("source_location"),
                    "raw_text": raw_text,
                    "caption": caption,
                    "reasoning": reasoning,
                    "bbox": note.get("bbox"),
                    "figure_id": note.get("figure_id"),
                    "is_primary": True,
                    "created_at": generated_at,
                }
                evidence_rows.append(evidence_record)
                evidence_for_item.append(evidence_record)
                evidence_ids = [evidence_id]
            else:
                evidence_ids = []

            proposal = {
                "proposal_schema_version": PROPOSAL_SCHEMA_VERSION,
                "proposal_id": proposal_id,
                "run_id": run_id,
                "row_id": row_id,
                "row_index": row_index,
                "row_label": row_label,
                "column_name": column_name,
                "cell_id": cell_id,
                "proposed_value": value,
                "rationale": rationale,
                "confidence": confidence,
                "needs_review": needs_review,
                "caveat": caveat,
                "source_location": note.get("source_location"),
                "evidence_ids": evidence_ids,
                "review_state": "draft_unreviewed",
                "created_at": generated_at,
                "compat": {
                    "proposal_status": "value_proposed",
                    "evidence_status": "direct_weak" if not evidence_ids else "direct_strong",
                    "review_bucket": "review",
                    "reason_codes": [],
                },
            }
            proposals.append(proposal)
            review_items.append({**proposal, "evidence": evidence_for_item})

    coverage = {
        "policy": "sparse_non_empty_values_only",
        "rows": len(rows),
        "target_columns": len(target_columns),
        "review_items": len(review_items),
        "omitted_blank_cells": omitted_blank_cells,
    }
    review_data = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "coverage": coverage,
        "columns": schema,
        "rows": review_rows,
        "items": review_items,
    }
    return review_data, proposals, evidence_rows


def load_from_proposals(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    proposals = read_jsonl(run_dir / "proposals" / "proposals.jsonl")
    evidence_rows = read_jsonl(run_dir / "evidence" / "evidence.jsonl")
    evidence_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for evidence in evidence_rows:
        evidence_by_proposal.setdefault(str(evidence.get("proposal_id")), []).append(evidence)
    items = [{**proposal, "evidence": evidence_by_proposal.get(str(proposal.get("proposal_id")), [])} for proposal in proposals]
    row_map: dict[str, dict[str, Any]] = {}
    for item in items:
        row_id = str(item.get("row_id") or "")
        if row_id and row_id not in row_map:
            row_map[row_id] = {
                "row_id": row_id,
                "row_index": item.get("row_index"),
                "row_label": item.get("row_label"),
                "values": {},
            }
    review_data = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "generated_at": utc_now(),
        "coverage": {
            "policy": "from_existing_proposals_jsonl",
            "review_items": len(items),
        },
        "columns": [],
        "rows": list(row_map.values()),
        "items": items,
    }
    return review_data, proposals, evidence_rows


def write_review_html(run_dir: Path, review_data: dict[str, Any]) -> Path:
    template_path = Path(__file__).resolve().parents[1] / "templates" / "review.html"
    template = template_path.read_text(encoding="utf-8")
    data_json = json.dumps(review_data, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("__REVIEW_DATA_JSON__", data_json)
    out_path = run_dir / "review" / "review.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def write_reports(run_dir: Path, review_data: dict[str, Any]) -> None:
    summaries_dir = run_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    coverage = review_data.get("coverage", {})
    report = [
        "# Papers-to-table agent kit run report",
        "",
        f"- Run id: `{review_data.get('run_id')}`",
        "- Mode: `human_review` package prepared",
        f"- Coverage policy: `{coverage.get('policy', 'unknown')}`",
        f"- Review items: {coverage.get('review_items', len(review_data.get('items', [])))}",
        f"- Omitted blank cells: {coverage.get('omitted_blank_cells', 'not tracked')}",
        "",
        "Values in this package are draft/unreviewed until decisions are applied.",
    ]
    (summaries_dir / "run_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    extraction_log = [
        "# Extraction log",
        "",
        "This file records high-level reproducibility metadata only; it does not contain private chain-of-thought.",
        "",
        "- Review package generated from normalized table/proposal artifacts.",
        f"- Generated at: {review_data.get('generated_at')}",
    ]
    (summaries_dir / "extraction_log.md").write_text("\n".join(extraction_log) + "\n", encoding="utf-8")
    handoff = {
        "schema_version": "papers_to_table_agent_report_handoff.v1",
        "run_id": review_data.get("run_id"),
        "status": "draft_unreviewed",
        "summary": {
            "draft_unreviewed": len(review_data.get("items", [])),
            "human_reviewed": 0,
            "auto_accepted": 0,
        },
        "items": [
            {
                "proposal_id": item.get("proposal_id"),
                "row_id": item.get("row_id"),
                "column_name": item.get("column_name"),
                "value": item.get("proposed_value"),
                "handoff_label": "draft_unreviewed",
            }
            for item in review_data.get("items", [])
        ],
    }
    write_json(summaries_dir / "report_handoff.json", handoff)


def build_review_package(run_dir: Path, *, rebuild_from_table: bool = False) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    proposal_path = run_dir / "proposals" / "proposals.jsonl"
    if proposal_path.exists() and not rebuild_from_table:
        review_data, proposals, evidence_rows = load_from_proposals(run_dir)
    else:
        review_data, proposals, evidence_rows = build_from_table(run_dir, table_path_for_run(run_dir))
        write_jsonl(run_dir / "proposals" / "proposals.jsonl", proposals)
        write_jsonl(run_dir / "evidence" / "evidence.jsonl", evidence_rows)

    write_json(run_dir / "review" / "review_data.json", review_data)
    html_path = write_review_html(run_dir, review_data)
    write_reports(run_dir, review_data)
    write_json(
        run_dir / "run.json",
        {
            "run_id": run_dir.name,
            "mode": "human_review",
            "kit": "papers-to-table-agent-kit",
            "schema_version": "papers_to_table_agent_run.v1",
            "coverage": review_data.get("coverage", {}),
            "review_data_path": "review/review_data.json",
            "review_html_path": "review/review.html",
            "generated_at": utc_now(),
        },
    )
    return {
        "run_id": run_dir.name,
        "review_items": len(review_data.get("items", [])),
        "review_data_path": str((run_dir / "review" / "review_data.json").resolve()),
        "review_html_path": str(html_path.resolve()),
        "proposals_path": str((run_dir / "proposals" / "proposals.jsonl").resolve()),
        "evidence_path": str((run_dir / "evidence" / "evidence.jsonl").resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static papers-to-table agent review package.")
    parser.add_argument("--run", required=True, help="Path to the lite run bundle directory.")
    parser.add_argument("--rebuild-from-table", action="store_true", help="Regenerate proposals/evidence from tables/draft_table.csv.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    args = parser.parse_args(argv)

    result = build_review_package(Path(args.run), rebuild_from_table=args.rebuild_from_table)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"review_data: {result['review_data_path']}")
        print(f"review_html: {result['review_html_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
