#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACCEPTED = {"accepted", "accepted_with_edit"}
DECISIONS = {"accepted", "accepted_with_edit", "rejected", "confirmed_no_data"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "::".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: (value or "") for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def proposals_for_run(run_dir: Path) -> list[dict[str, Any]]:
    proposals = read_jsonl(run_dir / "proposals" / "proposals.jsonl")
    if not proposals:
        raise FileNotFoundError("No proposals found at proposals/proposals.jsonl. Build a review package first.")
    return proposals


def decisions_from_file(path: Path, *, run_id: str) -> list[dict[str, Any]]:
    payload = read_json(path, [])
    rows = payload.get("decisions", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Decision payload must be a list or an object with a decisions list.")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("decision") or "").strip()
        if decision not in DECISIONS:
            raise ValueError(f"Unsupported decision: {decision!r}")
        proposal_id = str(row.get("proposal_id") or row.get("item_id") or "").strip()
        if not proposal_id:
            raise ValueError("Decision record is missing proposal_id.")
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


def auto_accept_decisions(proposals: list[dict[str, Any]], *, run_id: str) -> list[dict[str, Any]]:
    decided_at = utc_now()
    return [
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
        for proposal in proposals
    ]


def latest_decisions(run_dir: Path, new_decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    combined = [*read_jsonl(run_dir / "review" / "decisions.jsonl"), *new_decisions]
    latest: dict[str, dict[str, Any]] = {}
    for decision in combined:
        proposal_id = str(decision.get("proposal_id") or "")
        if proposal_id:
            latest[proposal_id] = decision
    return latest


def base_table_path(run_dir: Path) -> Path:
    for candidate in [
        run_dir / "inputs" / "source_table.csv",
        run_dir / "inputs" / "seed_table.csv",
        run_dir / "tables" / "draft_table.csv",
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No base table found in inputs/source_table.csv, inputs/seed_table.csv, or tables/draft_table.csv.")


def row_label_for(row: dict[str, Any], row_index: int) -> str:
    for key in ("Title", "title", "Paper", "paper", "source_pdf", "PDF", "pdf"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return f"row {row_index + 1}"


def row_id_for(row: dict[str, Any], row_index: int) -> str:
    if row.get("row_id"):
        return str(row["row_id"]).strip()
    return stable_id("row", row_index, row_label_for(row, row_index))


def export_final_table(run_dir: Path, proposals: list[dict[str, Any]], latest: dict[str, dict[str, Any]]) -> Path:
    base_path = base_table_path(run_dir)
    rows, fieldnames = read_csv(base_path)
    base_is_draft_only = base_path == run_dir / "tables" / "draft_table.csv"
    proposal_columns = {str(proposal.get("column_name") or "") for proposal in proposals if proposal.get("column_name")}
    if base_is_draft_only:
        for row in rows:
            for column in proposal_columns:
                if column in row:
                    row[column] = ""
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        rows_by_id[row_id_for(row, row_index)] = row

    fieldnames_out = list(fieldnames)
    for proposal in proposals:
        column = str(proposal.get("column_name") or "")
        if column and column not in fieldnames_out:
            fieldnames_out.append(column)

    for proposal in proposals:
        decision = latest.get(str(proposal.get("proposal_id") or ""))
        if not decision or decision.get("decision") not in ACCEPTED:
            continue
        row_id = str(proposal.get("row_id") or "")
        if row_id not in rows_by_id:
            rows_by_id[row_id] = {"row_id": row_id}
            if "row_id" not in fieldnames_out:
                fieldnames_out.insert(0, "row_id")
            rows.append(rows_by_id[row_id])
        value = decision.get("edited_value") if decision.get("decision") == "accepted_with_edit" else proposal.get("proposed_value")
        rows_by_id[row_id][str(proposal.get("column_name"))] = value or ""

    out_path = run_dir / "exports" / "final_table.csv"
    write_csv(out_path, rows, fieldnames_out)
    return out_path


def write_audit_and_summaries(
    run_dir: Path,
    proposals: list[dict[str, Any]],
    latest: dict[str, dict[str, Any]],
    final_table_path: Path | None,
) -> dict[str, Any]:
    proposal_by_id = {str(proposal.get("proposal_id")): proposal for proposal in proposals}
    entries: list[dict[str, Any]] = []
    counts = {"accepted": 0, "accepted_with_edit": 0, "rejected": 0, "confirmed_no_data": 0, "pending": 0}
    labels = {"human_reviewed": 0, "auto_accepted": 0, "draft_unreviewed": 0, "rejected": 0, "confirmed_no_data": 0}
    handoff_items: list[dict[str, Any]] = []

    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id"))
        decision = latest.get(proposal_id)
        decision_value = str(decision.get("decision")) if decision else "pending"
        if decision_value in counts:
            counts[decision_value] += 1
        else:
            counts["pending"] += 1

        if not decision:
            label = "draft_unreviewed"
        elif decision_value in {"accepted", "accepted_with_edit"} and decision.get("decision_source") == "automation_accept_all":
            label = "auto_accepted"
        elif decision_value in {"accepted", "accepted_with_edit"}:
            label = "human_reviewed"
        elif decision_value == "rejected":
            label = "rejected"
        elif decision_value == "confirmed_no_data":
            label = "confirmed_no_data"
        else:
            label = "draft_unreviewed"
        labels[label] += 1

        exported = bool(decision and decision_value in ACCEPTED)
        exported_value = None
        if exported:
            exported_value = decision.get("edited_value") if decision_value == "accepted_with_edit" else proposal.get("proposed_value")
        entries.append(
            {
                "proposal_id": proposal_id,
                "row_id": proposal.get("row_id"),
                "column_name": proposal.get("column_name"),
                "cell_id": proposal.get("cell_id"),
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
        handoff_items.append(
            {
                "proposal_id": proposal_id,
                "row_id": proposal.get("row_id"),
                "column_name": proposal.get("column_name"),
                "value": exported_value if exported else proposal.get("proposed_value"),
                "handoff_label": label,
            }
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    audit_path = run_dir / "exports" / f"audit_log_{timestamp}.json"
    write_json(audit_path, {"generated_at": utc_now(), "entries": entries})

    reviewer_summary = {
        "schema_version": "papers_to_table_agent_reviewer_summary.v1",
        "run_id": run_dir.name,
        "total_proposals": len(proposals),
        **counts,
        "explicitly_accepted": counts["accepted"] + counts["accepted_with_edit"],
        "automation_review_applied": labels["auto_accepted"] > 0,
        "automation_accepted_count": labels["auto_accepted"],
        "generated_at": utc_now(),
    }
    write_json(run_dir / "summaries" / "reviewer_summary.json", reviewer_summary)
    write_json(
        run_dir / "summaries" / "report_handoff.json",
        {
            "schema_version": "papers_to_table_agent_report_handoff.v1",
            "run_id": run_dir.name,
            "summary": labels,
            "items": handoff_items,
        },
    )
    write_json(
        run_dir / "exports" / f"diagnostics_{timestamp}.json",
        {
            "run_id": run_dir.name,
            "generated_at": utc_now(),
            "decision_counts": counts,
            "handoff_labels": labels,
            "final_table_path": str(final_table_path) if final_table_path else None,
        },
    )
    append_run_report(run_dir, counts, labels, final_table_path)
    return {
        "audit_log_path": str(audit_path.resolve()),
        "reviewer_summary": reviewer_summary,
        "handoff_labels": labels,
    }


def append_run_report(run_dir: Path, counts: dict[str, int], labels: dict[str, int], final_table_path: Path | None) -> None:
    path = run_dir / "summaries" / "run_report.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Papers-to-table agent kit run report\n"
    section = [
        "",
        "## Decision and export summary",
        "",
        f"- Decisions applied at: {utc_now()}",
        f"- Accepted: {counts['accepted']}",
        f"- Accepted with edit: {counts['accepted_with_edit']}",
        f"- Rejected: {counts['rejected']}",
        f"- Confirmed no data: {counts['confirmed_no_data']}",
        f"- Pending/draft: {counts['pending']}",
        f"- Human-reviewed handoff values: {labels['human_reviewed']}",
        f"- Auto-accepted handoff values: {labels['auto_accepted']}",
        f"- Draft/unreviewed handoff values: {labels['draft_unreviewed']}",
        f"- Final table: {final_table_path if final_table_path else 'not exported'}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing.rstrip() + "\n" + "\n".join(section) + "\n", encoding="utf-8")


def apply_decisions(
    run_dir: Path,
    *,
    decisions_path: Path | None = None,
    accept_all: bool = False,
    export: bool = True,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    proposals = proposals_for_run(run_dir)
    if accept_all:
        new_decisions = auto_accept_decisions(proposals, run_id=run_dir.name)
    elif decisions_path is not None:
        new_decisions = decisions_from_file(decisions_path, run_id=run_dir.name)
    else:
        raise ValueError("Pass --decisions or --accept-all.")

    proposal_ids = {str(proposal.get("proposal_id")) for proposal in proposals}
    for decision in new_decisions:
        if str(decision.get("proposal_id")) not in proposal_ids:
            raise ValueError(f"Decision references unknown proposal_id: {decision.get('proposal_id')}")

    append_jsonl(run_dir / "review" / "decisions.jsonl", new_decisions)
    latest = latest_decisions(run_dir, [])
    final_table_path = export_final_table(run_dir, proposals, latest) if export else None
    summaries = write_audit_and_summaries(run_dir, proposals, latest, final_table_path)
    result = {
        "run_id": run_dir.name,
        "decisions_recorded": len(new_decisions),
        "final_table_path": str(final_table_path.resolve()) if final_table_path else None,
        **summaries,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply papers-to-table agent review decisions and export a final table.")
    parser.add_argument("--run", required=True, help="Path to the lite run bundle directory.")
    parser.add_argument("--decisions", help="Downloaded review decisions JSON.")
    parser.add_argument("--accept-all", action="store_true", help="Record automation_accept_all decisions for every proposal.")
    parser.add_argument("--no-export", action="store_true", help="Record decisions without writing exports/final_table.csv.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    args = parser.parse_args(argv)

    result = apply_decisions(
        Path(args.run),
        decisions_path=Path(args.decisions).resolve() if args.decisions else None,
        accept_all=bool(args.accept_all),
        export=not args.no_export,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"decisions_recorded: {result['decisions_recorded']}")
        if result.get("final_table_path"):
            print(f"final_table: {result['final_table_path']}")
        print(f"audit_log: {result['audit_log_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
