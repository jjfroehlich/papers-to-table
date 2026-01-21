from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from jinja2 import Template

from paper_table_agent.store.db import Store


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


def write_mapping_report(store: Store, output_dir: Path, write_csv: bool = False) -> None:
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

    html = _REPORT_TEMPLATE.render(rows=report_rows, **summary)
    (output_dir / "mapping_report.html").write_text(html, encoding="utf-8")

    if write_csv:
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


def write_run_report(store: Store, run_paths: Path | object) -> None:
    run_dir = run_paths.run_dir if hasattr(run_paths, "run_dir") else Path(run_paths)
    config_path = run_dir / "run_config.json"
    config_payload = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    matches = [dict(row) for row in store.fetch_matches()]
    proposals = [
        dict(row)
        for row in store.conn.execute("SELECT column, status, flags_json, evidence_json FROM proposals")
    ]
    events = [dict(row) for row in store.conn.execute("SELECT level, event_type FROM events")]
    retrieval_chunks = [dict(row) for row in store.conn.execute("SELECT pdf_id FROM retrieval_chunks")]
    matched = sum(1 for row in matches if row.get("status") == "matched")
    ambiguous = sum(1 for row in matches if row.get("status") == "ambiguous")
    unmatched = sum(1 for row in matches if row.get("status") in {"unmatched", "duplicate"})
    filled = sum(1 for row in proposals if row.get("status") in {"found", "inferred"})
    total = len(proposals)
    needs_more = 0
    validation_total = 0
    validation_passed = 0
    validation_normalized = 0
    validation_reasons: dict[str, int] = {}
    highlight_attempts = 0
    highlight_success = 0
    not_found_by_column: dict[str, dict[str, float]] = {}
    for row in proposals:
        flags = json.loads(row.get("flags_json") or "{}")
        evidence_items = json.loads(row.get("evidence_json") or "[]")
        if flags.get("needs_more_evidence"):
            needs_more += 1
        mode = flags.get("validation_mode")
        if mode:
            validation_total += 1
            if mode in {"exact", "normalized"}:
                validation_passed += 1
            if mode == "normalized":
                validation_normalized += 1
        reason = flags.get("validation_reason")
        if reason:
            validation_reasons[reason] = validation_reasons.get(reason, 0) + 1
        for evidence in evidence_items:
            status = evidence.get("highlight_status")
            if status in {"highlighted", "not_found"}:
                highlight_attempts += 1
                if status == "highlighted":
                    highlight_success += 1
        column = row.get("column") or ""
        if column:
            not_found_by_column.setdefault(column, {"not_found": 0, "total": 0})
            not_found_by_column[column]["total"] += 1
            if row.get("status") == "not_found":
                not_found_by_column[column]["not_found"] += 1
    for column, stats in not_found_by_column.items():
        total_for_column = stats["total"]
        stats["rate"] = (stats["not_found"] / total_for_column) if total_for_column else 0.0
    fallback_events = {
        row["event_type"]: row["count"]
        for row in store.conn.execute(
            """
            SELECT event_type, COUNT(*) as count
            FROM events
            WHERE event_type IN ('embedding_fallback', 'reranker_fallback')
            GROUP BY event_type
            """
        )
    }
    fallback_mode = "bm25_only" if fallback_events.get("embedding_fallback") else None
    summary = {
        "mapping": {
            "matched": matched,
            "ambiguous": ambiguous,
            "unmatched": unmatched,
            "total": len(matches),
            "ambiguous_rate": (ambiguous / len(matches)) if matches else 0.0,
        },
        "retrieval": {
            "config": config_payload.get("retrieval", {}),
            "chunk_count": len(retrieval_chunks),
            "fallbacks": fallback_events,
            "fallback_mode": fallback_mode,
        },
        "extraction": {
            "total_proposals": total,
            "filled": filled,
            "fill_rate": (filled / total) if total else 0.0,
            "needs_more_evidence": needs_more,
            "evidence_validation": {
                "total": validation_total,
                "passed": validation_passed,
                "pass_rate": (validation_passed / validation_total) if validation_total else 0.0,
                "normalized_used": validation_normalized,
                "reasons": validation_reasons,
            },
            "highlight": {
                "attempted": highlight_attempts,
                "success": highlight_success,
                "success_rate": (highlight_success / highlight_attempts) if highlight_attempts else 0.0,
            },
            "not_found_by_column": not_found_by_column,
        },
        "errors": {
            "total_events": len(events),
            "error_events": sum(1 for row in events if row.get("level") == "error"),
        },
    }
    payload = {
        "run_config": config_payload,
        "summary": summary,
        "artifacts": {
            "run_dir": str(run_dir),
            "exports_dir": str(run_dir / "exports"),
            "artifacts_dir": str(run_dir / "artifacts"),
            "logs_dir": str(run_dir / "logs"),
            "db_path": str(run_dir / "proposals.sqlite"),
            "mapping_report": str(run_dir / "exports" / "mapping_report.html"),
        },
    }
    (run_dir / "run_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
