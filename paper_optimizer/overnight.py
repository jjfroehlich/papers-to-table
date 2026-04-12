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
    format_runtime,
    format_score,
    image_data_uri,
    is_missing,
    load_csv_rows,
    load_json_if_exists,
    merge_candidate_rows,
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


def _holdout_status(summary: dict[str, Any]) -> str:
    holdout = summary.get("holdout_validation") if isinstance(summary.get("holdout_validation"), dict) else {}
    status = holdout.get("status")
    if not status:
        status = "completed" if holdout.get("ran") else "not run"
    return str(status).replace("_", " ")


def _winner_id(summary: dict[str, Any], best_candidate: dict[str, Any], compare_summary: dict[str, Any]) -> str | None:
    winner = compare_summary.get("winner") if isinstance(compare_summary.get("winner"), dict) else {}
    return (
        summary.get("winner_candidate_id")
        or summary.get("current_best_candidate_id")
        or best_candidate.get("candidate_id")
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


def _main_conclusion(stage_rows: list[dict[str, Any]]) -> str:
    if not stage_rows:
        return "No stages were recorded in the overnight manifest."
    numeric_scores = [row for row in stage_rows if row.get("best_score") is not None]
    if not numeric_scores:
        final = stage_rows[-1]
        return (
            f"{len(stage_rows)} stages completed, but none recorded a numeric winner score. "
            f"Final stage '{final['stage_name']}' ended with winner {display_text(final.get('winner_candidate_id'), missing='not recorded')} "
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
        f"winner {display_text(best_stage.get('winner_candidate_id'), missing='not recorded')} at {format_score(best_stage.get('best_score'))}."
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
    if any(stage.get("holdout_status") != "completed" for stage in stage_rows):
        caveats.append("At least one stage did not run holdout validation.")
    if counts.get("scored_degraded", 0):
        caveats.append(f"{counts['scored_degraded']} pipeline candidates scored only in degraded mode.")
    if counts.get("unscored", 0):
        caveats.append(f"{counts['unscored']} pipeline candidates were unscored.")
    if counts.get("failed", 0):
        caveats.append(f"{counts['failed']} pipeline candidates failed before scoring.")
    if not any(row.get("correctness_judge_a") is not None and row.get("correctness_judge_b") is not None for row in all_candidate_rows):
        caveats.append("Dual-judge comparison was not recorded across the pipeline candidates.")
    if not caveats:
        caveats.append("No major overnight trust caveats were recorded.")
    return caveats


def _build_next_checks(stage_rows: list[dict[str, Any]], all_candidate_rows: list[dict[str, Any]]) -> list[str]:
    checks: list[str] = []
    counts = status_counts(all_candidate_rows)
    if any(stage.get("holdout_status") != "completed" for stage in stage_rows):
        checks.append("Run holdout validation for the final winner before treating the overnight result as final.")
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
        primary_metric = str(summary.get("primary_metric") or compare_summary.get("primary_metric") or "correctness")
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
            "winner_score_status": winner_row.get("score_status") if winner_row else None,
            "winner_unscored_reason": winner_row.get("unscored_reason") if winner_row else None,
            "winner_prompt_bundle_id": winner_row.get("prompt_bundle_id") if winner_row else best_candidate.get("prompt_bundle_id"),
            "winner_text_model_id": winner_row.get("text_model_id") if winner_row else best_candidate.get("text_model_id"),
            "winner_retrieval_mode": winner_row.get("retrieval_mode") if winner_row else None,
            "winner_retrieval_top_k": winner_row.get("retrieval_top_k") if winner_row else None,
            "winner_structured_output_mode": winner_row.get("structured_output_mode") if winner_row else None,
            "best_score": winner_score,
            "holdout_status": _holdout_status(summary),
            "candidate_count": len(candidate_rows),
            "score_counts": counts,
            "duration_seconds": duration_seconds,
            "change": change,
            "report_href": relative_href(experiment_dir / "report.html", base_dir=manifest_path.parent) if (experiment_dir / "report.html").exists() else None,
            "summary": (
                f"Winner {display_text(winner_id, missing='not recorded')} finished with {format_score(winner_score)} and status "
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
                    {"text": stage["holdout_status"], "tone": "warn" if stage["holdout_status"] != "completed" else "good"},
                    {"text": status_label(display_text(stage.get("winner_score_status"), missing="unknown")), "tone": status_tone(display_text(stage.get("winner_score_status"), missing="unknown"))},
                ],
                "metrics": [
                    {"label": "Winner", "value": display_text(stage.get("winner_candidate_id"), missing="not recorded")},
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
        {"label": "Trust", "align": "left", "sort": "string"},
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
                    build_table_cell(display_text(stage.get("winner_candidate_id"), missing="not recorded"), monospace=True),
                    build_table_cell(format_score(stage.get("best_score")), sort_value=stage.get("best_score") if stage.get("best_score") is not None else -1),
                    build_table_cell(format_delta(delta, missing="—"), sort_value=delta if delta is not None else -9999),
                    build_table_cell(display_text(stage.get("change"), missing="not recorded")),
                    build_table_cell(
                        display_text(stage.get("holdout_status"), missing="not recorded"),
                        badge=display_text(stage.get("winner_score_status"), missing="unknown"),
                        tone=status_tone(display_text(stage.get("winner_score_status"), missing="unknown")),
                        subtext=_status_mix_text(stage.get("score_counts") or {}),
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
                    build_table_cell(display_text(row.get("candidate_id"), missing="not recorded"), monospace=True, subtext="winner" if row.get("winner_candidate") else None),
                    build_table_cell(format_score(row.get("primary_metric_value")), sort_value=row.get("primary_metric_value") if row.get("primary_metric_value") is not None else -1),
                    build_table_cell(status_label(display_text(row.get("score_status"), missing="unknown")), badge=status_label(display_text(row.get("score_status"), missing="unknown")), tone=status_tone(display_text(row.get("score_status"), missing="unknown"))),
                    build_table_cell(format_runtime(row.get("runtime_seconds")), sort_value=row.get("runtime_seconds") if row.get("runtime_seconds") is not None else -1),
                    build_table_cell(
                        display_text(row.get("text_model_id"), missing="not recorded"),
                        subtext=display_text(row.get("prompt_bundle_id"), missing="not recorded"),
                    ),
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
                            f"contract={display_text(row.get('extraction_contract_valid'), missing='unknown')}; "
                            f"fallback={display_text(row.get('prompt_only_degraded_mode_used'), missing='not recorded')}"
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
        csv_rows = [
            {"stage_name": row["stage_name"], "stage_index": row["stage_index"], "best_score": row.get("best_score")}
            for row in stage_rows
        ]
        csv_path = plots_dir / "pipeline_stage_trajectory.csv"
        png_path = plots_dir / "pipeline_stage_trajectory.png"
        _write_csv(csv_path, csv_rows)
        plt.figure(figsize=(8, 4))
        plt.plot([row["stage_name"] for row in stage_rows], [row.get("best_score") or 0.0 for row in stage_rows], marker="o")
        plt.ylabel("best_score")
        plt.title("Stage-to-stage score trajectory")
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_stage_trajectory",
            "title": "Stage-To-Stage Score Trajectory",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
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
        plt.savefig(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_stage_durations",
            "title": "Stage Durations",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
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
            plt.scatter(
                [_seconds_to_minutes(float(row["runtime_seconds"])) for row in subset],
                [row["primary_metric_value"] for row in subset],
                label=stage_name,
                color=colors[stage_name],
            )
        plt.xlabel("runtime_minutes")
        plt.ylabel("primary_score")
        plt.title("Pipeline candidate frontier")
        plt.legend()
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close()
        assets.append({
            "stem": "pipeline_candidate_frontier",
            "title": "Pipeline Candidate Frontier",
            "csv_href": relative_href(csv_path, base_dir=output_dir),
            "png_href": relative_href(png_path, base_dir=output_dir),
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
    return links


def _provenance_items(manifest: dict[str, Any], stage_rows: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [
        {"label": "Session Id", "value": display_text(manifest.get("session_id"), missing="not recorded"), "note": None},
        {"label": "Label", "value": display_text(manifest.get("label"), missing="not recorded"), "note": None},
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
            {"text": _status_mix_text(status_counts(all_candidate_rows)), "tone": "neutral"},
            {"text": display_text(final_stage.get("holdout_status"), missing="not recorded"), "tone": "warn" if final_stage.get("holdout_status") != "completed" else "good"},
        ],
        "hero_meta": [
            {"label": "Session Id", "value": display_text(manifest.get("session_id"), missing="not recorded"), "note": None},
            {"label": "Label", "value": display_text(manifest.get("label"), missing="not recorded"), "note": None},
            {"label": "Final Winner", "value": display_text(final_stage.get("winner_candidate_id"), missing="not recorded"), "note": display_text(final_stage.get("study_type"), missing="not recorded")},
            {"label": "Final Score", "value": format_score(final_stage.get("best_score")), "note": display_text(final_stage.get("winner_score_status"), missing="unknown")},
            {"label": "Candidate Count", "value": str(len(all_candidate_rows)), "note": _status_mix_text(status_counts(all_candidate_rows))},
            {"label": "Stage Count", "value": str(len(stage_rows)), "note": None},
        ],
        "executive_cards": [
            {
                "label": "Main Conclusion",
                "value": display_text(final_stage.get("winner_candidate_id"), missing="no final winner"),
                "note": _main_conclusion(stage_rows),
                "badges": [{"text": "final winner", "tone": "good"}] if final_stage else [{"text": "no stages", "tone": "warn"}],
                "class_name": "",
            },
            {
                "label": "Biggest Gain",
                "value": next((stage["stage_name"] for stage in stage_rows if stage.get("change") and "->" in str(stage.get("change"))), "not isolated"),
                "note": "Stage-to-stage gain is called out explicitly so the parent report stays meaningful on its own.",
                "badges": [],
                "class_name": "",
            },
            {
                "label": "Trust / Caveats",
                "value": "healthy" if caveats == ["No major overnight trust caveats were recorded."] else "review needed",
                "note": caveats[0],
                "badges": [{"text": item.split(".")[0], "tone": "warn"} for item in caveats[:2]],
                "class_name": "",
            },
            {
                "label": "Next Check",
                "value": next_checks[0],
                "note": "; ".join(next_checks[1:]) if len(next_checks) > 1 else None,
                "badges": [{"text": "pipeline", "tone": "neutral"}],
                "class_name": "",
            },
        ],
        "decision_cards": [
            {
                "title": "Why The Final Configuration Won",
                "lead": "Selection rationale at the pipeline level, not just stage-local artifact links.",
                "items": [
                    f"Final stage winner was {display_text(final_stage.get('winner_candidate_id'), missing='not recorded')} with score {format_score(final_stage.get('best_score'))}.",
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
                "title": "Trust And Caveats",
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
    report_path = manifest_path.parent / "report.html"
    report_path.write_text(report_html, encoding="utf-8")
    return report_path
