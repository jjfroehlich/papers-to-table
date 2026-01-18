from __future__ import annotations

import csv
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
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background-color: #f4f4f4; }
  </style>
</head>
<body>
  <h1>Mapping Report</h1>
  <p>Matched: {{ matched }} | Ambiguous: {{ ambiguous }} | Duplicates: {{ duplicates }} | Failed: {{ failed }}</p>
  <table>
    <thead>
      <tr>
        <th>PDF ID</th>
        <th>Row ID</th>
        <th>Status</th>
        <th>Confidence</th>
        <th>Title</th>
        <th>Authors</th>
        <th>Year</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.pdf_id }}</td>
        <td>{{ row.row_id }}</td>
        <td>{{ row.status }}</td>
        <td>{{ row.confidence }}</td>
        <td>{{ row.title }}</td>
        <td>{{ row.authors }}</td>
        <td>{{ row.year }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""
)


def write_mapping_report(store: Store, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    matches = store.fetch_matches()
    rows = {row["row_id"]: row for row in store.fetch_rows()}
    report_rows = []
    for match in matches:
        row = rows.get(match["row_id"], {})
        report_rows.append(
            {
                "pdf_id": match["pdf_id"],
                "row_id": match["row_id"],
                "status": match["status"],
                "confidence": match["confidence"],
                "title": row.get("title", ""),
                "authors": row.get("authors", ""),
                "year": row.get("year", ""),
            }
        )

    summary = {
        "matched": sum(1 for match in matches if match["status"] == "matched"),
        "ambiguous": sum(1 for match in matches if match["status"] not in {"matched", "duplicate"}),
        "duplicates": sum(1 for match in matches if match["status"] == "duplicate"),
        "failed": 0,
    }

    html = _REPORT_TEMPLATE.render(rows=report_rows, **summary)
    (output_dir / "mapping_report.html").write_text(html, encoding="utf-8")

    with (output_dir / "pdf_row_matches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pdf_id", "row_id", "status", "confidence", "title", "authors", "year"])
        for row in report_rows:
            writer.writerow(
                [
                    row["pdf_id"],
                    row["row_id"],
                    row["status"],
                    row["confidence"],
                    row["title"],
                    row["authors"],
                    row["year"],
                ]
            )
