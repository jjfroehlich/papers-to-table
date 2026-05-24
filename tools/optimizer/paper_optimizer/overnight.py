from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from .report_templates import render_template
from .reporting import (
    build_plot_guidance,
    build_table_cell,
    display_text,
    format_delta,
    format_percent,
    format_runtime,
    format_score,
    image_data_uri,
    is_missing,
    load_csv_rows,
    load_json_if_exists,
    merge_candidate_rows,
    model_nickname,
    parse_bool,
    relative_href,
    safe_float,
    sort_candidates,
    status_counts,
    status_label,
    status_tone,
    study_variant,
)
from .utils import read_json, write_json


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


def _seconds_to_minutes(seconds: float) -> float:
    return seconds / 60.0


def _short_plot_label(label: Any, *, max_len: int = 34) -> str:
    text = str(label or "").strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}..."


def _annotate_points(xs: list[float], ys: list[float], labels: list[str]) -> None:
    for index, (x_value, y_value, label) in enumerate(zip(xs, ys, labels, strict=True)):
        x_offset = 5 if index % 2 == 0 else -5
        y_offset = 5 if index % 3 != 0 else -8
        ha = "left" if x_offset > 0 else "right"
        plt.annotate(
            _short_plot_label(label),
            (x_value, y_value),
            textcoords="offset points",
            xytext=(x_offset, y_offset),
            ha=ha,
            fontsize=7,
            color="#334155",
        )


def _winner_id(summary: dict[str, Any], best_candidate: dict[str, Any], compare_summary: dict[str, Any]) -> str | None:
    winner = compare_summary.get("winner") if isinstance(compare_summary.get("winner"), dict) else {}
    return (
        summary.get("eligible_winner_candidate_id")
        or summary.get("winner_candidate_id")
        or best_candidate.get("candidate_id")
        or summary.get("current_best_candidate_id")
        or summary.get("best_raw_candidate_id")
        or winner.get("candidate_id")
    )


def _winner_row(rows: list[dict[str, Any]], winner_id: str | None) -> dict[str, Any] | None:
    if not winner_id:
        return None
    return next((row for row in rows if row.get("candidate_id") == winner_id), None)


def _stage_change(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "First stage in the pipeline."
    changes: list[str] = []
    for label, key in [
        ("model", "text_model_id"),
        ("prompt", "prompt_bundle_id"),
        ("retrieval mode", "retrieval_mode"),
        ("retrieval top_k", "retrieval_top_k"),
    ]:
        before = previous.get(key)
        after = current.get(key)
        if before != after and (not is_missing(before) or not is_missing(after)):
            changes.append(f"{label}: {display_text(before, missing='—')} -> {display_text(after, missing='—')}")
    if not changes:
        return "No winner-configuration change; this stage mostly validated the earlier recommendation."
    return "; ".join(changes)


def _stage_duration(rows: list[dict[str, Any]]) -> float | None:
    durations = [safe_float(row.get("runtime_seconds")) for row in rows]
    numeric = [value for value in durations if value is not None]
    if not numeric:
        return None
    return sum(numeric)


def _save_plot(path: Path) -> None:
    plt.savefig(path)
    if path.suffix.casefold() == ".png":
        plt.savefig(path.with_suffix(".pdf"))


def _main_conclusion(stage_rows: list[dict[str, Any]]) -> str:
    if not stage_rows:
        return "No stages were recorded in the overnight manifest."
    numeric_scores = [row for row in stage_rows if row.get("best_score") is not None]
    if not numeric_scores:
        final = stage_rows[-1]
        return (
            f"{len(stage_rows)} stages completed, but none recorded a numeric winner score. "
            f"Final stage '{final['stage_name']}' ended with winner {display_text(final.get('winner_model_name'), missing=display_text(final.get('winner_candidate_id'), missing='not recorded'))} "
            f"and status {display_text(final.get('winner_score_status'), missing='unknown')}."
        )
    best_stage = max(numeric_scores, key=lambda row: row["best_score"])
    final_stage = stage_rows[-1]
    biggest_gain_stage = None
    biggest_gain = None
    previous_score = None
    for stage in stage_rows:
        score = stage.get("best_score")
        if score is None:
            continue
        if previous_score is None:
            previous_score = score
            continue
        delta = score - previous_score
        if biggest_gain is None or delta > biggest_gain:
            biggest_gain = delta
            biggest_gain_stage = stage
        previous_score = score
    conclusion = (
        f"Across {len(stage_rows)} stages, the strongest score came from '{best_stage['stage_name']}' with "
        f"winner {display_text(best_stage.get('winner_model_name'), missing=display_text(best_stage.get('winner_candidate_id'), missing='not recorded'))} at {format_score(best_stage.get('best_score'))}."
    )
    if len(stage_rows) > 1:
        previous_final = stage_rows[-2].get("best_score")
        final_score = final_stage.get("best_score")
        if final_score is not None and previous_final is not None and final_score > previous_final:
            conclusion += f" The final stage improved the score by {format_delta(final_score - previous_final)} over the preceding stage."
        else:
            conclusion += " The final stage mainly validated an earlier winner rather than extending the score frontier."
    if biggest_gain_stage is not None and biggest_gain is not None and biggest_gain > 0:
        conclusion += f" The biggest stage-to-stage gain came in '{biggest_gain_stage['stage_name']}' ({format_delta(biggest_gain)})."
    return conclusion


def _build_caveats(stage_rows: list[dict[str, Any]], all_candidate_rows: list[dict[str, Any]]) -> list[str]:
    caveats: list[str] = []
    counts = status_counts(all_candidate_rows)
    dual_judge_completed = any(row.get("dual_judge_completed") for row in all_candidate_rows)
    dual_judge_incomplete_only = any(row.get("dual_judge_completed") is False for row in all_candidate_rows) and not dual_judge_completed
    if counts.get("scored_degraded", 0):
        caveats.append(f"{counts['scored_degraded']} pipeline candidates scored only in degraded mode.")
    if counts.get("unscored", 0):
        caveats.append(f"{counts['unscored']} pipeline candidates were unscored.")
    if counts.get("failed", 0):
        caveats.append(f"{counts['failed']} pipeline candidates failed before scoring.")
    if dual_judge_incomplete_only:
        caveats.append("Dual-judge comparison was not recorded across the pipeline candidates.")
    if not caveats:
        caveats.append("No major overnight trust caveats were recorded.")
    return caveats


def _trust_note(row: dict[str, Any]) -> str:
    notes: list[str] = []
    if parse_bool(row.get("prompt_only_degraded_mode_used")):
        notes.append("prompt-only degraded")
    if parse_bool(row.get("extraction_contract_valid")) is False:
        notes.append("contract invalid")
    if safe_float(row.get("anchor_valid_rate")) == 0 and (row.get("evidence_item_count") or 0):
        notes.append("zero grounded evidence")
    if row.get("dual_judge_completed"):
        notes.append(f"dual_judge disagreement={format_percent(row.get('judge_disagreement_rate'), missing='0.0%')}")
    elif row.get("dual_judge_completed") is False:
        notes.append("dual_judge incomplete")
    return "; ".join(notes) if notes else "healthy"


def _build_next_checks(stage_rows: list[dict[str, Any]], all_candidate_rows: list[dict[str, Any]]) -> list[str]:
    checks: list[str] = []
    counts = status_counts(all_candidate_rows)
    if counts.get("unscored", 0):
        checks.append("Inspect unscored candidates in the stage where they occurred to see whether the issue is systematic.")
    retrieval_stage = next((stage for stage in stage_rows if "retrieval" in str(stage.get("variant") or "")), None)
    if retrieval_stage is not None:
        checks.append("Review the retrieval stage frontier to confirm the winning top_k is stable enough for production defaults.")
    optimize_stage = next((stage for stage in stage_rows if stage.get("study_type") == "optimize"), None)
    if optimize_stage is not None:
        checks.append("Review optimize plateau behavior to decide whether search bounds or tie policy should change.")
    if not checks:
        checks.append("No urgent overnight follow-up stands out from the recorded evidence.")
    return checks[:4]


def _build_stage_rows(manifest_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = read_json(manifest_path)
    stage_payloads = manifest.get("stages", []) if isinstance(manifest.get("stages"), list) else []
    stage_rows: list[dict[str, Any]] = []
    all_candidate_rows: list[dict[str, Any]] = []
    previous_winner: dict[str, Any] | None = None

    for index, payload in enumerate(stage_payloads, start=1):
        stage_name = display_text(payload.get("stage_name"), missing=f"stage_{index}")
        run_root = Path(str(payload.get("run_root")))
        experiment_dir = run_root / "experiment"
        experiment_json = load_json_if_exists(experiment_dir / "experiment.json")
        summary = load_json_if_exists(experiment_dir / "summary.json")
        compare_summary = load_json_if_exists(experiment_dir / "compare_summary.json")
        best_candidate = load_json_if_exists(experiment_dir / "best_candidate.json")
        candidate_diagnostics = load_json_if_exists(experiment_dir / "candidate_diagnostics.json")
        primary_metric = str(summary.get("primary_metric") or compare_summary.get("primary_metric") or "content_correctness")
        results_rows = load_csv_rows(experiment_dir / "results" / "results.csv")
        diagnostics_rows = candidate_diagnostics.get("rows", []) if isinstance(candidate_diagnostics.get("rows"), list) else []
        candidate_rows = merge_candidate_rows(results_rows, diagnostics_rows, primary_metric=primary_metric)
        candidate_rows = sort_candidates(candidate_rows)

        study_type = str(experiment_json.get("study_type") or summary.get("study_type") or "unknown")
        variant = study_variant(candidate_rows, study_type, experiment_id=str(experiment_json.get("experiment_id") or ""))
        winner_id = _winner_id(summary, best_candidate, compare_summary)
        winner_row = _winner_row(candidate_rows, winner_id)
        winner_score = winner_row.get("primary_metric_value") if winner_row else None
        change = _stage_change(previous_winner, winner_row or {})
        counts = status_counts(candidate_rows)
        duration_seconds = _stage_duration(candidate_rows)
        stage_row = {
            "stage_index": index,
            "stage_name": stage_name,
            "study_type": study_type,
            "variant": variant,
            "winner_candidate_id": winner_id,
            "winner_model_name": model_nickname(winner_row.get("text_model_id")) if winner_row else None,
            "winner_score_status": winner_row.get("score_status") if winner_row else None,
            "winner_unscored_reason": winner_row.get("unscored_reason") if winner_row else None,
            "winner_prompt_bundle_id": winner_row.get("prompt_bundle_id") if winner_row else best_candidate.get("prompt_bundle_id"),
            "winner_text_model_id": winner_row.get("text_model_id") if winner_row else best_candidate.get("text_model_id"),
            "winner_retrieval_mode": winner_row.get("retrieval_mode") if winner_row else None,
            "winner_retrieval_top_k": winner_row.get("retrieval_top_k") if winner_row else None,
            "winner_structured_output_mode": winner_row.get("structured_output_mode") if winner_row else None,
            "best_score": winner_score,
            "candidate_count": len(candidate_rows),
            "score_counts": counts,
            "duration_seconds": duration_seconds,
            "change": change,
            "report_href": relative_href(experiment_dir / "report.html", base_dir=manifest_path.parent) if (experiment_dir / "report.html").exists() else None,
            "summary": (
                f"Winner {display_text(model_nickname(winner_row.get('text_model_id')) if winner_row else None, missing=display_text(winner_id, missing='not recorded'))} finished with {format_score(winner_score)} and status "
                f"{status_label(display_text(winner_row.get('score_status') if winner_row else None, missing='unknown'))}."
            ),
        }
        for row in candidate_rows:
            enriched = dict(row)
            enriched["stage_name"] = stage_name
            enriched["stage_index"] = index
            enriched["stage_study_type"] = study_type
            enriched["stage_variant"] = variant
            enriched["winner_candidate"] = row.get("candidate_id") == winner_id
            all_candidate_rows.append(enriched)

        stage_rows.append(stage_row)
        previous_winner = winner_row

    return stage_rows, all_candidate_rows


def _stage_cards(stage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    previous_score = None
    for stage in stage_rows:
        score = stage.get("best_score")
        delta = None if previous_score is None or score is None else score - previous_score
        previous_score = score if score is not None else previous_score
        cards.append(
            {
                "stage_name": stage["stage_name"],
                "stage_type": stage["study_type"],
                "summary": stage["summary"],
                "badges": [
                    {"text": stage["variant"].replace("_", " "), "tone": "neutral"},
                    {"text": status_label(display_text(stage.get("winner_score_status"), missing="unknown")), "tone": status_tone(display_text(stage.get("winner_score_status"), missing="unknown"))},
                ],
                "metrics": [
                    {"label": "Winner", "value": display_text(stage.get("winner_model_name"), missing=display_text(stage.get("winner_candidate_id"), missing="not recorded"))},
                    {"label": "Best Score", "value": format_score(stage.get("best_score"))},
                    {"label": "Candidates", "value": str(stage.get("candidate_count") or 0)},
                    {"label": "Duration", "value": format_runtime(stage.get("duration_seconds"))},
                ],
                "change": stage.get("change"),
                "report_href": stage.get("report_href"),
            }
        )
    return cards


def _build_stage_table(stage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = [
        {"label": "Stage", "align": "left", "sort": "string"},
        {"label": "Study", "align": "left", "sort": "string"},
        {"label": "Winner", "align": "left", "sort": "string"},
        {"label": "Best Score", "align": "right", "sort": "number"},
        {"label": "Delta", "align": "right", "sort": "number"},
        {"label": "What Changed", "align": "left", "sort": "string"},
        {"label": "Status Mix", "align": "left", "sort": "string"},
    ]
    rows: list[dict[str, Any]] = []
    previous_score = None
    for stage in stage_rows:
        score = stage.get("best_score")
        delta = None if previous_score is None or score is None else score - previous_score
        previous_score = score if score is not None else previous_score
        rows.append(
            {
                "cells": [
                    build_table_cell(stage["stage_name"], subtext=display_text(stage.get("variant"), missing="not recorded")),
                    build_table_cell(display_text(stage.get("study_type"), missing="not recorded")),
                    build_table_cell(display_text(stage.get("winner_model_name"), missing="not recorded"), subtext=display_text(stage.get("winner_candidate_id"), missing="not recorded")),
                    build_table_cell(format_score(stage.get("best_score")), sort_value=stage.get("best_score") if stage.get("best_score") is not None else -1),
                    build_table_cell(format_delta(delta, missing="—"), sort_value=delta if delta is not None else -9999),
                    build_table_cell(display_text(stage.get("change"), missing="not recorded")),
                    build_table_cell(
                        _status_mix_text(stage.get("score_counts") or {}),
                        badge=display_text(stage.get("winner_score_status"), missing="unknown"),
                        tone=status_tone(display_text(stage.get("winner_score_status"), missing="unknown")),
                    ),
                ]
            }
        )
    return {
        "title": "Stage Decision Table",
        "subtitle": "Each row explains the winner, score movement, and whether the stage changed the winning configuration.",
        "columns": columns,
        "rows": rows,
        "links": [],
    }


def _status_mix_text(counts: dict[str, int]) -> str:
    return (
        f"{counts.get('scored', 0)} scored, "
        f"{counts.get('scored_degraded', 0)} degraded, "
        f"{counts.get('unscored', 0)} unscored, "
        f"{counts.get('failed', 0)} failed"
    )


def _build_candidate_table(all_candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = [
        {"label": "Stage", "align": "left", "sort": "string"},
        {"label": "Candidate", "align": "left", "sort": "string"},
        {"label": "Score", "align": "right", "sort": "number"},
        {"label": "Status", "align": "left", "sort": "string"},
        {"label": "Runtime", "align": "right", "sort": "number"},
        {"label": "Model / Prompt", "align": "left", "sort": "string"},
        {"label": "Retrieval", "align": "left", "sort": "string"},
        {"label": "Structure", "align": "left", "sort": "string"},
        {"label": "Reason", "align": "left", "sort": "string"},
    ]
    rows: list[dict[str, Any]] = []
    for row in all_candidate_rows:
        rows.append(
            {
                "cells": [
                    build_table_cell(display_text(row.get("stage_name"), missing="not recorded"), subtext=display_text(row.get("stage_study_type"), missing="not recorded")),
                    build_table_cell(model_nickname(row.get("text_model_id")), subtext=f"{display_text(row.get('candidate_id'), missing='not recorded')} · {'winner' if row.get('winner_candidate') else display_text(row.get('prompt_bundle_id'), missing='prompt not recorded')}"),
                    build_table_cell(format_score(row.get("primary_metric_value")), sort_value=row.get("primary_metric_value") if row.get("primary_metric_value") is not None else -1),
                    build_table_cell(status_label(display_text(row.get("score_status"), missing="unknown")), badge=status_label(display_text(row.get("score_status"), missing="unknown")), tone=status_tone(display_text(row.get("score_status"), missing="unknown"))),
                    build_table_cell(format_runtime(row.get("runtime_seconds")), sort_value=row.get("runtime_seconds") if row.get("runtime_seconds") is not None else -1),
                    build_table_cell(model_nickname(row.get("text_model_id")), subtext=display_text(row.get("prompt_bundle_id"), missing="not recorded")),
                    build_table_cell(
                        display_text(row.get("retrieval_mode"), missing="not configured"),
                        subtext=(
                            f"top_k={display_text(row.get('retrieval_top_k'), missing='not configured')}; "
                            f"rescue={display_text(row.get('recall_rescue_enabled'), missing='not recorded')}"
                        ),
                    ),
                    build_table_cell(
                        display_text(row.get("structured_output_mode"), missing="not recorded"),
                        subtext=(
                            f"trust={_trust_note(row)}; "
                            f"anchor_valid_rate={format_percent(row.get('anchor_valid_rate'), missing='not recorded')}"
                        ),
                    ),
                    build_table_cell(
                        display_text(row.get("unscored_reason"), missing=display_text(row.get("decision_reason"), missing="not recorded")),
                        subtext=display_text(row.get("score_explanation"), missing="not recorded"),
                    ),
                ]
            }
        )
    return {
        "title": "All Candidates Across Stages",
        "subtitle": "Candidate rows are normalized before rendering so blank cells and raw null placeholders do not leak into the report.",
        "columns": columns,
        "rows": rows,
        "links": [
            {"label": "CSV", "href": "all_candidates.csv"},
            {"label": "JSON", "href": "all_candidates.json"},
        ],
    }


def _build_plot_assets(output_dir: Path, stage_rows: list[dict[str, Any]], all_candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plots_dir = output_dir / "pipeline_plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []

    scores = [row.get("best_score") for row in stage_rows if row.get("best_score") is not None]
    if scores:
        stage_candidates: list[dict[str, Any]] = []
        for stage in stage_rows:
            stage_name = stage["stage_name"]
            rows_for_stage = [
                row
                for row in all_candidate_rows
                if row.get("stage_name") == stage_name and row.get("primary_metric_value") is not None
            ]
            external_rows = [
                row
                for row in rows_for_stage
                if str(row.get("candidate_id") or "").startswith("external_")
                or str(row.get("prompt_bundle_id") or "") == "external_result"
            ]
            internal_rows = [
                row
                for row in rows_for_stage
                if row not in external_rows
            ]
            internal_rows = sorted(
                internal_rows,
                key=lambda row: float(row.get("primary_metric_value") or -1.0),
                reverse=True,
            )[:3]
            for row in [*external_rows, *internal_rows]:
                stage_candidates.append(
                    {
                        "stage_name": stage_name,
                        "stage_index": stage["stage_index"],
                        "candidate_id": row.get("candidate_id"),
                        "candidate_label": model_nickname(row.get("text_model_id")),
                        "primary_metric_value": row.get("primary_metric_value"),
                        "runtime_seconds": row.get("runtime_seconds"),
                        "included_reason": "external_result"
                        if row in external_rows
                        else "top_internal_candidate",
                    }
                )
        csv_rows = [
            row for row in stage_candidates
        ]
        csv_path = plots_dir / "pipeline_stage_trajectory.csv"
        png_path = plots_dir / "pipeline_stage_trajectory.png"
        _write_csv(csv_path, csv_rows)
        plt.figure(figsize=(max(8, len(stage_rows) * 1.8), 5.0))
        by_reason = {
            "external_result": {"marker": "D", "color": "tab:green", "label": "external result"},
            "top_internal_candidate": {"marker": "o", "color": "tab:blue", "label": "top internal candidate"},
        }
        for reason, style in by_reason.items():
            subset = [row for row in stage_candidates if row.get("included_reason") == reason]
            if not subset:
                continue
            xs = [float(row["stage_index"]) for row in subset]
            ys = [float(row["primary_metric_value"]) for row in subset]
            plt.scatter(
                xs,
                ys,
                marker=style["marker"],
                color=style["color"],
                edgecolors="white",
                linewidths=0.7,
                s=52,
                label=style["label"],
            )
            _annotate_points(
                xs,
                ys,
                [
                    f"{display_text(row.get('candidate_id'), missing='candidate')} {display_text(row.get('candidate_label'), missing='')}"
                    for row in subset
                ],
            )
        plt.xticks([row["stage_index"] for row in stage_rows], [row["stage_name"] for row in stage_rows], rotation=20, ha="right")
        plt.ylabel("primary_score")
        plt.title("Stage-to-stage score trajectory")
        plt.legend(frameon=False)
        plt.margins(x=0.18, y=0.14)
        plt.tight_layout()
        _save_plot(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_stage_trajectory",
            "title": "Stage-To-Stage Score Trajectory",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
            "pdf_href": relative_href(png_path.with_suffix(".pdf"), base_dir=output_dir),
            "image_data_uri": image_data_uri(png_path),
            "hero": True,
        })

    duration_rows = [
        {
            "stage_name": row["stage_name"],
            "duration_minutes": _seconds_to_minutes(float(row.get("duration_seconds"))),
        }
        for row in stage_rows
        if row.get("duration_seconds") is not None
    ]
    if duration_rows:
        csv_path = plots_dir / "pipeline_stage_durations.csv"
        png_path = plots_dir / "pipeline_stage_durations.png"
        _write_csv(csv_path, duration_rows)
        plt.figure(figsize=(8, 4))
        plt.bar([row["stage_name"] for row in duration_rows], [row["duration_minutes"] for row in duration_rows], color="tab:orange")
        plt.ylabel("duration_minutes")
        plt.title("Stage durations")
        plt.tight_layout()
        _save_plot(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_stage_durations",
            "title": "Stage Durations",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
            "pdf_href": relative_href(png_path.with_suffix(".pdf"), base_dir=output_dir),
            "image_data_uri": image_data_uri(png_path),
            "hero": False,
        })

    frontier_rows = [
        row for row in all_candidate_rows if row.get("primary_metric_value") is not None and row.get("runtime_seconds") is not None
    ]
    if frontier_rows:
        csv_path = plots_dir / "pipeline_candidate_frontier.csv"
        png_path = plots_dir / "pipeline_candidate_frontier.png"
        _write_csv(
            csv_path,
            [
                {
                    "stage_name": row.get("stage_name"),
                    "candidate_id": row.get("candidate_id"),
                    "candidate_label": model_nickname(row.get("text_model_id")),
                    "primary_metric_value": row.get("primary_metric_value"),
                    "runtime_minutes": _seconds_to_minutes(float(row.get("runtime_seconds"))),
                }
                for row in frontier_rows
            ],
        )
        stage_names = list(dict.fromkeys(display_text(row.get("stage_name"), missing="stage") for row in frontier_rows))
        palette = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown"]
        colors = {name: palette[index % len(palette)] for index, name in enumerate(stage_names)}
        plt.figure(figsize=(7, 5))
        for stage_name in stage_names:
            subset = [row for row in frontier_rows if display_text(row.get("stage_name"), missing="stage") == stage_name]
            xs = [_seconds_to_minutes(float(row["runtime_seconds"])) for row in subset]
            ys = [row["primary_metric_value"] for row in subset]
            plt.scatter(
                xs,
                ys,
                label=stage_name,
                color=colors[stage_name],
                edgecolors="white",
                linewidths=0.7,
                s=42,
            )
            _annotate_points(xs, ys, [model_nickname(row.get("text_model_id")) for row in subset])
        plt.xlabel("runtime_minutes")
        plt.ylabel("primary_score")
        plt.title("Pipeline candidate frontier")
        plt.legend()
        plt.margins(x=0.18, y=0.14)
        plt.tight_layout()
        _save_plot(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_candidate_frontier",
            "title": "Pipeline Candidate Frontier",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
            "pdf_href": relative_href(png_path.with_suffix(".pdf"), base_dir=output_dir),
            "image_data_uri": image_data_uri(png_path),
            "hero": False,
        })

    for asset in assets:
        asset["guidance"] = build_plot_guidance(asset["stem"])
        asset["subtitle"] = None
    return assets


def _artifact_links(output_dir: Path, manifest_path: Path) -> list[dict[str, str]]:
    links = [
        {"label": "Manifest", "href": relative_href(manifest_path, base_dir=output_dir), "text": manifest_path.name},
        {"label": "All Candidates CSV", "href": "all_candidates.csv", "text": "all_candidates.csv"},
        {"label": "All Candidates JSON", "href": "all_candidates.json", "text": "all_candidates.json"},
    ]
    plots_dir = output_dir / "pipeline_plots"
    if plots_dir.exists():
        links.append({"label": "Pipeline Plots", "href": "pipeline_plots/pipeline_stage_trajectory.csv", "text": "pipeline_plots/"})
    proposal_dir = output_dir / "compare" / "experiment" / "results" / "proposal_tables"
    proposal_files = [
        ("Proposal Tables Manifest", proposal_dir / "manifest.json"),
        ("Cell Review CSV", proposal_dir / "cell_review.csv"),
        ("All Proposals CSV", proposal_dir / "all_proposals.csv"),
        ("All Scored Cells CSV", proposal_dir / "all_scored_cells.csv"),
        ("Column Difficulty CSV", proposal_dir / "column_difficulty.csv"),
    ]
    for label, path in proposal_files:
        if path.exists():
            links.append({"label": label, "href": relative_href(path, base_dir=output_dir), "text": path.name})
    return links


def _provenance_items(manifest: dict[str, Any], stage_rows: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [
        {"label": "Session Id", "value": display_text(manifest.get("session_id"), missing="not recorded"), "note": None},
        {"label": "Label", "value": display_text(manifest.get("label"), missing="not recorded"), "note": None},
        {"label": "Session Status", "value": display_text(manifest.get("status"), missing="not recorded"), "note": display_text(manifest.get("completed_at"), missing=None)},
        {"label": "Stage Count", "value": str(len(stage_rows)), "note": None},
        {
            "label": "Final Winner",
            "value": display_text(stage_rows[-1].get("winner_candidate_id"), missing="not recorded") if stage_rows else "not recorded",
            "note": display_text(stage_rows[-1].get("study_type"), missing="not recorded") if stage_rows else None,
        },
    ]


def build_overnight_report_view(manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    output_dir = manifest_path.parent
    stage_rows, all_candidate_rows = _build_stage_rows(manifest_path)
    all_candidate_rows = sort_candidates(all_candidate_rows)

    _write_csv(
        output_dir / "all_candidates.csv",
        [
            {
                "stage_name": row.get("stage_name"),
                "stage_study_type": row.get("stage_study_type"),
                "candidate_id": row.get("candidate_id"),
                "text_model_id": row.get("text_model_id"),
                "prompt_bundle_id": row.get("prompt_bundle_id"),
                "retrieval_mode": row.get("retrieval_mode"),
                "retrieval_top_k": row.get("retrieval_top_k"),
                "score_status": row.get("score_status"),
                "unscored_reason": row.get("unscored_reason"),
                "primary_metric_value": row.get("primary_metric_value"),
                "runtime_seconds": row.get("runtime_seconds"),
                "promotion_decision": row.get("promotion_decision"),
                "decision_reason": row.get("decision_reason"),
            }
            for row in all_candidate_rows
        ],
    )
    write_json(output_dir / "all_candidates.json", all_candidate_rows)

    caveats = _build_caveats(stage_rows, all_candidate_rows)
    next_checks = _build_next_checks(stage_rows, all_candidate_rows)
    final_stage = stage_rows[-1] if stage_rows else {}
    plots = _build_plot_assets(output_dir, stage_rows, all_candidate_rows)
    page = {
        "title": f"{display_text(manifest.get('label'), missing='overnight')} pipeline decision report",
        "summary_sentence": _main_conclusion(stage_rows),
        "top_badges": [
            {"text": "pipeline", "tone": "good"},
            {"text": f"{len(stage_rows)} stages", "tone": "neutral"},
            {"text": display_text(manifest.get("status"), missing="status unknown"), "tone": "warn" if manifest.get("status") != "completed" else "good"},
        ],
        "hero_meta": [
            {"label": "Session Id", "value": display_text(manifest.get("session_id"), missing="not recorded"), "note": None},
            {"label": "Label", "value": display_text(manifest.get("label"), missing="not recorded"), "note": None},
            {"label": "Session Status", "value": display_text(manifest.get("status"), missing="not recorded"), "note": display_text(manifest.get("completed_at"), missing=None)},
            {"label": "Final Winner", "value": display_text(final_stage.get("winner_model_name"), missing=display_text(final_stage.get("winner_candidate_id"), missing="not recorded")), "note": display_text(final_stage.get("study_type"), missing="not recorded")},
            {"label": "Final Score", "value": format_score(final_stage.get("best_score")), "note": display_text(final_stage.get("winner_score_status"), missing="unknown")},
            {"label": "Candidate Count", "value": str(len(all_candidate_rows)), "note": _status_mix_text(status_counts(all_candidate_rows))},
            {"label": "Stage Count", "value": str(len(stage_rows)), "note": None},
        ],
        "executive_cards": [],
        "decision_cards": [
            {
                "title": "Final Selection",
                "lead": "Selection rationale at the pipeline level, not just stage-local artifact links.",
                "items": [
                    f"Final stage winner was {display_text(final_stage.get('winner_model_name'), missing=display_text(final_stage.get('winner_candidate_id'), missing='not recorded'))} with score {format_score(final_stage.get('best_score'))}.",
                    f"Final winner status was {status_label(display_text(final_stage.get('winner_score_status'), missing='unknown'))}.",
                    "Final stage improved the score relative to the preceding stage."
                    if len(stage_rows) > 1 and safe_float(final_stage.get("best_score")) is not None and safe_float(stage_rows[-2].get("best_score")) is not None and safe_float(final_stage.get("best_score")) > safe_float(stage_rows[-2].get("best_score"))
                    else "Final stage mainly validated the earlier pipeline leader.",
                ],
                "badges": [{"text": "final selection", "tone": "good"}],
            },
            {
                "title": "Stage Interpretation",
                "lead": "Rule-based reading of where the overnight run gained score versus merely validated prior work.",
                "items": [
                    f"Strongest stage by score: {max(stage_rows, key=lambda row: row.get('best_score') if row.get('best_score') is not None else float('-inf'))['stage_name']}." if stage_rows else "No stage score was recorded.",
                    f"Pipeline covered {len(stage_rows)} stages and {len(all_candidate_rows)} candidates.",
                    "At least one later stage changed the winner configuration."
                    if any(stage.get("change") and "->" in str(stage.get("change")) for stage in stage_rows)
                    else "No later stage changed the winner configuration.",
                ],
                "badges": [{"text": "stage evolution", "tone": "neutral"}],
            },
            {
                "title": "Caveats",
                "lead": "Pipeline-wide trust summary aggregated from every stage and candidate.",
                "items": caveats,
                "badges": [{"text": "trust", "tone": "warn" if caveats and caveats[0] != "No major overnight trust caveats were recorded." else "good"}],
            },
            {
                "title": "Next Checks",
                "lead": "Deterministic pipeline follow-ups based on stage evidence.",
                "items": next_checks,
                "badges": [{"text": "follow-up", "tone": "neutral"}],
            },
        ],
        "stage_cards": _stage_cards(stage_rows),
        "stage_table": _build_stage_table(stage_rows),
        "candidate_table": _build_candidate_table(all_candidate_rows),
        "plots": plots,
        "artifact_links": _artifact_links(output_dir, manifest_path),
        "provenance_items": _provenance_items(manifest, stage_rows),
    }
    return page


def generate_overnight_report(manifest_path: Path) -> Path:
    page = build_overnight_report_view(manifest_path)
    report_html = render_template("overnight.html", page=page)
    report_path = manifest_path.parent / "overview.html"
    report_path.write_text(report_html, encoding="utf-8")
    return report_path
