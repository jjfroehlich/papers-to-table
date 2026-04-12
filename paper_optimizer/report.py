from __future__ import annotations

import base64
import csv
import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from .utils import read_json


_REPORT_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4efe4;
      --card: #fffaf2;
      --ink: #1c2b2d;
      --muted: #657476;
      --line: #d8cdb8;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
      --good: #166534;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Georgia, "Iowan Old Style", serif; background: linear-gradient(180deg, #f8f3e9 0%, var(--bg) 100%); color: var(--ink); }
    main { max-width: 1400px; margin: 0 auto; padding: 24px; }
    h1, h2, h3 { margin: 0 0 12px; font-weight: 700; }
    p, li, td, th { line-height: 1.4; }
    section { margin: 20px 0; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px; box-shadow: 0 10px 30px rgba(28, 43, 45, 0.05); }
    .label { color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .value { font-size: 1.4rem; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 16px; overflow: hidden; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #efe4cf; font-size: 0.85rem; }
    .muted { color: var(--muted); }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.78rem; background: #e9ddc6; }
    .pill.good { color: var(--good); }
    .pill.bad { color: var(--bad); }
    .pill.warn { color: var(--warn); }
    .plot { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 12px; }
    .plot img { width: 100%; height: auto; display: block; border-radius: 12px; }
    a { color: var(--accent); }
    ul { margin: 8px 0 0; padding-left: 20px; }
    @media (max-width: 700px) {
      main { padding: 16px; }
      th, td { font-size: 0.85rem; }
    }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>{{ title }}</h1>
      <div class="grid">
        {% for item in header_items %}
        <div>
          <div class="label">{{ item.label }}</div>
          <div>{{ item.value }}</div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section>
      <h2>Summary Cards</h2>
      <div class="grid">
        {% for item in summary_cards %}
        <div class="card">
          <div class="label">{{ item.label }}</div>
          <div class="value">{{ item.value }}</div>
          {% if item.note %}<div class="muted">{{ item.note }}</div>{% endif %}
        </div>
        {% endfor %}
      </div>
    </section>

    <section>
      <h2>Candidate Overview</h2>
      <table>
        <thead>
          <tr>
            {% for heading in candidate_headings %}<th>{{ heading }}</th>{% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for row in candidate_rows %}
          <tr>
            {% for key in candidate_keys %}
            <td>{{ row.get(key, "") }}</td>
            {% endfor %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Provenance</h2>
        <ul>
          {% for item in provenance_items %}<li>{{ item }}</li>{% endfor %}
        </ul>
      </div>
      <div class="card">
        <h2>Decision</h2>
        <ul>
          {% for item in decision_items %}<li>{{ item }}</li>{% endfor %}
        </ul>
      </div>
    </section>

    <section class="card">
      <h2>Diagnostics Highlights</h2>
      <ul>
        {% for item in diagnostics_items %}<li>{{ item }}</li>{% endfor %}
      </ul>
    </section>

    <section>
      <h2>Plots</h2>
      <div class="grid">
        {% for plot in plots %}
        <div class="plot">
          <h3>{{ plot.title }}</h3>
          {% if plot.csv_href %}<div class="muted"><a href="{{ plot.csv_href }}">CSV</a></div>{% endif %}
          {% if plot.image_data_uri %}<img src="{{ plot.image_data_uri }}" alt="{{ plot.title }}">{% else %}<div class="muted">No image generated.</div>{% endif %}
        </div>
        {% endfor %}
      </div>
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


def _image_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _title_from_stem(stem: str) -> str:
    return stem.replace("_", " ").strip().title()


def _sortable_score(value: Any) -> float:
  try:
    if value in (None, ""):
      return float("-inf")
    return float(value)
  except (TypeError, ValueError):
    return float("-inf")


def generate_experiment_report(experiment_dir: Path) -> Path | None:
    experiment_json = _load_json_if_exists(experiment_dir / "experiment.json")
    if not experiment_json:
        return None
    summary = _load_json_if_exists(experiment_dir / "summary.json")
    compare_summary = _load_json_if_exists(experiment_dir / "compare_summary.json")
    best_candidate = _load_json_if_exists(experiment_dir / "best_candidate.json")
    candidate_diagnostics = _load_json_if_exists(experiment_dir / "candidate_diagnostics.json")
    run_metadata = _load_json_if_exists(experiment_dir.parent / "run_metadata.json")
    results_rows = _load_csv_rows(experiment_dir / "results" / "results.csv")
    candidate_rows = candidate_diagnostics.get("rows", []) if isinstance(candidate_diagnostics.get("rows"), list) else []
    candidate_rows = sorted(
        candidate_rows,
        key=lambda row: (
            row.get("score_status") != "scored",
        -_sortable_score(row.get("primary_metric_value")),
        ),
    ) if candidate_rows else results_rows

    primary_metric = summary.get("primary_metric") or compare_summary.get("primary_metric") or "correctness"
    holdout = summary.get("holdout_validation", {}) if isinstance(summary.get("holdout_validation"), dict) else {}
    header_items = [
        {"label": "Experiment Id", "value": experiment_json.get("experiment_id")},
        {"label": "Study Type", "value": experiment_json.get("study_type")},
        {"label": "Timestamp", "value": run_metadata.get("started_at") or run_metadata.get("timestamp") or ""},
        {"label": "Config Path", "value": run_metadata.get("config_path") or ""},
        {"label": "Benchmark Split", "value": summary.get("benchmark_id") or experiment_json.get("benchmark_id")},
        {"label": "Holdout", "value": holdout.get("status") or ("completed" if holdout.get("ran") else "not_run")},
    ]

    summary_cards = [
        {"label": "Winner / Incumbent", "value": summary.get("winner_candidate_id") or summary.get("current_best_candidate_id") or best_candidate.get("candidate_id") or "n/a", "note": None},
        {"label": "Baseline", "value": "cand_0000", "note": None},
        {"label": "Promoted", "value": "yes" if summary.get("winner_candidate_id") or summary.get("current_best_candidate_id") else "no", "note": None},
        {"label": "Best Dev Score", "value": summary.get("current_best_score") or best_candidate.get("primary_metric_value") or "n/a", "note": primary_metric},
        {"label": "Holdout Score", "value": holdout.get("score") or "n/a", "note": holdout.get("status")},
        {"label": "Judge Disagreement", "value": summary.get("judge_disagreement") or "n/a", "note": "dual-judge"},
    ]

    candidate_keys = [
        "candidate_id",
        "score_status",
        "primary_metric_value",
        "unscored_reason",
        "text_model_id",
        "prompt_bundle_id",
        "retrieval_mode",
        "retrieval_top_k",
        "main_structured_output_mode",
    ]
    candidate_headings = [
        "Candidate",
        "Status",
        f"{primary_metric}",
        "Unscored Reason",
        "Text Model",
        "Prompt Bundle",
        "Retrieval Mode",
        "Retrieval Top K",
        "Structured Output",
    ]

    provenance_items = []
    if best_candidate:
        provenance_items.append(f"text model: {best_candidate.get('text_model_id')}")
        provenance_items.append(f"prompt bundle: {best_candidate.get('prompt_bundle_id')}")
    if candidate_rows:
        top = candidate_rows[0]
        provenance_items.append(f"retrieval.mode: {top.get('retrieval_mode', '')}")
        provenance_items.append(f"retrieval.top_k: {top.get('retrieval_top_k', '')}")
        provenance_items.append(f"structured_output_mode: {top.get('main_structured_output_mode', '')}")
        provenance_items.append(f"degraded prompt-only: {top.get('prompt_only_degraded_mode_used', '')}")

    decision_items = []
    if compare_summary.get("winner"):
        decision_items.append(f"winner: {compare_summary['winner'].get('candidate_id')}")
    if isinstance(summary.get("promotion_history"), list):
        for entry in summary.get("promotion_history", [])[:8]:
            decision_items.append(
                f"round {entry.get('round_index')}: promoted={entry.get('promoted_candidate_id') or 'none'} notes={', '.join(entry.get('decision_notes', []))}"
            )
    if not decision_items:
        decision_items.append("No promotion history recorded.")

    diagnostics_items = []
    if holdout.get("status") in {"not_run", "skipped", "failed"}:
        diagnostics_items.append(f"holdout status: {holdout.get('status')} ({holdout.get('skip_reason') or 'no extra reason'})")
    if any(str(row.get("unscored_reason", "")).strip() for row in candidate_rows):
        diagnostics_items.append("One or more candidates were unscored; see the candidate overview table for explicit reasons.")
    if any(row.get("missing_proposal_count") not in (None, "", 0, "0") for row in candidate_rows):
        diagnostics_items.append("Missing-proposal diagnostics are present in at least one candidate.")
    if any(row.get("judge_disagreement") not in (None, "", 0, "0", 0.0, "0.0") for row in candidate_rows):
        diagnostics_items.append("Judge disagreement outliers detected.")
    if not diagnostics_items:
        diagnostics_items.append("No major diagnostics highlights recorded.")

    plots: list[dict[str, str | None]] = []
    plots_dir = experiment_dir / "plots"
    for png_path in sorted(plots_dir.glob("*.png")):
        stem = png_path.stem
        csv_path = plots_dir / f"{stem}.csv"
        plots.append(
            {
                "title": _title_from_stem(stem),
                "csv_href": f"plots/{csv_path.name}" if csv_path.exists() else None,
                "image_data_uri": _image_data_uri(png_path),
            }
        )

    report_html = _REPORT_TEMPLATE.render(
        title=f"{experiment_json.get('experiment_id')} report",
        header_items=header_items,
        summary_cards=summary_cards,
        candidate_headings=candidate_headings,
        candidate_keys=candidate_keys,
        candidate_rows=candidate_rows,
        provenance_items=provenance_items,
        decision_items=decision_items,
        diagnostics_items=diagnostics_items,
        plots=plots,
    )
    report_path = experiment_dir / "report.html"
    report_path.write_text(report_html, encoding="utf-8")
    return report_path