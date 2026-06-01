#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_package_common import (  # noqa: E402
    DECISIONS,
    EVIDENCE_STATUSES,
    MAIN_COMPAT_SOURCE_TYPES,
    MAIN_EVIDENCE_SCHEMA_VERSION,
    PROPOSAL_STATUSES,
    REVIEW_BUCKETS,
    REVIEW_INPUT_SCHEMA_VERSION,
    evidence_tier,
    is_finite_number,
    is_non_empty,
    load_review_input,
    normalized_regions,
    read_json,
    read_jsonl,
    write_json,
)


def _report(mode: str, errors: list[str], warnings: list[str], counts: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": "papers_to_table.validation_report.v1",
        "mode": mode,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
    }


def _page_number(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _validate_regions(
    raw_value: Any,
    *,
    context: str,
    label: str,
    default_page: Any,
    errors: list[str],
    warnings: list[str],
) -> None:
    if raw_value is None:
        return
    regions = normalized_regions(raw_value, default_page=_page_number(default_page))
    if not regions:
        errors.append(f"{context}.{label} must be a region object/list or a [x0, y0, x1, y1] bbox.")
        return

    conventions: set[str] = set()
    for index, region in enumerate(regions):
        prefix = f"{context}.{label}[{index}]"
        coords: dict[str, float] = {}
        for key in ("x0", "y0", "x1", "y1"):
            value = region.get(key)
            if not is_finite_number(value):
                errors.append(f"{prefix}.{key} must be a finite number.")
                continue
            coords[key] = float(value)

        page = _page_number(region.get("page"))
        if page is None:
            errors.append(f"{prefix}.page must be present and a positive integer.")

        if len(coords) != 4:
            continue
        if math.isclose(coords["x0"], coords["x1"]) or math.isclose(coords["y0"], coords["y1"]):
            errors.append(f"{prefix} must have nonzero area.")
            continue

        max_abs = max(abs(value) for value in coords.values())
        min_value = min(coords.values())
        max_value = max(coords.values())
        if max_abs <= 1.05:
            conventions.add("normalized")
            if min_value < 0 or max_value > 1:
                errors.append(f"{prefix} looks normalized but coordinates must stay within [0, 1].")
        else:
            conventions.add("absolute")
            if max_abs <= 100:
                warnings.append(
                    f"{prefix} uses small absolute coordinates; verify they are page-space units rather than percentages."
                )

    if len(conventions) > 1:
        warnings.append(f"{context}.{label} mixes normalized and absolute coordinate conventions.")


def validate_authoring(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    counts = {"pdfs": 0, "rows": 0, "columns": 0, "proposals": 0, "evidence": 0}

    try:
        payload = load_review_input(run_dir)
    except Exception as exc:
        return _report("authoring", [str(exc)], warnings, counts)

    version = str(payload.get("schema_version") or "").strip()
    if version and version != REVIEW_INPUT_SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version {version!r}; expected {REVIEW_INPUT_SCHEMA_VERSION!r}.")
    if not version:
        warnings.append("review_input.json is missing schema_version; assuming papers_to_table.review_input.v1.")

    pdfs = payload.get("pdfs")
    if not isinstance(pdfs, list) or not pdfs:
        errors.append("review_input.json must include a non-empty pdfs list.")
        pdfs = []
    pdf_ids: set[str] = set()
    for index, item in enumerate(pdfs):
        if not isinstance(item, dict):
            errors.append(f"pdfs[{index}] must be an object.")
            continue
        pdf_id = str(item.get("pdf_id") or "").strip()
        if not pdf_id:
            errors.append(f"pdfs[{index}] is missing pdf_id.")
            continue
        if pdf_id in pdf_ids:
            errors.append(f"Duplicate pdf_id: {pdf_id}")
        pdf_ids.add(pdf_id)
        path_value = str(item.get("path") or "").strip()
        if not path_value:
            errors.append(f"pdfs[{index}] is missing path.")
        else:
            path = (run_dir / path_value).resolve() if not Path(path_value).is_absolute() else Path(path_value)
            if not path.exists():
                errors.append(f"PDF file does not exist for pdf_id={pdf_id}: {path_value}")
    counts["pdfs"] = len(pdf_ids)

    columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
    column_names = {str(item.get("column_name") or "").strip() for item in columns if isinstance(item, dict)}
    column_names.discard("")
    counts["columns"] = len(column_names)

    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    row_ids: set[str] = set()
    row_pdf_by_id: dict[str, str] = {}
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            warnings.append(f"rows[{index}] is not an object and will be ignored.")
            continue
        row_id = str(item.get("row_id") or "").strip()
        if not row_id:
            warnings.append(f"rows[{index}] is missing row_id and will not be addressable by proposals.")
            continue
        if row_id in row_ids:
            errors.append(f"Duplicate row_id: {row_id}")
        row_ids.add(row_id)
        pdf_id = str(item.get("pdf_id") or "").strip()
        if pdf_id:
            row_pdf_by_id[row_id] = pdf_id
            if pdf_id not in pdf_ids:
                errors.append(f"rows[{index}] references unknown pdf_id: {pdf_id}")
    counts["rows"] = len(row_ids)

    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        errors.append("review_input.json must include a non-empty proposals list.")
        proposals = []
    counts["proposals"] = len(proposals)

    seen_proposal_ids: set[str] = set()
    seen_evidence_ids: set[str] = set()
    for proposal_index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            errors.append(f"proposals[{proposal_index}] must be an object.")
            continue
        proposal_id = str(proposal.get("proposal_id") or "").strip()
        if proposal_id:
            if proposal_id in seen_proposal_ids:
                errors.append(f"Duplicate proposal_id: {proposal_id}")
            seen_proposal_ids.add(proposal_id)
        row_id = str(proposal.get("row_id") or "").strip()
        column_name = str(proposal.get("column_name") or "").strip()
        if not row_id:
            errors.append(f"proposals[{proposal_index}] is missing row_id.")
        elif row_ids and row_id not in row_ids:
            warnings.append(f"proposals[{proposal_index}] references row_id not listed in rows; builder will synthesize it: {row_id}")
        if not column_name:
            errors.append(f"proposals[{proposal_index}] is missing column_name.")
        elif column_names and column_name not in column_names:
            warnings.append(f"proposals[{proposal_index}] references column not listed in columns; builder will synthesize it: {column_name}")
        if proposal.get("proposal_status") and str(proposal["proposal_status"]) not in PROPOSAL_STATUSES:
            errors.append(f"proposals[{proposal_index}] has unsupported proposal_status: {proposal['proposal_status']!r}")

        proposal_pdf_id = str(proposal.get("pdf_id") or row_pdf_by_id.get(row_id, "")).strip()
        if proposal_pdf_id and proposal_pdf_id not in pdf_ids:
            errors.append(f"proposals[{proposal_index}] references unknown pdf_id: {proposal_pdf_id}")

        proposed_value = proposal.get("proposed_value")
        evidence_items = proposal.get("evidence") if isinstance(proposal.get("evidence"), list) else []
        counts["evidence"] += len(evidence_items)
        valid_evidence_count = 0
        for evidence_index, evidence in enumerate(evidence_items):
            if not isinstance(evidence, dict):
                errors.append(f"proposals[{proposal_index}].evidence[{evidence_index}] must be an object.")
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if evidence_id:
                if evidence_id in seen_evidence_ids:
                    errors.append(f"Duplicate evidence_id: {evidence_id}")
                seen_evidence_ids.add(evidence_id)
            evidence_pdf_id = str(evidence.get("pdf_id") or proposal_pdf_id or "").strip()
            if evidence_pdf_id and evidence_pdf_id not in pdf_ids:
                errors.append(f"proposals[{proposal_index}].evidence[{evidence_index}] references unknown pdf_id: {evidence_pdf_id}")
            context = f"proposals[{proposal_index}].evidence[{evidence_index}]"
            _validate_regions(
                evidence.get("exact_highlight_regions"),
                context=context,
                label="exact_highlight_regions",
                default_page=evidence.get("page_number"),
                errors=errors,
                warnings=warnings,
            )
            _validate_regions(
                evidence.get("approximate_highlight_regions") or evidence.get("bbox"),
                context=context,
                label="approximate_highlight_regions" if evidence.get("approximate_highlight_regions") else "bbox",
                default_page=evidence.get("page_number"),
                errors=errors,
                warnings=warnings,
            )
            tier = evidence_tier(evidence, inherited_pdf_id=proposal_pdf_id)
            if tier["tier"] != "D":
                valid_evidence_count += 1
        if is_non_empty(proposed_value) and valid_evidence_count == 0:
            errors.append(
                f"proposals[{proposal_index}] has non-empty proposed_value but no structured Tier A/B/C evidence."
            )

    return _report("authoring", errors, warnings, counts)


def validate_generated(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    counts = {"proposals": 0, "evidence": 0, "decisions": 0, "exports": 0}

    required = [
        "review/index.html",
        "review/review_package.json",
        "normalized/proposals.jsonl",
        "normalized/evidence.jsonl",
        "summaries/validation_report.json",
    ]
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"Missing generated artifact: {rel}")

    if errors:
        return _report("generated", errors, warnings, counts)

    try:
        package = read_json(run_dir / "review" / "review_package.json")
    except Exception as exc:
        errors.append(f"Cannot read review/review_package.json: {exc}")
        package = {}
    proposals = read_jsonl(run_dir / "normalized" / "proposals.jsonl")
    evidence = read_jsonl(run_dir / "normalized" / "evidence.jsonl")
    counts["proposals"] = len(proposals)
    counts["evidence"] = len(evidence)

    proposal_ids = {str(item.get("proposal_id")) for item in proposals if item.get("proposal_id")}
    evidence_ids = {str(item.get("evidence_id")) for item in evidence if item.get("evidence_id")}
    if len(proposal_ids) != len(proposals):
        errors.append("normalized/proposals.jsonl contains duplicate or missing proposal_id values.")
    if len(evidence_ids) != len(evidence):
        errors.append("normalized/evidence.jsonl contains duplicate or missing evidence_id values.")
    for index, proposal in enumerate(proposals):
        for field in ["proposal_id", "run_id", "row_id", "column_name", "cell_id", "proposal_status", "evidence_status", "review_bucket", "evidence_ids"]:
            if field not in proposal:
                errors.append(f"proposal #{index + 1} is missing {field}.")
        if proposal.get("proposal_status") not in PROPOSAL_STATUSES:
            errors.append(f"proposal {proposal.get('proposal_id')} has invalid proposal_status.")
        if proposal.get("evidence_status") not in EVIDENCE_STATUSES:
            errors.append(f"proposal {proposal.get('proposal_id')} has invalid evidence_status.")
        if proposal.get("review_bucket") not in REVIEW_BUCKETS:
            errors.append(f"proposal {proposal.get('proposal_id')} has invalid review_bucket.")
        for evidence_id in proposal.get("evidence_ids", []) or []:
            if evidence_id not in evidence_ids:
                errors.append(f"proposal {proposal.get('proposal_id')} references missing evidence_id {evidence_id}.")
    for index, item in enumerate(evidence):
        for field in ["evidence_id", "proposal_id", "run_id", "pdf_id", "source_type", "is_primary", "evidence_status", "review_bucket"]:
            if field not in item:
                errors.append(f"evidence #{index + 1} is missing {field}.")
        if item.get("evidence_schema_version") != MAIN_EVIDENCE_SCHEMA_VERSION:
            errors.append(f"evidence {item.get('evidence_id')} has invalid evidence_schema_version.")
        if item.get("proposal_id") not in proposal_ids:
            errors.append(f"evidence {item.get('evidence_id')} references missing proposal_id {item.get('proposal_id')}.")
        if item.get("source_type") not in MAIN_COMPAT_SOURCE_TYPES:
            errors.append(f"evidence {item.get('evidence_id')} has invalid main-compatible source_type {item.get('source_type')!r}.")
        if item.get("evidence_status") not in EVIDENCE_STATUSES:
            errors.append(f"evidence {item.get('evidence_id')} has invalid evidence_status.")
        if item.get("review_bucket") not in REVIEW_BUCKETS:
            errors.append(f"evidence {item.get('evidence_id')} has invalid review_bucket.")
        context = f"normalized/evidence.jsonl[{index}]"
        _validate_regions(
            item.get("exact_highlight_regions"),
            context=context,
            label="exact_highlight_regions",
            default_page=item.get("page_number"),
            errors=errors,
            warnings=warnings,
        )
        _validate_regions(
            item.get("approximate_highlight_regions"),
            context=context,
            label="approximate_highlight_regions",
            default_page=item.get("page_number"),
            errors=errors,
            warnings=warnings,
        )

    pdfs = package.get("pdfs") if isinstance(package, dict) else []
    if isinstance(pdfs, list):
        for pdf in pdfs:
            if not isinstance(pdf, dict):
                continue
            path_value = str(pdf.get("asset_path") or pdf.get("path") or "").strip()
            if path_value:
                path = (run_dir / "review" / path_value).resolve()
                try:
                    path.relative_to(run_dir)
                except ValueError:
                    errors.append(f"PDF asset path escapes run directory: {path_value}")
                    continue
                if not path.exists():
                    errors.append(f"PDF asset is missing: {path_value}")

    decisions_path = run_dir / "review" / "decisions.jsonl"
    if decisions_path.exists():
        decisions = read_jsonl(decisions_path)
        counts["decisions"] = len(decisions)
        for decision in decisions:
            if decision.get("proposal_id") not in proposal_ids:
                errors.append(f"decision {decision.get('review_decision_id')} references missing proposal_id {decision.get('proposal_id')}.")
            if decision.get("decision") not in DECISIONS:
                errors.append(f"decision {decision.get('review_decision_id')} has invalid decision {decision.get('decision')!r}.")

    exports_dir = run_dir / "exports"
    if exports_dir.exists():
        counts["exports"] = len([path for path in exports_dir.iterdir() if path.is_file()])
    return _report("generated", errors, warnings, counts)


def persist_report(run_dir: Path, report: dict[str, Any]) -> None:
    write_json(run_dir / "summaries" / "validation_report.json", report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a papers-to-table rich agent-kit review package.")
    parser.add_argument("--run", required=True, help="Path to the run directory.")
    parser.add_argument("--mode", choices=["authoring", "generated"], default="authoring")
    parser.add_argument("--write-report", action="store_true", help="Write summaries/validation_report.json.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    args = parser.parse_args(argv)

    run_dir = Path(args.run)
    report = validate_authoring(run_dir) if args.mode == "authoring" else validate_generated(run_dir)
    if args.write_report:
        persist_report(run_dir, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"mode: {report['mode']}")
        print(f"ok: {report['ok']}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
