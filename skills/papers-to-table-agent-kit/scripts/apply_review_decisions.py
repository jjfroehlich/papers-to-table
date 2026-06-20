#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_package_common import (  # noqa: E402
    ACCEPTED_DECISIONS,
    DECISIONS,
    decisions_path,
    latest_decisions,
    read_csv,
    read_json,
    read_jsonl,
    review_package_path,
    reviewed_table_path,
    proposals_path,
    resolve_input_path,
    reviewer_summary_path,
    stable_id,
    utc_now,
    write_csv,
    write_json,
    write_jsonl,
)


def _load_package(run_dir: Path) -> dict[str, Any]:
    path = review_package_path(run_dir)
    if not path.exists():
        raise FileNotFoundError("Missing human_review/review_package.json. Build with --with-review first.")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("human_review/review_package.json must contain an object.")
    return payload


def _load_proposals(run_dir: Path) -> list[dict[str, Any]]:
    proposals = read_jsonl(proposals_path(run_dir))
    if not proposals:
        raise FileNotFoundError("Missing extraction/proposals.jsonl. Run build_review_package.py first.")
    return proposals


def _load_decisions_payload(path: Path, *, run_id: str) -> list[dict[str, Any]]:
    payload = read_json(path)
    rows = payload.get("decisions", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Decision payload must be a list or an object with a decisions list.")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        proposal_id = str(row.get("proposal_id") or row.get("item_id") or "").strip()
        decision = str(row.get("decision") or "").strip()
        if not proposal_id:
            raise ValueError(f"Decision #{index + 1} is missing proposal_id.")
        if decision not in DECISIONS:
            raise ValueError(f"Unsupported decision for proposal {proposal_id}: {decision!r}")
        normalized.append(
            {
                "review_decision_id": row.get("review_decision_id") or stable_id("rev", proposal_id, decision, utc_now()),
                "run_id": str(row.get("run_id") or run_id),
                "proposal_id": proposal_id,
                "cell_id": row.get("cell_id"),
                "decision": decision,
                "decision_source": str(row.get("decision_source") or "human_individual"),
                "edited_value": row.get("edited_value"),
                "reviewer_note": row.get("reviewer_note"),
                "decided_at": row.get("decided_at") or utc_now(),
            }
        )
    return normalized


def _auto_accept_decisions(proposals: list[dict[str, Any]], *, run_id: str) -> list[dict[str, Any]]:
    decided_at = utc_now()
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        rows.append(
            {
                "review_decision_id": stable_id("rev", proposal.get("proposal_id"), "automation_accept_all"),
                "run_id": run_id,
                "proposal_id": proposal.get("proposal_id"),
                "cell_id": proposal.get("cell_id"),
                "decision": "accepted",
                "decision_source": "automation_accept_all",
                "edited_value": None,
                "reviewer_note": "Auto-accepted by papers-to-table agent kit.",
                "decided_at": decided_at,
            }
        )
    return rows


def write_latest_decisions(run_dir: Path, new_decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = read_jsonl(decisions_path(run_dir))
    latest = latest_decisions([*existing, *new_decisions])
    rows = list(latest.values())
    rows.sort(key=lambda row: (str(row.get("proposal_id") or ""), str(row.get("decided_at") or "")))
    write_jsonl(decisions_path(run_dir), rows)
    return rows


def _base_rows_and_fields(run_dir: Path, package: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]]]:
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    source_table_value = str(source.get("source_table_path") or "").strip()
    if source_table_value:
        source_table = resolve_input_path(run_dir, source_table_value)
        rows, fieldnames = read_csv(source_table)
        row_map: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(rows):
            row_id = str(row.get("row_id") or "").strip() or stable_id("row", index, row)
            row_map[row_id] = row
        return rows, list(fieldnames), row_map

    package_rows = package.get("rows") if isinstance(package.get("rows"), list) else []
    rows_out: list[dict[str, Any]] = []
    fieldnames: list[str] = ["row_id", "pdf_id"]
    for column in package.get("columns", []) if isinstance(package.get("columns"), list) else []:
        name = str(column.get("column_name") or "").strip() if isinstance(column, dict) else ""
        if name and name not in fieldnames:
            fieldnames.append(name)
    row_map: dict[str, dict[str, Any]] = {}
    for row in package_rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("row_id") or "").strip()
        values = dict(row.get("values") if isinstance(row.get("values"), dict) else {})
        values.setdefault("row_id", row_id)
        values.setdefault("pdf_id", row.get("pdf_id") or "")
        for key in values:
            if key not in fieldnames:
                fieldnames.append(key)
        rows_out.append(values)
        row_map[row_id] = values
    return rows_out, fieldnames, row_map


def _export_value(proposal: dict[str, Any], decision: dict[str, Any]) -> Any:
    if decision.get("decision") == "accepted_with_edit":
        return decision.get("edited_value") or ""
    return proposal.get("proposed_value") or ""


def export_reviewed_table(run_dir: Path, proposals: list[dict[str, Any]], decisions: list[dict[str, Any]], package: dict[str, Any]) -> Path:
    rows, fieldnames, rows_by_id = _base_rows_and_fields(run_dir, package)
    latest = latest_decisions(decisions)
    for proposal in proposals:
        decision = latest.get(str(proposal.get("proposal_id") or ""))
        if not decision or decision.get("decision") not in ACCEPTED_DECISIONS:
            continue
        row_id = str(proposal.get("row_id") or "")
        if row_id not in rows_by_id:
            row = {"row_id": row_id, "pdf_id": proposal.get("pdf_id") or ""}
            rows_by_id[row_id] = row
            rows.append(row)
            for field in ["row_id", "pdf_id"]:
                if field not in fieldnames:
                    fieldnames.append(field)
        column = str(proposal.get("column_name") or "")
        if column and column not in fieldnames:
            fieldnames.append(column)
        rows_by_id[row_id][column] = _export_value(proposal, decision)
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    out_path = reviewed_table_path(
        run_dir,
        {
            "output_table_name": source.get("output_table_name"),
            "output_table_path": source.get("output_table_path"),
        },
    )
    write_csv(out_path, rows, fieldnames)
    return out_path


def write_audit_and_summary(
    run_dir: Path,
    proposals: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    reviewed_table: Path | None,
) -> dict[str, Any]:
    latest = latest_decisions(decisions)
    counts = {"accepted": 0, "accepted_with_edit": 0, "rejected": 0, "confirmed_no_data": 0, "pending": 0}
    audit_entries: list[dict[str, Any]] = []
    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        decision = latest.get(proposal_id)
        decision_value = str(decision.get("decision")) if decision else "pending"
        if decision_value in counts:
            counts[decision_value] += 1
        else:
            counts["pending"] += 1
        exported = bool(decision and decision_value in ACCEPTED_DECISIONS)
        exported_value = _export_value(proposal, decision) if decision and exported else None
        audit_entries.append(
            {
                "proposal_id": proposal_id,
                "cell_id": proposal.get("cell_id"),
                "row_id": proposal.get("row_id"),
                "column_name": proposal.get("column_name"),
                "decision": decision_value,
                "decision_source": decision.get("decision_source") if decision else None,
                "auto_accepted": bool(decision and decision.get("decision_source") == "automation_accept_all"),
                "proposed_value": proposal.get("proposed_value"),
                "exported": exported,
                "exported_value": exported_value,
                "reviewer_note": decision.get("reviewer_note") if decision else None,
                "decided_at": decision.get("decided_at") if decision else None,
            }
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    audit_path = run_dir / "human_review" / f"audit_log_{timestamp}.json"
    diagnostics_path = run_dir / "human_review" / f"diagnostics_{timestamp}.json"
    write_json(audit_path, {"generated_at": utc_now(), "entries": audit_entries})
    reviewer_summary = {
        "schema_version": "papers_to_table.agent_reviewer_summary.v1",
        "run_id": proposals[0].get("run_id") if proposals else run_dir.name,
        "total_proposals": len(proposals),
        "reviewed": len(proposals) - counts["pending"],
        **counts,
        "explicitly_accepted": counts["accepted"] + counts["accepted_with_edit"],
        "generated_at": utc_now(),
        "reviewed_table_path": str(reviewed_table) if reviewed_table else None,
    }
    write_json(reviewer_summary_path(run_dir), reviewer_summary)
    write_json(
        diagnostics_path,
        {
            "schema_version": "papers_to_table.agent_export_diagnostics.v1",
            "generated_at": utc_now(),
            "decision_counts": counts,
            "accepted_only_export": True,
            "reviewed_table_path": str(reviewed_table) if reviewed_table else None,
        },
    )
    return {"audit_log_path": str(audit_path), "diagnostics_path": str(diagnostics_path), "reviewer_summary": reviewer_summary}


def apply_decisions(
    run_dir: Path,
    *,
    decisions_path: Path | None = None,
    accept_all: bool = False,
    use_existing_decisions: bool = False,
    export: bool = True,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    package = _load_package(run_dir)
    proposals = _load_proposals(run_dir)
    run_id = str(package.get("run_id") or run_dir.name)
    proposal_ids = {str(proposal.get("proposal_id") or "") for proposal in proposals}

    if accept_all:
        new_decisions = _auto_accept_decisions(proposals, run_id=run_id)
    elif decisions_path is not None:
        new_decisions = _load_decisions_payload(decisions_path, run_id=run_id)
    elif use_existing_decisions:
        new_decisions = []
    else:
        raise ValueError("Pass --decisions, --accept-all, or --use-existing-decisions.")

    for decision in new_decisions:
        if str(decision.get("proposal_id") or "") not in proposal_ids:
            raise ValueError(f"Decision references unknown proposal_id: {decision.get('proposal_id')}")
        if decision.get("decision") not in DECISIONS:
            raise ValueError(f"Unsupported decision: {decision.get('decision')!r}")
    decisions = write_latest_decisions(run_dir, new_decisions)
    reviewed_path = export_reviewed_table(run_dir, proposals, decisions, package) if export else None
    summaries = write_audit_and_summary(run_dir, proposals, decisions, reviewed_path)
    accepted_count = sum(1 for decision in decisions if decision.get("decision") in ACCEPTED_DECISIONS)
    return {
        "run_id": run_id,
        "decisions_recorded": len(new_decisions),
        "decision_count": len(decisions),
        "accepted_changes_count": accepted_count,
        "reviewed_table_path": str(reviewed_path) if reviewed_path else None,
        **summaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply papers-to-table human review decisions and export reviewed CSV.")
    parser.add_argument("--run", required=True, help="Path to the generated review run directory.")
    parser.add_argument("--decisions", help="Downloaded decisions JSON.")
    parser.add_argument("--accept-all", action="store_true", help="Record automation_accept_all decisions for every proposal.")
    parser.add_argument("--use-existing-decisions", action="store_true", help="Export using human_review/decisions.jsonl already written by serve_review.py.")
    parser.add_argument("--no-export", action="store_true", help="Record decisions without writing the root reviewed CSV.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    args = parser.parse_args(argv)

    result = apply_decisions(
        Path(args.run),
        decisions_path=Path(args.decisions).resolve() if args.decisions else None,
        accept_all=args.accept_all,
        use_existing_decisions=args.use_existing_decisions,
        export=not args.no_export,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"decisions_recorded: {result['decisions_recorded']}")
        print(f"decision_count: {result['decision_count']}")
        if result.get("reviewed_table_path"):
            print(f"reviewed_table: {Path(result['reviewed_table_path']).resolve()}")
        print(f"audit_log: {Path(result['audit_log_path']).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
