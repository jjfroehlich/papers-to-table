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
    infer_source_type,
    is_non_empty,
    merged_evidence_semantics,
    normalized_regions,
    read_csv,
    read_json,
    safe_filename,
    stable_id,
    text_evidence_value,
    utc_now,
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


def _template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "review.html"


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
    out_dir = run_dir / "review" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for candidate_dir in candidates:
        pdf = candidate_dir / "pdf.mjs"
        worker = candidate_dir / "pdf.worker.mjs"
        if pdf.exists() and worker.exists():
            shutil.copy2(pdf, out_dir / "pdf.mjs")
            shutil.copy2(worker, out_dir / "pdf.worker.mjs")
            copied.extend(["review/assets/pdf.mjs", "review/assets/pdf.worker.mjs"])
            break
    return copied


def _load_schema_columns(run_dir: Path) -> list[dict[str, Any]]:
    schema_path = run_dir / "schema.json"
    if not schema_path.exists():
        return []
    payload = read_json(schema_path)
    columns: Any
    if isinstance(payload, dict):
        columns = payload.get("columns", [])
        if isinstance(columns, dict):
            columns = [{"column_name": name, **(value or {})} for name, value in columns.items()]
    else:
        columns = payload
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
                "allowed_values": item.get("allowed_values"),
                "is_target": bool(item.get("is_target", True)),
            }
        )
    return normalized


def _normalize_field_type(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    return FIELD_TYPE_ALIASES.get(raw, raw if raw in {"text", "number", "categorical", "boolean"} else None)


def _source_table(run_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    path = run_dir / "source_table.csv"
    if not path.exists():
        return [], []
    return read_csv(path)


def _row_label(row: dict[str, Any], row_id: str, index: int) -> str:
    values = row.get("values") if isinstance(row.get("values"), dict) else row
    for key in ("Title", "title", "Paper", "paper", "label", "pdf_id"):
        value = values.get(key) if isinstance(values, dict) else None
        if is_non_empty(value):
            return str(value).strip()
    return row_id or f"row {index + 1}"


def _normalize_pdfs(run_dir: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pdfs = payload.get("pdfs") if isinstance(payload.get("pdfs"), list) else []
    pdf_dir = run_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    normalized: list[dict[str, Any]] = []
    for item in raw_pdfs:
        if not isinstance(item, dict):
            continue
        pdf_id = str(item.get("pdf_id") or "").strip()
        if not pdf_id:
            continue
        raw_path = str(item.get("path") or "").strip()
        source = (run_dir / raw_path).resolve() if raw_path and not Path(raw_path).is_absolute() else Path(raw_path)
        target = source
        try:
            target.relative_to(run_dir.resolve())
        except ValueError:
            suffix = source.suffix if source.suffix else ".pdf"
            target = pdf_dir / f"{safe_filename(pdf_id, 'pdf')}{suffix}"
            if source.exists():
                shutil.copy2(source, target)
        rel_path = target.resolve().relative_to(run_dir.resolve()).as_posix()
        normalized.append(
            {
                "pdf_id": pdf_id,
                "label": item.get("label") or item.get("title") or pdf_id,
                "path": rel_path,
                "asset_path": f"../{rel_path}",
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
                "allowed_values": column.get("allowed_values"),
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
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
    row_pdf = _row_pdf_lookup(rows)
    column_defs = {item["column_name"]: item for item in columns}
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
                "evidence_status": item.get("evidence_status") or semantics["evidence_status"],
                "review_bucket": item.get("review_bucket") or semantics["review_bucket"],
                "reason_codes": reason_codes,
                "proposed_value": proposed_value,
                "rationale": item.get("rationale") or item.get("reasoning"),
                "calculation": item.get("calculation"),
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
    source_table_present: bool,
    pdfs: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
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


def _write_draft_filled_table(
    run_dir: Path,
    table_rows: list[dict[str, str]],
    table_fieldnames: list[str],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> Path:
    out_rows, fieldnames, rows_by_id = _draft_rows_and_fields(table_rows, table_fieldnames, rows, columns)
    for proposal in proposals:
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
        rows_by_id[row_id][column_name] = proposal.get("proposed_value") or ""

    out_path = run_dir / "exports" / "draft_filled_table.csv"
    write_csv(out_path, out_rows, fieldnames)
    return out_path


def _write_review_html(run_dir: Path, package: dict[str, Any]) -> Path:
    template = _template_path().read_text(encoding="utf-8")
    package_json = json.dumps(package, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("__REVIEW_PACKAGE_JSON__", package_json)
    out_path = run_dir / "review" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def build_review_package(run_dir: Path, *, from_review_input: bool = True) -> dict[str, Any]:
    if not from_review_input:
        raise ValueError("The rich agent kit now builds from review_input.json by default.")
    run_dir = run_dir.resolve()
    payload = read_json(run_dir / "review_input.json")
    authoring_report = validate_authoring(run_dir)
    persist_report(run_dir, authoring_report)
    if not authoring_report["ok"]:
        raise ValueError("review_input.json failed authoring validation. See summaries/validation_report.json.")

    generated_at = utc_now()
    run_id = str(payload.get("run_id") or run_dir.name)
    table_rows, table_fieldnames = _source_table(run_dir)
    schema_columns = _load_schema_columns(run_dir)
    raw_proposals = payload.get("proposals") if isinstance(payload.get("proposals"), list) else []
    pdfs = _normalize_pdfs(run_dir, payload)
    rows = _normalize_rows(payload, table_rows, table_fieldnames, raw_proposals)
    columns = _normalize_columns(payload, schema_columns, table_fieldnames, raw_proposals)
    proposals, evidence = _normalize_proposals(run_id, payload, rows, columns, generated_at)
    package = _build_review_package(
        run_id,
        generated_at,
        payload,
        bool((run_dir / "source_table.csv").exists()),
        pdfs,
        rows,
        columns,
        proposals,
        evidence,
    )

    write_jsonl(run_dir / "normalized" / "proposals.jsonl", proposals)
    write_jsonl(run_dir / "normalized" / "evidence.jsonl", evidence)
    write_json(run_dir / "review" / "review_package.json", package)
    draft_table_path = _write_draft_filled_table(run_dir, table_rows, table_fieldnames, rows, columns, proposals)
    html_path = _write_review_html(run_dir, package)
    copied_assets = _copy_pdfjs_assets(run_dir)
    generated_report = validate_generated(run_dir)
    generated_report["authoring"] = authoring_report
    generated_report["copied_assets"] = copied_assets
    persist_report(run_dir, generated_report)
    if not generated_report["ok"]:
        raise ValueError("Generated review package failed validation. See summaries/validation_report.json.")
    return {
        "run_id": run_id,
        "review_items": len(proposals),
        "review_index_path": str(html_path),
        "review_package_path": str(run_dir / "review" / "review_package.json"),
        "proposals_path": str(run_dir / "normalized" / "proposals.jsonl"),
        "evidence_path": str(run_dir / "normalized" / "evidence.jsonl"),
        "validation_report_path": str(run_dir / "summaries" / "validation_report.json"),
        "draft_filled_table_path": str(draft_table_path),
        "pdfjs_assets_copied": bool(copied_assets),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a rich static papers-to-table agent review package.")
    parser.add_argument("--run", required=True, help="Path to the run directory containing review_input.json.")
    parser.add_argument("--from-review-input", action="store_true", help="Explicitly use review_input.json; this is the default.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    args = parser.parse_args(argv)

    result = build_review_package(Path(args.run), from_review_input=True)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"review_index: {Path(result['review_index_path']).resolve()}")
        print(f"review_package: {Path(result['review_package_path']).resolve()}")
        print(f"proposals: {Path(result['proposals_path']).resolve()}")
        print(f"evidence: {Path(result['evidence_path']).resolve()}")
        print(f"draft_filled_table: {Path(result['draft_filled_table_path']).resolve()}")
        if not result["pdfjs_assets_copied"]:
            print("warning: PDF.js assets were not copied; the review UI will use browser PDF fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
