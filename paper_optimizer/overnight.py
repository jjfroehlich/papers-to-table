from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from jinja2 import Template

from .utils import read_json, write_json


_OVERNIGHT_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body { margin: 0; font-family: Georgia, "Iowan Old Style", serif; background: #f7f1e6; color: #203033; }
    main { max-width: 1380px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
    .card { background: #fffaf2; border: 1px solid #dbcdb8; border-radius: 16px; padding: 16px; }
    h1, h2, h3 { margin: 0 0 12px; }
    table { width: 100%; border-collapse: collapse; background: #fffaf2; border-radius: 16px; overflow: hidden; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #dbcdb8; text-align: left; vertical-align: top; }
    th { background: #efe3cf; }
    .muted { color: #667577; }
    a { color: #0f766e; }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>{{ title }}</h1>
      <div class="grid">
        {% for item in header_items %}
        <div>
          <div class="muted">{{ item.label }}</div>
          <div>{{ item.value }}</div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section>
      <h2>Pipeline Stages</h2>
      <div class="grid">
        {% for stage in stages %}
        <div class="card">
          <h3>{{ stage.stage_name }}</h3>
          <div>Study: {{ stage.study_type }}</div>
          <div>Winner: {{ stage.winner_candidate_id or 'n/a' }}</div>
          <div>Best Score: {{ stage.best_score }}</div>
          <div>Holdout: {{ stage.holdout_status }}</div>
          <div class="muted"><a href="{{ stage.report_href }}">Experiment report</a></div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section class="card">
      <h2>Trajectory</h2>
      <table>
        <thead>
          <tr>
            <th>Stage</th>
            <th>Winner</th>
            <th>Prompt</th>
            <th>Model</th>
            <th>Retrieval</th>
            <th>Score</th>
            <th>Holdout</th>
          </tr>
        </thead>
        <tbody>
          {% for stage in stages %}
          <tr>
            <td>{{ stage.stage_name }}</td>
            <td>{{ stage.winner_candidate_id or '' }}</td>
            <td>{{ stage.winner_prompt_bundle_id or '' }}</td>
            <td>{{ stage.winner_text_model_id or '' }}</td>
            <td>{{ stage.winner_retrieval_mode or '' }} / {{ stage.winner_retrieval_top_k or '' }}</td>
            <td>{{ stage.best_score }}</td>
            <td>{{ stage.holdout_status }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>All Candidates</h2>
      <div class="muted"><a href="all_candidates.csv">CSV</a></div>
      <table>
        <thead>
          <tr>
            {% for heading in candidate_headings %}<th>{{ heading }}</th>{% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for row in candidate_rows %}
          <tr>
            {% for key in candidate_keys %}<td>{{ row.get(key, '') }}</td>{% endfor %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
)


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _relative_href(target: Path, *, base_dir: Path) -> str:
  return os.path.relpath(target.resolve(), start=base_dir.resolve()).replace("\\", "/")


def _normalized_candidate_rows(stage_name: str, run_root: Path) -> list[dict[str, Any]]:
    experiment_dir = run_root / "experiment"
    rows = _load_csv_rows(experiment_dir / "results" / "results.csv")
    return [
        {
            "stage_name": stage_name,
            "run_name": run_root.name,
            "study_type": row.get("study_type"),
            "candidate_id": row.get("candidate_id"),
            "parent_candidate_id": row.get("parent_candidate_id"),
            "text_model_id": row.get("text_model_id"),
            "prompt_bundle_id": row.get("prompt_bundle_id"),
            "retrieval_mode": row.get("retrieval_mode"),
            "retrieval_top_k": row.get("retrieval_top_k"),
            "whole_document_mode": row.get("whole_document_mode"),
            "whole_document_max_chars": row.get("whole_document_max_chars"),
            "structured_output_mode": row.get("structured_output_mode"),
            "prompt_only_degraded_mode_used": row.get("prompt_only_degraded_mode_used"),
            "score_status": row.get("score_status"),
            "scored": row.get("scored"),
            "unscored_reason": row.get("unscored_reason"),
            "unscored_reason_detail": row.get("unscored_reason_detail"),
            "primary_score": row.get("primary.correctness") or row.get("primary.correctness_mean"),
            "correctness_judge_a": row.get("primary.correctness_judge_a") or row.get("diagnostic.correctness_judge_a"),
            "correctness_judge_b": row.get("primary.correctness_judge_b") or row.get("diagnostic.correctness_judge_b"),
            "runtime_seconds": row.get("runtime_seconds"),
            "promotion_decision": row.get("promotion_decision"),
            "decision_reason": row.get("decision_reason"),
        }
        for row in rows
    ]


def generate_overnight_report(manifest_path: Path) -> Path:
    manifest = read_json(manifest_path)
    output_dir = manifest_path.parent
    stages_payload = manifest.get("stages", []) if isinstance(manifest.get("stages"), list) else []

    all_candidate_rows: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    for stage in stages_payload:
        stage_name = str(stage.get("stage_name") or "stage")
        run_root = Path(str(stage.get("run_root")))
        experiment_dir = run_root / "experiment"
        summary = _load_json_if_exists(experiment_dir / "summary.json")
        best_candidate = _load_json_if_exists(experiment_dir / "best_candidate.json")
        holdout = summary.get("holdout_validation", {}) if isinstance(summary.get("holdout_validation"), dict) else {}
        stage_rows.append(
            {
                "stage_name": stage_name,
                "study_type": summary.get("study_type") or best_candidate.get("study_type") or "",
                "winner_candidate_id": best_candidate.get("candidate_id") or summary.get("winner_candidate_id") or summary.get("current_best_candidate_id"),
                "winner_prompt_bundle_id": best_candidate.get("prompt_bundle_id") or summary.get("winner_prompt_bundle_id") or summary.get("current_best_prompt_bundle_id"),
                "winner_text_model_id": best_candidate.get("text_model_id") or summary.get("winner_text_model_id") or summary.get("current_best_text_model_id"),
                "winner_retrieval_mode": best_candidate.get("retrieval_mode"),
                "winner_retrieval_top_k": best_candidate.get("retrieval_top_k"),
                "best_score": best_candidate.get("primary_metric_value") or summary.get("current_best_score") or "n/a",
                "holdout_status": holdout.get("status") or ("completed" if holdout.get("ran") else "not_run"),
                "report_href": _relative_href(experiment_dir / "report.html", base_dir=output_dir),
            }
        )
        all_candidate_rows.extend(_normalized_candidate_rows(stage_name, run_root))

    _write_csv(output_dir / "all_candidates.csv", all_candidate_rows)
    write_json(output_dir / "all_candidates.json", all_candidate_rows)

    candidate_keys = [
        "stage_name",
        "candidate_id",
        "text_model_id",
        "prompt_bundle_id",
        "retrieval_mode",
        "retrieval_top_k",
        "score_status",
        "unscored_reason",
        "primary_score",
        "runtime_seconds",
        "promotion_decision",
        "decision_reason",
    ]
    candidate_headings = [
        "Stage",
        "Candidate",
        "Text Model",
        "Prompt Bundle",
        "Retrieval Mode",
        "Top K",
        "Score Status",
        "Unscored Reason",
        "Primary Score",
        "Runtime",
        "Decision",
        "Decision Reason",
    ]

    report_html = _OVERNIGHT_TEMPLATE.render(
        title=f"{manifest.get('label') or manifest.get('session_id') or 'overnight'} report",
        header_items=[
            {"label": "Session Id", "value": manifest.get("session_id")},
            {"label": "Label", "value": manifest.get("label")},
            {"label": "Stage Count", "value": len(stage_rows)},
            {"label": "Candidate Count", "value": len(all_candidate_rows)},
        ],
        stages=stage_rows,
        candidate_keys=candidate_keys,
        candidate_headings=candidate_headings,
        candidate_rows=all_candidate_rows,
    )
    report_path = output_dir / "report.html"
    report_path.write_text(report_html, encoding="utf-8")
    return report_path