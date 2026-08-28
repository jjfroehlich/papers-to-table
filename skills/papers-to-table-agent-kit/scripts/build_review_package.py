#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_package_common import (  # noqa: E402
    MAIN_EVIDENCE_SCHEMA_VERSION,
    NORMALIZED_PROPOSAL_SCHEMA_VERSION,
    REVIEW_INPUT_SCHEMA_VERSION,
    REVIEW_PACKAGE_SCHEMA_VERSION,
    authored_evidence_kind,
    evidence_tier,
    evidence_path,
    extraction_summary_path,
    filled_table_path,
    human_review_dir,
    infer_source_type,
    is_non_empty,
    load_review_input,
    merged_evidence_semantics,
    normalized_regions,
    output_table_name,
    proposals_path,
    read_csv,
    read_json,
    resolve_input_path,
    review_index_path,
    review_package_path,
    stable_id,
    text_evidence_value,
    utc_now,
    validation_report_path,
    write_csv,
    write_json,
    write_jsonl,
)
from validate_review_package import persist_report, validate_authoring, validate_generated  # noqa: E402


INTERNAL_COLUMNS = {"row_id", "pdf_id"}
FIELD_TYPE_ALIASES = {
    "string": "text",
    "free_text": "text",
    "number": "number",
    "numeric": "number",
    "enum": "categorical",
    "category": "categorical",
    "bool": "boolean",
}
def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _review_app_dist_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "review_app"


def _vendored_pdfjs_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "pdfjs"


def _copy_pdfjs_assets(run_dir: Path) -> list[str]:
    """Copy vendored or repo-local pdfjs-dist runtime assets."""
    repo_root = _repo_root()
    candidates = [
        _vendored_pdfjs_dir(),
        repo_root / "app" / "frontend" / "node_modules" / "pdfjs-dist" / "build",
        repo_root / "app" / "frontend" / "node_modules" / "pdfjs-dist" / "legacy" / "build",
    ]
    out_dir = human_review_dir(run_dir) / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for candidate_dir in candidates:
        pdf = candidate_dir / "pdf.mjs"
        worker = candidate_dir / "pdf.worker.mjs"
        if pdf.exists() and worker.exists():
            shutil.copy2(pdf, out_dir / "pdf.mjs")
            shutil.copy2(worker, out_dir / "pdf.worker.mjs")
            copied.extend(["human_review/assets/pdf.mjs", "human_review/assets/pdf.worker.mjs"])
            break
    return copied


def _load_schema_columns(run_dir: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    schema_value = str(payload.get("schema_path") or "").strip()
    if not schema_value:
        return []
    schema_path = resolve_input_path(run_dir, schema_value)
    if not schema_path.exists():
        return []
    columns: Any
    if schema_path.suffix.lower() == ".csv":
        columns, _headers = read_csv(schema_path)
    else:
        schema_payload = read_json(schema_path)
        if not isinstance(schema_payload, dict):
            columns = schema_payload
        else:
            columns = schema_payload.get("columns", [])
        if isinstance(columns, dict):
            columns = [{"column_name": name, **(value or {})} for name, value in columns.items()]
    if not isinstance(columns, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in columns:
        if not isinstance(item, dict):
            continue
        name = str(item.get("column_name") or item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "column_name": name,
                "description": item.get("description"),
                "field_type": _normalize_field_type(item.get("field_type") or item.get("type") or item.get("format")),
                "allowed_values": _normalize_allowed_values(item.get("allowed_values")),
                "is_target": bool(item.get("is_target", True)),
            }
        )
    return normalized


def _normalize_field_type(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    return FIELD_TYPE_ALIASES.get(raw, raw if raw in {"text", "number", "categorical", "boolean"} else None)


def _normalize_allowed_values(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in value.split("|") if part.strip()]
    if not isinstance(parsed, list):
        return None
    normalized = [str(item) for item in parsed if is_non_empty(item)]
    return normalized or None


def _source_table(run_dir: Path, payload: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    path_value = str(payload.get("source_table_path") or "").strip()
    if not path_value:
        return [], []
    path = resolve_input_path(run_dir, path_value)
    if not path.exists():
        return [], []
    return read_csv(path)


def _baseline_provenance(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path_value = str(payload.get("baseline_manifest_path") or "").strip()
    if not path_value:
        return {"preexisting_human_reviewed_cells": 0, "baseline_manifest_path": None}
    path = resolve_input_path(run_dir, path_value)
    manifest = read_json(path)
    return {
        "preexisting_human_reviewed_cells": int(manifest.get("preexisting_human_reviewed_cells") or 0),
        "baseline_manifest_path": str(path),
        "original_template_path": manifest.get("original_template_path"),
        "authoritative_source_table_path": manifest.get("authoritative_source_table_path"),
        "authoritative_source_sheet": manifest.get("authoritative_source_sheet"),
        "template_only_override": bool(manifest.get("template_only_override")),
    }


def _row_label(row: dict[str, Any], row_id: str, index: int) -> str:
    values = row.get("values") if isinstance(row.get("values"), dict) else row
    for key in ("Title", "title", "Paper", "paper", "label", "pdf_id"):
        value = values.get(key) if isinstance(values, dict) else None
        if is_non_empty(value):
            return str(value).strip()
    return row_id or f"row {index + 1}"


def _normalize_pdfs(run_dir: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pdfs = payload.get("pdfs") if isinstance(payload.get("pdfs"), list) else []
    normalized: list[dict[str, Any]] = []
    for item in raw_pdfs:
        if not isinstance(item, dict):
            continue
        pdf_id = str(item.get("pdf_id") or "").strip()
        if not pdf_id:
            continue
        raw_path = str(item.get("path") or "").strip()
        source = resolve_input_path(run_dir, raw_path) if raw_path else Path("")
        normalized.append(
            {
                "pdf_id": pdf_id,
                "label": item.get("label") or item.get("title") or pdf_id,
                "path": str(source),
                "title": item.get("title"),
                "authors": item.get("authors"),
                "year": item.get("year"),
            }
        )
    return normalized


def _normalize_rows(
    payload: dict[str, Any],
    table_rows: list[dict[str, str]],
    table_fieldnames: list[str],
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    for index, item in enumerate(raw_rows):
        if not isinstance(item, dict):
            continue
        row_id = str(item.get("row_id") or "").strip()
        if not row_id:
            continue
        values = item.get("values") if isinstance(item.get("values"), dict) else {}
        row = {
            "row_id": row_id,
            "row_index": item.get("row_index", index),
            "pdf_id": item.get("pdf_id"),
            "paper_label": item.get("label") or _row_label({"values": values, **item}, row_id, index),
            "values": values,
        }
        rows.append(row)
        seen.add(row_id)

    for index, table_row in enumerate(table_rows):
        row_id = str(table_row.get("row_id") or "").strip() or stable_id("row", index, table_row)
        if row_id in seen:
            continue
        row = {
            "row_id": row_id,
            "row_index": index,
            "pdf_id": table_row.get("pdf_id"),
            "paper_label": _row_label(table_row, row_id, index),
            "values": table_row,
        }
        rows.append(row)
        seen.add(row_id)

    for proposal in proposals:
        row_id = str(proposal.get("row_id") or "").strip()
        if row_id and row_id not in seen:
            row = {
                "row_id": row_id,
                "row_index": len(rows),
                "pdf_id": proposal.get("pdf_id"),
                "paper_label": row_id,
                "values": {"row_id": row_id},
            }
            rows.append(row)
            seen.add(row_id)

    if not rows and table_fieldnames:
        rows.append({"row_id": "row_1", "row_index": 0, "pdf_id": None, "paper_label": "row_1", "values": {}})
    return rows


def _normalize_columns(
    payload: dict[str, Any],
    schema_columns: list[dict[str, Any]],
    table_fieldnames: list[str],
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    columns: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_column(column: dict[str, Any], *, is_target: bool = True) -> None:
        name = str(column.get("column_name") or column.get("name") or "").strip()
        if not name or name in seen:
            return
        seen.add(name)
        columns.append(
            {
                "column_name": name,
                "description": column.get("description"),
                "field_type": _normalize_field_type(column.get("field_type") or column.get("type") or column.get("format")),
                "allowed_values": _normalize_allowed_values(column.get("allowed_values")),
                "is_target": bool(column.get("is_target", is_target)),
            }
        )

    raw_columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
    for column in raw_columns:
        if isinstance(column, dict):
            add_column(column, is_target=True)
    for column in schema_columns:
        add_column(column, is_target=True)
    for name in table_fieldnames:
        add_column({"column_name": name, "is_target": name not in INTERNAL_COLUMNS}, is_target=name not in INTERNAL_COLUMNS)
    for proposal in proposals:
        add_column({"column_name": proposal.get("column_name"), "is_target": True}, is_target=True)
    return columns


def _row_pdf_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {str(row.get("row_id")): str(row.get("pdf_id") or "") for row in rows if row.get("pdf_id")}


def _normalize_evidence(
    run_id: str,
    proposal_id: str,
    proposal: dict[str, Any],
    evidence_items: list[Any],
    inherited_pdf_id: str | None,
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    tiers: list[dict[str, Any]] = []
    for index, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            continue
        tier = evidence_tier(item, inherited_pdf_id=inherited_pdf_id)
        tiers.append(tier)
        pdf_id = str(item.get("pdf_id") or inherited_pdf_id or "").strip()
        page_number = _page_number(item.get("page_number"))
        exact_regions = normalized_regions(item.get("exact_highlight_regions"), default_page=page_number)
        approximate_regions = normalized_regions(
            item.get("approximate_highlight_regions") or item.get("bbox"),
            default_page=page_number,
        )
        text_value = text_evidence_value(item)
        source_type = infer_source_type(item)
        authored_kind = authored_evidence_kind(item)
        evidence_id = str(item.get("evidence_id") or "").strip() or stable_id(
            "ev",
            proposal_id,
            index,
            pdf_id,
            page_number,
            text_value,
            item.get("reasoning"),
        )
        evidence = {
            "evidence_schema_version": MAIN_EVIDENCE_SCHEMA_VERSION,
            "evidence_id": evidence_id,
            "run_id": run_id,
            "proposal_id": proposal_id,
            "pdf_id": pdf_id,
            "source_type": source_type,
            "source_type_inferred": not is_non_empty(item.get("source_type")),
            "authored_evidence_kind": authored_kind,
            "quote_text": item.get("quote_text") or item.get("table_text") or item.get("evidence_text") or item.get("caption_text"),
            "table_text": item.get("table_text"),
            "evidence_text": item.get("evidence_text"),
            "page_number": page_number,
            "source_location": item.get("source_location"),
            "exact_highlight_regions": exact_regions or None,
            "approximate_highlight_regions": approximate_regions or None,
            "figure_ref": item.get("figure_ref"),
            "caption_text": item.get("caption_text"),
            "crop_path": item.get("crop_path"),
            "full_page_path": item.get("full_page_path"),
            "anchor_confidence": item.get("anchor_confidence"),
            "evidence_rank": int(item.get("evidence_rank") or index + 1),
            "reasoning": item.get("reasoning"),
            "is_primary": index == 0,
            "evidence_tier": tier["tier"],
            "evidence_tier_label": tier["label"],
            "evidence_status": tier["evidence_status"],
            "review_bucket": tier["review_bucket"],
            "reason_codes": tier["reason_codes"],
            "created_at": item.get("created_at") or generated_at,
        }
        normalized.append(evidence)
    normalized.sort(key=lambda row: int(row.get("evidence_rank") or 9999))
    for index, evidence in enumerate(normalized):
        evidence["is_primary"] = index == 0
    return normalized, tiers


def _proposal_rationale(proposal: dict[str, Any], evidence_items: list[dict[str, Any]]) -> str | None:
    for value in (proposal.get("rationale"), proposal.get("reasoning")):
        if is_non_empty(value):
            return str(value).strip()
    for evidence in evidence_items:
        reasoning = evidence.get("reasoning")
        if is_non_empty(reasoning):
            return str(reasoning).strip()
    return None


def _page_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _normalize_proposals(
    run_id: str,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    table_rows: list[dict[str, str]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
    row_pdf = _row_pdf_lookup(rows)
    column_defs = {item["column_name"]: item for item in columns}
    existing_values: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get("row_id") or "").strip()
        if row_id:
            existing_values[row_id] = dict(row.get("values") if isinstance(row.get("values"), dict) else {})
    for table_index, table_row in enumerate(table_rows):
        row_id = str(table_row.get("row_id") or "").strip() or stable_id("row", table_index, table_row)
        existing_values.setdefault(row_id, {}).update(table_row)
    extraction_mode = str(payload.get("extraction_mode") or "fill_blanks")
    proposals: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for index, item in enumerate(raw_proposals):
        if not isinstance(item, dict):
            continue
        row_id = str(item.get("row_id") or "").strip()
        column_name = str(item.get("column_name") or "").strip()
        proposed_value = item.get("proposed_value")
        proposal_status = str(item.get("proposal_status") or "").strip()
        if not proposal_status:
            if is_non_empty(proposed_value):
                proposal_status = "value_proposed"
            elif bool(item.get("no_data")):
                proposal_status = "no_data"
            else:
                proposal_status = "unresolved"
        cell_id = str(item.get("cell_id") or "").strip() or stable_id("cell", row_id, column_name)
        proposal_id = str(item.get("proposal_id") or "").strip() or stable_id(
            "prop",
            run_id,
            row_id,
            column_name,
            proposed_value,
            index,
        )
        inherited_pdf_id = str(item.get("pdf_id") or row_pdf.get(row_id, "")).strip() or None
        normalized_evidence, tiers = _normalize_evidence(
            run_id,
            proposal_id,
            item,
            item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            inherited_pdf_id,
            generated_at,
        )
        evidence.extend(normalized_evidence)
        semantics = merged_evidence_semantics(tiers, proposal_status)
        explicit_reason_codes = item.get("reason_codes") if isinstance(item.get("reason_codes"), list) else []
        reason_codes: list[str] = []
        for code in [*semantics["reason_codes"], *explicit_reason_codes]:
            code_str = str(code)
            if code_str and code_str not in reason_codes:
                reason_codes.append(code_str)
        evidence_ids = [row["evidence_id"] for row in normalized_evidence]
        proposal_pdf_id = inherited_pdf_id or (normalized_evidence[0]["pdf_id"] if normalized_evidence else "")
        warning_flags = list(item.get("warning_flags") if isinstance(item.get("warning_flags"), list) else [])
        if semantics["evidence_status"] in {"direct_weak", "inferred_weak", "no_evidence"} and "weak_evidence" not in warning_flags:
            warning_flags.append("weak_evidence")
        column_def = column_defs.get(column_name, {})
        existing_value = existing_values.get(row_id, {}).get(column_name)
        is_verify_mode = extraction_mode == "fill_and_verify" and is_non_empty(existing_value)
        derivation_codes = set(explicit_reason_codes)
        evidence_status = item.get("evidence_status") or semantics["evidence_status"]
        review_bucket = item.get("review_bucket") or semantics["review_bucket"]
        numeric_value_form = item.get("numeric_value_form")
        if "calculation" in derivation_codes:
            if "calculation" not in reason_codes:
                reason_codes.append("calculation")
            if semantics["evidence_status"] == "direct_strong":
                evidence_status = "inferred_strong"
            else:
                evidence_status = "inferred_weak"
                review_bucket = "attention"
        if "figure_estimate" in derivation_codes:
            numeric_value_form = "approximate"
            evidence_status = "direct_weak"
            review_bucket = "attention"
            if "figure_estimate" not in warning_flags:
                warning_flags.append("figure_estimate")
        if "protocol_inference" in derivation_codes:
            evidence_status = "inferred_weak"
            review_bucket = "attention"
            if "protocol_inference" not in warning_flags:
                warning_flags.append("protocol_inference")
        if "absence_inference" in derivation_codes:
            evidence_status = "inferred_weak"
            review_bucket = "attention"
            if "absence_inference" not in warning_flags:
                warning_flags.append("absence_inference")
        proposals.append(
            {
                "proposal_schema_version": NORMALIZED_PROPOSAL_SCHEMA_VERSION,
                "proposal_id": proposal_id,
                "run_id": run_id,
                "pdf_id": proposal_pdf_id,
                "row_id": row_id,
                "column_name": column_name,
                "cell_id": cell_id,
                "proposal_status": proposal_status,
                "evidence_status": evidence_status,
                "review_bucket": review_bucket,
                "reason_codes": reason_codes,
                "proposed_value": proposed_value,
                "rationale": _proposal_rationale(item, normalized_evidence),
                "calculation": item.get("calculation"),
                "numeric_value_form": numeric_value_form,
                "is_verify_mode": is_verify_mode,
                "existing_value": existing_value if is_verify_mode else None,
                "primary_evidence_id": evidence_ids[0] if evidence_ids else None,
                "ordered_supporting_evidence_ids": evidence_ids[1:],
                "evidence_ids": evidence_ids,
                "warning_flags": warning_flags,
                "field_type": column_def.get("field_type"),
                "allowed_values": column_def.get("allowed_values"),
                "evidence_tiers": [tier["tier"] for tier in tiers],
                "latest_decision": None,
                "is_figure_derived": any(row.get("figure_ref") for row in normalized_evidence),
                "is_fallback_evidence": any(tier["tier"] in {"B", "C"} for tier in tiers),
                "created_at": item.get("created_at") or generated_at,
            }
        )
    return proposals, evidence


def _build_review_package(
    run_id: str,
    generated_at: str,
    payload: dict[str, Any],
    output_name: str,
    source_table_present: bool,
    pdfs: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    evidence_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for row in evidence:
        evidence_by_proposal.setdefault(str(row.get("proposal_id")), []).append(row)
    proposal_items: list[dict[str, Any]] = []
    for proposal in proposals:
        item = dict(proposal)
        item["evidence"] = evidence_by_proposal.get(str(proposal.get("proposal_id")), [])
        proposal_items.append(item)
    return {
        "schema_version": REVIEW_PACKAGE_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "source": {
            "review_input_schema_version": payload.get("schema_version") or REVIEW_INPUT_SCHEMA_VERSION,
            "source_table_present": source_table_present,
            "source_table_path": payload.get("source_table_path"),
            "schema_path": payload.get("schema_path"),
            "output_table_name": output_name,
            "output_table_path": payload.get("output_table_path"),
            **baseline,
        },
        "pdfs": pdfs,
        "columns": columns,
        "rows": rows,
        "proposals": proposal_items,
        "review_progress": {
            "total_proposals": len([item for item in proposals if item.get("review_bucket") != "diagnostic"]),
            "reviewed": 0,
            "pending": len([item for item in proposals if item.get("review_bucket") != "diagnostic"]),
            "accepted": 0,
            "accepted_with_edit": 0,
            "rejected": 0,
            "confirmed_no_data": 0,
        },
    }


def _draft_rows_and_fields(
    table_rows: list[dict[str, str]],
    table_fieldnames: list[str],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]]]:
    if table_rows:
        out_rows = [dict(row) for row in table_rows]
        fieldnames = list(table_fieldnames)
        row_map: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(out_rows):
            row_id = str(row.get("row_id") or "").strip() or stable_id("row", index, row)
            row.setdefault("row_id", row_id)
            row_map[row_id] = row
        return out_rows, fieldnames, row_map

    fieldnames = ["row_id", "pdf_id"]
    for column in columns:
        name = str(column.get("column_name") or "").strip()
        if name and name not in fieldnames:
            fieldnames.append(name)
    out_rows = []
    row_map = {}
    for row in rows:
        row_id = str(row.get("row_id") or "").strip()
        values = dict(row.get("values") if isinstance(row.get("values"), dict) else {})
        values.setdefault("row_id", row_id)
        values.setdefault("pdf_id", row.get("pdf_id") or "")
        for key in values:
            if key not in fieldnames:
                fieldnames.append(key)
        out_rows.append(values)
        row_map[row_id] = values
    return out_rows, fieldnames, row_map


def _write_filled_table(
    run_dir: Path,
    payload: dict[str, Any],
    table_rows: list[dict[str, str]],
    table_fieldnames: list[str],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> Path:
    out_rows, fieldnames, rows_by_id = _draft_rows_and_fields(table_rows, table_fieldnames, rows, columns)
    for proposal in proposals:
        if proposal.get("is_verify_mode"):
            continue
        if not is_non_empty(proposal.get("proposed_value")):
            continue
        row_id = str(proposal.get("row_id") or "").strip()
        if not row_id:
            continue
        if row_id not in rows_by_id:
            row = {"row_id": row_id, "pdf_id": proposal.get("pdf_id") or ""}
            rows_by_id[row_id] = row
            out_rows.append(row)
            for field in ("row_id", "pdf_id"):
                if field not in fieldnames:
                    fieldnames.append(field)
        column_name = str(proposal.get("column_name") or "").strip()
        if not column_name:
            continue
        if column_name not in fieldnames:
            fieldnames.append(column_name)
        value = proposal.get("proposed_value")
        rows_by_id[row_id][column_name] = value if is_non_empty(value) else ""

    out_path = filled_table_path(run_dir, payload)
    write_csv(out_path, out_rows, fieldnames)
    return out_path


def _copy_review_app_assets(run_dir: Path) -> list[str]:
    dist_dir = _review_app_dist_dir()
    if not (dist_dir / "index.html").exists():
        raise FileNotFoundError(
            "Missing built React review app assets. Run "
            "npm --prefix skills/papers-to-table-agent-kit/review_app run build."
        )
    copied: list[str] = []
    review_dir = human_review_dir(run_dir)
    review_dir.mkdir(parents=True, exist_ok=True)

    def make_script_file_safe(path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        if "import.meta.url" not in text:
            return
        current_script_url = (
            "((globalThis.document && globalThis.document.currentScript && globalThis.document.currentScript.src) "
            "|| globalThis.location.href)"
        )
        path.write_text(text.replace("import.meta.url", current_script_url), encoding="utf-8")

    for child in dist_dir.iterdir():
        if child.name == "index.html":
            continue
        destination = review_dir / child.name
        if child.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(child, destination)
            copied.extend(
                path.relative_to(run_dir).as_posix()
                for path in destination.rglob("*")
                if path.is_file()
            )
            for path in destination.rglob("*.js"):
                make_script_file_safe(path)
        elif child.is_file():
            shutil.copy2(child, destination)
            if destination.suffix == ".js":
                make_script_file_safe(destination)
            copied.append(destination.relative_to(run_dir).as_posix())
    return copied


def _write_review_html(run_dir: Path, package: dict[str, Any]) -> Path:
    template_path = _review_app_dist_dir() / "index.html"
    template = template_path.read_text(encoding="utf-8")
    template = template.replace('<script type="module" crossorigin src=', '<script defer src=')
    template = template.replace('<script type="module" src=', '<script defer src=')
    template = template.replace(" crossorigin", "")
    package_json = json.dumps(package, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("__REVIEW_PACKAGE_JSON__", package_json)
    out_path = review_index_path(run_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _write_extraction_summary(
    run_dir: Path,
    payload: dict[str, Any],
    *,
    run_id: str,
    generated_at: str,
    proposals: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    filled_table: Path,
    baseline: dict[str, Any],
) -> Path:
    preexisting_cells = int(baseline.get("preexisting_human_reviewed_cells") or 0)
    mixed_provenance = preexisting_cells > 0
    summary = {
        "schema_version": "papers_to_table.extraction_summary.v1",
        "run_id": run_id,
        "generated_at": generated_at,
        "filled_table_path": str(filled_table),
        "output_table_name": output_table_name(run_dir, payload),
        "output_table_path": str(filled_table),
        "proposal_count": len(proposals),
        "evidence_count": len(evidence),
        "review_status": "not_human_reviewed",
        "value_provenance": (
            "mixed_preexisting_human_reviewed_and_agent_extracted"
            if mixed_provenance
            else "agent_extracted"
        ),
        "preexisting_human_reviewed_cell_count": preexisting_cells,
        "baseline_manifest_path": baseline.get("baseline_manifest_path"),
        "notes": (
            "The filled table preserves pre-existing human-reviewed values and adds agent-extracted proposals; "
            "the new proposals have not been human-reviewed."
            if mixed_provenance
            else "The filled table is agent-extracted from proposed values and has not been human-reviewed."
        ),
    }
    path = extraction_summary_path(run_dir)
    write_json(path, summary)
    return path


def build_review_package(run_dir: Path, *, from_review_input: bool = True, with_review: bool = False) -> dict[str, Any]:
    if not from_review_input:
        raise ValueError("The rich agent kit now builds from review_input.json by default.")
    run_dir = run_dir.resolve()
    payload = load_review_input(run_dir)
    authoring_report = validate_authoring(run_dir)
    persist_report(run_dir, authoring_report)
    if not authoring_report["ok"]:
        raise ValueError("extraction/review_input.json failed authoring validation. See extraction/validation_report.json.")

    generated_at = utc_now()
    run_id = str(payload.get("run_id") or run_dir.name)
    table_rows, table_fieldnames = _source_table(run_dir, payload)
    baseline = _baseline_provenance(run_dir, payload)
    schema_columns = _load_schema_columns(run_dir, payload)
    raw_proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
    pdfs = _normalize_pdfs(run_dir, payload)
    rows = _normalize_rows(payload, table_rows, table_fieldnames, raw_proposals)
    columns = _normalize_columns(payload, schema_columns, table_fieldnames, raw_proposals)
    proposals, evidence = _normalize_proposals(run_id, payload, rows, columns, table_rows, generated_at)
    package = _build_review_package(
        run_id,
        generated_at,
        payload,
        output_table_name(run_dir, payload),
        bool(payload.get("source_table_path")),
        pdfs,
        rows,
        columns,
        proposals,
        evidence,
        baseline,
    )

    write_jsonl(proposals_path(run_dir), proposals)
    write_jsonl(evidence_path(run_dir), evidence)
    filled_path = _write_filled_table(run_dir, payload, table_rows, table_fieldnames, rows, columns, proposals)
    summary_path = _write_extraction_summary(
        run_dir,
        payload,
        run_id=run_id,
        generated_at=generated_at,
        proposals=proposals,
        evidence=evidence,
        filled_table=filled_path,
        baseline=baseline,
    )
    html_path: Path | None = None
    review_pkg_path: Path | None = None
    copied_review_app_assets: list[str] = []
    copied_assets: list[str] = []
    if with_review:
        write_json(review_package_path(run_dir), package)
        review_pkg_path = review_package_path(run_dir)
        copied_review_app_assets = _copy_review_app_assets(run_dir)
        html_path = _write_review_html(run_dir, package)
        copied_assets = _copy_pdfjs_assets(run_dir)
    generated_report = validate_generated(run_dir)
    generated_report["authoring"] = authoring_report
    if with_review:
        generated_report["copied_assets"] = copied_assets
        generated_report["copied_review_app_assets"] = copied_review_app_assets
    persist_report(run_dir, generated_report)
    if not generated_report["ok"]:
        raise ValueError("Generated extraction package failed validation. See extraction/validation_report.json.")
    return {
        "run_id": run_id,
        "review_items": len(proposals),
        "filled_table_path": str(filled_path),
        "output_table_name": output_table_name(run_dir, payload),
        "extraction_summary_path": str(summary_path),
        "review_index_path": str(html_path) if html_path else None,
        "review_package_path": str(review_pkg_path) if review_pkg_path else None,
        "proposals_path": str(proposals_path(run_dir)),
        "evidence_path": str(evidence_path(run_dir)),
        "validation_report_path": str(validation_report_path(run_dir)),
        "pdfjs_assets_copied": bool(copied_assets),
        "review_app_assets_copied": bool(copied_review_app_assets),
        "human_review_built": with_review,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build lean papers-to-table agent extraction outputs.")
    parser.add_argument("--run", required=True, help="Path to the run directory containing extraction/review_input.json.")
    parser.add_argument("--from-review-input", action="store_true", help="Explicitly use review_input.json; this is the default.")
    parser.add_argument("--with-review", action="store_true", help="Also build the optional human_review browser interface.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    args = parser.parse_args(argv)

    result = build_review_package(Path(args.run), from_review_input=True, with_review=args.with_review)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        if result.get("review_index_path"):
            print(f"review_index: {Path(result['review_index_path']).resolve()}")
        if result.get("review_package_path"):
            print(f"review_package: {Path(result['review_package_path']).resolve()}")
        print(f"proposals: {Path(result['proposals_path']).resolve()}")
        print(f"evidence: {Path(result['evidence_path']).resolve()}")
        print(f"filled_table: {Path(result['filled_table_path']).resolve()}")
        if result.get("human_review_built") and not result["pdfjs_assets_copied"]:
            print("warning: PDF.js assets were not copied; the review UI will use bundled PDF.js fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
