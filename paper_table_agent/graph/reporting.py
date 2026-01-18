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
      {% if row.candidates %}
      <tr>
        <td colspan=\"7\">
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


def write_mapping_report(store: Store, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    matches = store.fetch_matches()
    rows = {row["row_id"]: dict(row) for row in store.fetch_rows()}
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
        report_rows.append(
            {
                "pdf_id": match["pdf_id"],
                "row_id": match["row_id"],
                "status": match["status"],
                "confidence": match["confidence"],
                "title": row.get("title", ""),
                "authors": row.get("authors", ""),
                "year": row.get("year", ""),
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
