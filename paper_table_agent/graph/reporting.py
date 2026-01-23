from __future__ import annotations

import csv
import json
import logging
import zipfile
from pathlib import Path

from jinja2 import Template

from paper_table_agent.io.schema import load_schema
from paper_table_agent.store.db import Store

LOGGER = logging.getLogger(__name__)


_REPORT_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Mapping Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background-color: #f4f4f4; }
    .candidates { margin-left: 16px; }
  </style>
  </head>
<body>
  <h1>Mapping Report</h1>
  <p>
    Matched: {{ matched }} |
    Ambiguous: {{ ambiguous }} |
    Unmatched: {{ unmatched }} |
    Duplicates: {{ duplicates }}
  </p>
  <table>
    <thead>
      <tr>
        <th>PDF ID</th>
        <th>Row ID</th>
        <th>Status</th>
        <th>Confidence</th>
        <th>PDF Title</th>
        <th>PDF Authors</th>
        <th>PDF Year</th>
        <th>Row Title</th>
        <th>Row Authors</th>
        <th>Row Year</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.pdf_id }}</td>
        <td>{{ row.row_id }}</td>
        <td>{{ row.status }}</td>
        <td>{{ row.confidence }}</td>
        <td>{{ row.pdf_title }}</td>
        <td>{{ row.pdf_authors }}</td>
        <td>{{ row.pdf_year }}</td>
        <td>{{ row.row_title }}</td>
        <td>{{ row.row_authors }}</td>
        <td>{{ row.row_year }}</td>
      </tr>
      {% if row.candidates %}
      <tr>
        <td colspan=\"10\">
          <div class=\"candidates\">
            <strong>Top candidates</strong>
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Row ID</th>
                  <th>Score</th>
                  <th>Title</th>
                  <th>Authors</th>
                  <th>Year</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {% for candidate in row.candidates %}
                <tr>
                  <td>{{ candidate.rank }}</td>
                  <td>{{ candidate.row_id }}</td>
                  <td>{{ candidate.score }}</td>
                  <td>{{ candidate.title }}</td>
                  <td>{{ candidate.authors }}</td>
                  <td>{{ candidate.year }}</td>
                  <td>{{ candidate.source }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </td>
      </tr>
      {% endif %}
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""
)


def write_mapping_report(store: Store, output_dir: Path, write_html: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    matches = store.fetch_matches()
    rows = {row["row_id"]: dict(row) for row in store.fetch_rows()}
    pdf_metadata = {row["pdf_id"]: dict(row) for row in store.fetch_pdf_metadata()}
    candidates = store.fetch_match_candidates()
    candidates_by_pdf: dict[str, list[dict[str, object]]] = {}
    for candidate in candidates:
        candidates_by_pdf.setdefault(candidate["pdf_id"], []).append(dict(candidate))
    for pdf_id, items in candidates_by_pdf.items():
        items.sort(key=lambda item: (item.get("rank") or 0, item.get("source") or ""))
        candidates_by_pdf[pdf_id] = items
    report_rows = []
    for match in matches:
        row = rows.get(match["row_id"], {})
        pdf_meta = pdf_metadata.get(match["pdf_id"], {})
        report_rows.append(
            {
                "pdf_id": match["pdf_id"],
                "row_id": match["row_id"],
                "status": match["status"],
                "confidence": match["confidence"],
                "pdf_title": pdf_meta.get("title", ""),
                "pdf_authors": pdf_meta.get("authors", ""),
                "pdf_year": pdf_meta.get("year", ""),
                "row_title": row.get("title", ""),
                "row_authors": row.get("authors", ""),
                "row_year": row.get("year", ""),
                "candidates": candidates_by_pdf.get(match["pdf_id"], []),
            }
        )

    summary = {
        "matched": sum(1 for match in matches if match["status"] == "matched"),
        "ambiguous": sum(1 for match in matches if match["status"] == "ambiguous"),
        "unmatched": sum(1 for match in matches if match["status"] == "unmatched"),
        "duplicates": sum(1 for match in matches if match["status"] == "duplicate"),
    }

    if write_html:
        html = _REPORT_TEMPLATE.render(rows=report_rows, **summary)
        (output_dir / "mapping_report.html").write_text(html, encoding="utf-8")

    with (output_dir / "pdf_row_matches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pdf_id",
                "row_id",
                "status",
                "confidence",
                "pdf_title",
                "pdf_authors",
                "pdf_year",
                "row_title",
                "row_authors",
                "row_year",
            ]
        )
        for row in report_rows:
            writer.writerow(
                [
                    row["pdf_id"],
                    row["row_id"],
                    row["status"],
                    row["confidence"],
                    row["pdf_title"],
                    row["pdf_authors"],
                    row["pdf_year"],
                    row["row_title"],
                    row["row_authors"],
                    row["row_year"],
                ]
            )


def write_run_report(store: Store, run_paths: Path | object) -> str:
    run_dir = run_paths.run_dir if hasattr(run_paths, "run_dir") else Path(run_paths)
    config_path = run_dir / "run_config.json"
    config_payload = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    matches = [dict(row) for row in store.fetch_matches()]
    proposals = [
        dict(row)
        for row in store.conn.execute("SELECT column, status, flags_json FROM proposals")
    ]
    events = [
        dict(row)
        for row in store.conn.execute("SELECT level, event_type, payload_json FROM events")
    ]
    matched = sum(1 for row in matches if row.get("status") == "matched")
    ambiguous = sum(1 for row in matches if row.get("status") == "ambiguous")
    unmatched = sum(1 for row in matches if row.get("status") in {"unmatched", "duplicate"})
    proposal_counts = _proposal_counts(proposals)
    extractable_columns = _count_extractable_columns(store, config_payload, matched_rows=matches)
    sanity_check = _run_sanity_check(
        matched,
        extractable_columns,
        proposal_counts.get("total", 0),
        store,
        config_payload,
        matches,
        proposals,
    )
    health_events = [event for event in events if event.get("event_type") == "health_check_failed"]
    run_status = "failed" if sanity_check.get("failed") or health_events else "completed"
    if run_status != "failed":
        error_events = [event for event in events if event.get("level") == "error"]
        if error_events:
            run_status = "completed_with_errors"
    if run_status == "failed":
        (run_dir / "FAILED").write_text("failed", encoding="utf-8")
        if sanity_check.get("failed"):
            LOGGER.error("Run failed sanity check: %s", sanity_check)
        elif health_events:
            LOGGER.error("Run failed health check: %s", health_events)
    retrieval_backend = next(
        (
            json.loads(event.get("payload_json") or "{}")
            for event in reversed(events)
            if event.get("event_type") == "retrieval_backend"
        ),
        {},
    )
    debug_extraction = []
    for row in store.fetch_debug_extraction():
        payload_json = row["payload_json"]
        payload = json.loads(payload_json) if payload_json else {}
        debug_extraction.append(payload)
    payload = {
        "run_id": run_dir.name,
        "status": run_status,
        "inputs": {
            "table_path": config_payload.get("table_path"),
            "pdf_folder": config_payload.get("pdf_folder"),
        },
        "summary": {
            "mapping": {
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "total": len(matches),
            },
            "proposals": proposal_counts,
            "errors": {
                "total_events": len(events),
                "error_events": sum(1 for row in events if row.get("level") == "error"),
            },
            "health_check": {
                "failed": bool(health_events),
                "errors": [json.loads(event.get("payload_json") or "{}") for event in health_events],
            },
            "retrieval": retrieval_backend,
            "sanity_check": sanity_check,
        },
        "debug_extraction": debug_extraction,
    }
    (run_dir / "run_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return run_status


def _count_extractable_columns(
    store: Store,
    config_payload: dict[str, object],
    matched_rows: list[dict[str, object]],
) -> int:
    try:
        table_path = Path(str(config_payload.get("table_path", "")))
        schema_source = table_path
        if config_payload.get("schema_mode") == "separate" and config_payload.get("schema_path"):
            schema_source = Path(str(config_payload["schema_path"]))
        specs = load_schema(schema_source, str(config_payload.get("schema_sheet_name", "schema")))
    except Exception:
        return 0
    schema_columns = [spec.column_name for spec in specs]
    if not schema_columns:
        return 0
    matched_row_ids = {
        str(row.get("row_id"))
        for row in matched_rows
        if row.get("status") == "matched" and row.get("row_id") is not None
    }
    if not matched_row_ids:
        return 0
    locked_rows = store.list_locks()
    locked_map: dict[str, set[str]] = {}
    for lock in locked_rows:
        if str(lock["row_id"]) in matched_row_ids:
            locked_map.setdefault(str(lock["row_id"]), set()).add(str(lock["column"]))
    extractable: set[str] = set()
    for row_id in matched_row_ids:
        locked = locked_map.get(row_id, set())
        for column in schema_columns:
            if column not in locked:
                extractable.add(column)
    return len(extractable)


def _proposal_counts(proposals: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {"total": len(proposals)}
    for row in proposals:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _run_sanity_check(
    matched: int,
    extractable_columns: int,
    proposals_count: int,
    store: Store,
    config_payload: dict[str, object],
    matches: list[dict[str, object]],
    proposals: list[dict[str, object]],
) -> dict[str, object]:
    failed = matched > 0 and proposals_count == 0
    if not failed:
        return {"failed": False}
    schema_columns = _load_schema_columns(config_payload)
    missing_cell_count = _missing_cell_count(store, schema_columns, matches)
    extraction_events = _event_count(store, "extraction_invoked")
    validation_drop_count = sum(
        1
        for proposal in proposals
        if "evidence_validation_errors" in json.loads(proposal.get("flags_json") or "{}")
    )
    return {
        "failed": True,
        "reason": (
            "Matched PDFs and extractable columns were detected, but zero proposals were stored. "
            "This usually indicates extraction never ran or proposal persistence failed."
        ),
        "diagnostics": {
            "schema_columns_loaded": schema_columns,
            "schema_column_count": len(schema_columns),
            "extractable_columns": extractable_columns,
            "missing_cell_count": missing_cell_count,
            "extraction_invoked_count": extraction_events,
            "evidence_validation_drop_count": validation_drop_count,
        },
        "most_likely_causes": [
            "Locked-cell detection treated empty cells as locked.",
            "Schema loader produced zero columns or mismatched column names.",
            "Extraction loop never ran for groups (no group targets).",
            "UI/query filtering hid proposals despite DB entries.",
        ],
    }


def _event_count(store: Store, event_type: str) -> int:
    row = store.conn.execute(
        "SELECT COUNT(*) as count FROM events WHERE event_type = ?",
        (event_type,),
    ).fetchone()
    return int(row["count"]) if row else 0


def _load_schema_columns(config_payload: dict[str, object]) -> list[str]:
    try:
        table_path = Path(str(config_payload.get("table_path", "")))
        schema_source = table_path
        if config_payload.get("schema_mode") == "separate" and config_payload.get("schema_path"):
            schema_source = Path(str(config_payload["schema_path"]))
        specs = load_schema(schema_source, str(config_payload.get("schema_sheet_name", "schema")))
    except Exception:
        return []
    return [spec.column_name for spec in specs]


def _missing_cell_count(
    store: Store,
    schema_columns: list[str],
    matched_rows: list[dict[str, object]],
) -> int:
    if not schema_columns:
        return 0
    matched_row_ids = {
        str(row.get("row_id"))
        for row in matched_rows
        if row.get("status") == "matched" and row.get("row_id") is not None
    }
    if not matched_row_ids:
        return 0
    locked_rows = store.list_locks()
    locked_map: dict[str, set[str]] = {}
    for lock in locked_rows:
        if str(lock["row_id"]) in matched_row_ids:
            locked_map.setdefault(str(lock["row_id"]), set()).add(str(lock["column"]))
    missing = 0
    for row_id in matched_row_ids:
        locked = locked_map.get(row_id, set())
        for column in schema_columns:
            if column not in locked:
                missing += 1
    return missing


def write_run_bundle(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    bundle_path = run_dir / "run_bundle.zip"
    files = [
        run_dir / "run_config.json",
        run_dir / "run_report.json",
        run_dir / "proposals.sqlite",
        run_dir / "exports" / "mapping_report.html",
        run_dir / "exports" / "pdf_row_matches.csv",
        run_dir / "exports" / "audit_log.csv",
        run_dir / "exports" / "updated_table.xlsx",
    ]
    logs_dir = run_dir / "logs"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            if path.exists():
                bundle.write(path, arcname=path.relative_to(run_dir))
        if logs_dir.exists():
            for log_path in logs_dir.glob("**/*"):
                if log_path.is_file():
                    bundle.write(log_path, arcname=log_path.relative_to(run_dir))
    return bundle_path
