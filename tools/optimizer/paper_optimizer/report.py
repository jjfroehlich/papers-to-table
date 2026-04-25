from __future__ import annotations

from pathlib import Path
from typing import Any

from .report_templates import render_template
from .reporting import (
    build_plot_guidance,
    build_table_cell,
    candidate_label,
    display_text,
    format_delta,
    format_percent,
    format_runtime,
    format_score,
    format_timestamp,
    image_data_uri,
    is_missing,
    load_csv_rows,
    load_json_if_exists,
    merge_candidate_rows,
    parse_bool,
    primary_value_from_row,
    reason_text,
    relative_href,
    safe_float,
    sort_candidates,
    status_counts,
    status_label,
    status_tone,
    study_variant,
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


def _holdout_payload(summary: dict[str, Any]) -> dict[str, Any]:
    holdout = summary.get("holdout_validation") if isinstance(summary.get("holdout_validation"), dict) else {}
    if not holdout:
        return {"status": "not run", "score": None, "configured": False}
    status = holdout.get("status")
    if not status:
        status = "completed" if holdout.get("ran") else "not run"
    return {
        "status": str(status).replace("_", " "),
        "score": holdout.get("score"),
        "configured": bool(holdout.get("configured", holdout.get("ran", False))),
        "skip_reason": holdout.get("skip_reason"),
    }


def _status_mix_text(counts: dict[str, int]) -> str:
    return (
        f"{counts.get('scored', 0)} scored, "
        f"{counts.get('scored_degraded', 0)} degraded, "
        f"{counts.get('unscored', 0)} unscored, "
        f"{counts.get('failed', 0)} failed"
    )


def _gap_to_runner_up(rows: list[dict[str, Any]]) -> float | None:
    scored_rows = [row for row in rows if row.get("primary_metric_value") is not None]
    if len(scored_rows) < 2:
        return None
    return (scored_rows[0]["primary_metric_value"] or 0.0) - (scored_rows[1]["primary_metric_value"] or 0.0)


def _time_window(rows: list[dict[str, Any]], run_metadata: dict[str, Any]) -> tuple[str, str]:
    starts = [str(row.get("started_at")) for row in rows if not is_missing(row.get("started_at"))]
    ends = [str(row.get("ended_at")) for row in rows if not is_missing(row.get("ended_at"))]
    started = min(starts) if starts else run_metadata.get("started_at") or run_metadata.get("timestamp")
    ended = max(ends) if ends else run_metadata.get("ended_at")
    return format_timestamp(started), format_timestamp(ended)


def _compare_summary_sentence(
    *,
    winner_label: str,
    winner_row: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    primary_metric: str,
    holdout: dict[str, Any],
    variant: str,
) -> str:
    counts = status_counts(rows)
    gap = _gap_to_runner_up(rows)
    if winner_row is None:
        return (
            f"No winner was materialized in this {variant.replace('_', ' ')} study. "
            f"Status mix: {_status_mix_text(counts)}. Holdout was {holdout['status']}."
        )
    summary = (
        f"{winner_label} {display_text(winner_row.get('candidate_id'), missing='not recorded')} led the {variant.replace('_', ' ')} study "
        f"with {primary_metric} {format_score(winner_row.get('primary_metric_value'))}."
    )
    if gap is not None:
        summary += f" The margin to the runner-up was {format_delta(gap)}."
    summary += f" Status mix: {_status_mix_text(counts)}. Holdout was {holdout['status']}."
    return summary


def _optimize_summary_sentence(
    *,
    winner_label: str,
    winner_row: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    primary_metric: str,
    summary: dict[str, Any],
    holdout: dict[str, Any],
) -> str:
    counts = status_counts(rows)
    promoted_count = sum(1 for entry in summary.get("promotion_history", []) if entry.get("promoted_candidate_id"))
    rounds_completed = summary.get("rounds_completed") or 0
    if winner_row is None:
        return (
            f"No incumbent was materialized after {rounds_completed} optimize rounds. "
            f"Status mix: {_status_mix_text(counts)}. Holdout was {holdout['status']}."
        )
    incumbent_changed = winner_row.get("candidate_id") != "cand_0000"
    changed_text = "changed from baseline" if incumbent_changed else "remained the baseline incumbent"
    return (
        f"{winner_label} {display_text(winner_row.get('candidate_id'), missing='not recorded')} {changed_text} after {rounds_completed} rounds, "
        f"finishing with {primary_metric} {format_score(winner_row.get('primary_metric_value'))}. "
        f"Promoted challengers: {promoted_count}. Status mix: {_status_mix_text(counts)}. Holdout was {holdout['status']}."
    )


def _build_caveats(
    rows: list[dict[str, Any]],
    *,
    holdout: dict[str, Any],
    study_type: str,
) -> list[str]:
    counts = status_counts(rows)
    caveats: list[str] = []
    dual_judge_completed = any(row.get("dual_judge_completed") for row in rows)
    dual_judge_incomplete_only = any(row.get("dual_judge_completed") is False for row in rows) and not dual_judge_completed
    if holdout["status"] != "completed":
        suffix = f": {holdout['skip_reason']}" if holdout.get("skip_reason") else ""
        caveats.append(f"Holdout was {holdout['status']}{suffix}.")
    if counts.get("scored_degraded", 0):
        caveats.append(f"{counts['scored_degraded']} candidate(s) scored only in degraded mode.")
    if counts.get("unscored", 0):
        caveats.append(f"{counts['unscored']} candidate(s) were unscored.")
    if counts.get("failed", 0):
        caveats.append(f"{counts['failed']} candidate(s) failed before scoring.")
    if dual_judge_incomplete_only:
        caveats.append("Dual-judge comparison was not recorded in this report.")
    if any(parse_bool(row.get("prompt_only_degraded_mode_used")) for row in rows):
        caveats.append("Prompt-only fallback was used for at least one candidate.")
    if any(parse_bool(row.get("extraction_contract_valid")) is False for row in rows):
        caveats.append("At least one candidate failed extraction contract validation.")
    if any((safe_float(row.get("judge_disagreement_rate")) or 0.0) >= 0.2 for row in rows):
        caveats.append("At least one candidate had materially high dual-judge disagreement.")
    if any((row.get("missing_evidence_count") or 0) > 0 for row in rows):
        caveats.append("At least one candidate is carrying missing evidence into the ranked report.")
    if study_type == "optimize" and not caveats:
        caveats.append("No major trust caveats were recorded beyond the optimize acceptance policy.")
    if not caveats:
        caveats.append("No major report caveats were recorded.")
    return caveats


def _trust_note(row: dict[str, Any]) -> str:
    notes: list[str] = []
    if parse_bool(row.get("prompt_only_degraded_mode_used")):
        notes.append("prompt-only degraded")
    if parse_bool(row.get("extraction_contract_valid")) is False:
        notes.append("contract invalid")
    if safe_float(row.get("anchor_valid_rate")) == 0 and (row.get("evidence_item_count") or 0):
        notes.append("zero grounded evidence")
    if (row.get("missing_evidence_count") or 0) > 0:
        notes.append(f"missing_evidence={row.get('missing_evidence_count')}")
    if (row.get("join_failure_count") or 0) > 0:
        notes.append(f"join_failures={row.get('join_failure_count')}")
    if row.get("dual_judge_completed"):
        notes.append(f"dual_judge disagreement={format_percent(row.get('judge_disagreement_rate'), missing='0.0%')}")
    elif row.get("dual_judge_completed") is False:
        notes.append("dual_judge incomplete")
    if parse_bool(row.get("judge_disagreement_warning")):
        notes.append("high judge disagreement")
    return "; ".join(notes) if notes else "healthy"


def _build_next_checks(rows: list[dict[str, Any]], *, holdout: dict[str, Any], variant: str, study_type: str) -> list[str]:
    next_checks: list[str] = []
    counts = status_counts(rows)
    if holdout["status"] != "completed":
        next_checks.append("Run holdout validation before treating this recommendation as final.")
    if counts.get("unscored", 0):
        next_checks.append("Inspect unscored candidates to determine whether the failure mode is fixable or expected.")
    if counts.get("scored_degraded", 0):
        next_checks.append("Review degraded candidates to see whether structured-output or fallback behavior is masking a stronger configuration.")
    if variant == "retrieval_compare":
        next_checks.append("Inspect whether the winning retrieval depth is stable enough to narrow the retrieval search bounds.")
    if variant == "model_compare":
        next_checks.append("Review winner-versus-runner-up traces before standardizing on the top model.")
    if variant == "prompt_compare":
        next_checks.append("Check whether the winning prompt also preserves better structure and lower ambiguity, not just higher score.")
    if study_type == "optimize":
        next_checks.append("Review the promotion history for signs of a score ceiling or a too-tight tie zone.")
    if not next_checks:
        next_checks.append("No immediate follow-up stands out from the recorded metrics.")
    return next_checks[:4]


def _build_why_winner(
    winner_row: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    *,
    primary_metric: str,
    holdout: dict[str, Any],
    study_type: str,
) -> list[str]:
    if winner_row is None:
        return ["No winner was materialized, so there is no positive selection rationale to report."]
    bullets = [
        f"It had the best recorded {primary_metric}: {format_score(winner_row.get('primary_metric_value'))}.",
        f"Its score state was {status_label(str(winner_row.get('score_status') or 'unknown'))}.",
        f"Runtime was {format_runtime(winner_row.get('runtime_seconds'))}.",
    ]
    gap = _gap_to_runner_up(rows)
    if gap is not None:
        bullets.append(f"It outscored the runner-up by {format_delta(gap)} on the primary metric.")
    if parse_bool(winner_row.get("prompt_only_degraded_mode_used")):
        bullets.append("Selection is weaker because the winner required prompt-only fallback.")
    if holdout["status"] != "completed":
        bullets.append("Selection remains provisional because holdout validation was not completed.")
    if study_type == "optimize":
        bullets.append(
            f"Optimize kept or promoted it under the acceptance policy with decision '{display_text(winner_row.get('promotion_decision'), missing='not recorded')}'."
        )
    return bullets


def _build_why_others(rows: list[dict[str, Any]], winner_id: str | None) -> list[str]:
    losers = [row for row in rows if row.get("candidate_id") != winner_id]
    if not losers:
        return ["No runner-up candidates were recorded."]
    lower_score = sum(1 for row in losers if row.get("primary_metric_value") is not None)
    unscored = sum(1 for row in losers if row.get("score_status") == "unscored")
    failed = sum(1 for row in losers if row.get("score_status") == "failed")
    reasons: list[str] = []
    if lower_score:
        reasons.append(f"{lower_score} candidate(s) lost on the primary metric.")
    if unscored:
        reasons.append(f"{unscored} candidate(s) never produced a valid score.")
    if failed:
        reasons.append(f"{failed} candidate(s) failed before scoring completed.")
    common_decisions: dict[str, int] = {}
    for row in losers:
        reason = display_text(row.get("decision_reason"), missing="reason not recorded")
        common_decisions[reason] = common_decisions.get(reason, 0) + 1
    dominant = sorted(common_decisions.items(), key=lambda item: (-item[1], item[0]))[:2]
    for reason, count in dominant:
        reasons.append(f"{count} candidate(s) carried decision reason '{reason}'.")
    return reasons


def _build_interpretation(rows: list[dict[str, Any]], *, study_type: str, variant: str, summary: dict[str, Any]) -> list[str]:
    bullets: list[str] = []
    counts = status_counts(rows)
    gap = _gap_to_runner_up(rows)
    if gap is not None:
        bullets.append(f"Top candidate outperformed the runner-up by {format_delta(gap)}.")
    if counts.get("unscored", 0):
        bullets.append(f"{counts['unscored']} of {len(rows)} candidates were unscored.")
    if variant == "retrieval_compare":
        best = rows[0] if rows else None
        if best is not None:
            bullets.append(
                f"Retrieval sweep peaked at top_k={display_text(best.get('retrieval_top_k'), missing='not recorded')} with mode {display_text(best.get('retrieval_mode'), missing='not configured')}."
            )
    if variant == "prompt_compare":
        bullets.append("Prompt comparison should be read as rank order plus trust signals, not just a single best score.")
    if variant == "model_compare":
        bullets.append("Model comparison reflects benchmark-specific ranking, so inspect runtime and judge signals before standardizing on the winner.")
    if study_type == "optimize":
        promoted = sum(1 for entry in summary.get("promotion_history", []) if entry.get("promoted_candidate_id"))
        rounds_configured = summary.get("rounds_configured") or 0
        bullets.append(f"Optimization promoted {promoted} challengers across {rounds_configured} configured rounds.")
        if promoted == 0:
            bullets.append("Optimization did not improve beyond the baseline incumbent.")
    if not bullets:
        bullets.append("No additional rule-based interpretation was triggered for this run.")
    return bullets


def _build_study_cards(
    rows: list[dict[str, Any]],
    *,
    study_type: str,
    variant: str,
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    if study_type == "optimize":
        unique_challengers = len({row.get("candidate_id") for row in rows if row.get("candidate_id") != "cand_0000"})
        promoted = [entry for entry in summary.get("promotion_history", []) if entry.get("promoted_candidate_id")]
        rounds_configured = int(summary.get("rounds_configured") or 0)
        rounds_with_unique = len({row.get("round_index") for row in rows if row.get("round_index") not in (None, 0)})
        changed = display_text(summary.get("current_best_candidate_id"), missing="not recorded") != "cand_0000"
        return [
            {
                "title": "Optimize Summary",
                "lead": "Optimize reports use incumbent semantics and explicitly separate search activity from accepted progress.",
                "items": [
                    f"Incumbent changed from baseline: {'yes' if changed else 'no'}.",
                    f"Rounds configured: {rounds_configured}.",
                    f"Rounds with unique challengers: {rounds_with_unique}.",
                    f"Promoted challengers: {len(promoted)}.",
                ],
                "badges": [{"text": "incumbent semantics", "tone": "good"}],
            },
            {
                "title": "Promotion History",
                "lead": "Condensed view of the optimize timeline.",
                "items": [
                    f"Round {entry.get('round_index')}: promoted {display_text(entry.get('promoted_candidate_id'), missing='none')}"
                    for entry in summary.get("promotion_history", [])[:6]
                ]
                or ["No round history was recorded."],
                "badges": [{"text": f"{unique_challengers} challengers", "tone": "neutral"}],
            },
            {
                "title": "Search Ceiling",
                "lead": "Tie-zone and plateau interpretation derived from the recorded metrics.",
                "items": [
                    "No promoted challenger suggests the run may have hit a score ceiling or an acceptance tie zone."
                    if len(promoted) == 0
                    else f"Promotion history shows {len(promoted)} accepted score improvements."
                ],
                "badges": [{"text": "search health", "tone": "warn" if len(promoted) == 0 else "good"}],
            },
        ]

    retrieval_rows = [row for row in rows if not is_missing(row.get("retrieval_top_k")) or not is_missing(row.get("retrieval_mode"))]
    retrieval_card = {
        "title": "Retrieval Signals",
        "lead": "Retrieval settings are surfaced explicitly whenever retrieval is part of the comparison.",
        "items": [
            f"Winner retrieval mode: {display_text(rows[0].get('retrieval_mode'), missing='not configured')}." if rows else "Winner retrieval mode not recorded.",
            f"Winner top_k: {display_text(rows[0].get('retrieval_top_k'), missing='not configured')}." if rows else "Winner top_k not recorded.",
            f"Recall rescue enabled: {display_text(rows[0].get('recall_rescue_enabled'), missing='not recorded')}." if rows else "Recall rescue state not recorded.",
            f"Whole-document mode: {display_text(rows[0].get('whole_document_mode'), missing='not recorded')}." if rows else "Whole-document state not recorded.",
        ],
        "badges": [{"text": "retrieval surfaced", "tone": "good" if retrieval_rows else "warn"}],
    }
    comparison_card = {
        "title": "Compare Semantics",
        "lead": "Compare reports focus on rank order and winner selection, not optimize promotion language.",
        "items": [
            f"Candidate count: {len(rows)}.",
            f"Scored mix: {_status_mix_text(status_counts(rows))}.",
            f"Top runtime: {format_runtime(rows[0].get('runtime_seconds'))}." if rows else "No candidate runtime recorded.",
        ],
        "badges": [{"text": "winner semantics", "tone": "good"}],
    }
    cards = [comparison_card]
    if variant == "retrieval_compare":
        cards.append(retrieval_card)
    elif variant == "prompt_compare":
        cards.append(
            {
                "title": "Prompt Comparison",
                "lead": "Prompt reports compare prompt bundle behavior without optimize-language spillover.",
                "items": [
                    f"Prompt bundles compared: {len({row.get('prompt_bundle_id') for row in rows if row.get('prompt_bundle_id')})}.",
                    "Use the candidate table to compare prompt score, structure, and fallback behavior together.",
                ],
                "badges": [{"text": "prompt semantics", "tone": "good"}],
            }
        )
    elif variant == "model_compare":
        cards.append(
            {
                "title": "Model Comparison",
                "lead": "Model reports emphasize rank order, runtime, and trustworthiness rather than promotion state.",
                "items": [
                    f"Models compared: {len({row.get('text_model_id') for row in rows if row.get('text_model_id')})}.",
                    "Check the score-vs-runtime frontier before standardizing on the top-ranked model.",
                ],
                "badges": [{"text": "model semantics", "tone": "good"}],
            }
        )
    return cards


def _build_plot_cards(experiment_dir: Path, *, study_type: str, variant: str) -> list[dict[str, Any]]:
    plots_dir = experiment_dir / "plots"
    if not plots_dir.exists():
        return []
    preferred: list[str]
    if study_type == "optimize":
        preferred = [
            "optimize_history_best_so_far",
            "optimize_best_by_round",
            "optimize_score_delta_by_round",
            "optimize_decision_counts_by_round",
            "optimize_runtime_by_round",
            "optimize_score_status_counts",
            "optimize_unscored_reasons",
            "optimize_all_scores_by_round",
            "optimize_primary_by_knob_retrieval_top_k",
        ]
    elif variant == "retrieval_compare":
        preferred = [
            "compare_primary_by_knob_retrieval_top_k",
            "compare_correctness_vs_runtime",
            "compare_score_status_counts",
            "compare_unscored_reasons",
            "compare_primary_by_candidate",
            "compare_primary_by_text_model",
        ]
    else:
        preferred = [
            "compare_primary_by_candidate",
            "compare_correctness_vs_runtime",
            "compare_score_status_counts",
            "compare_unscored_reasons",
            "compare_primary_by_text_model",
            "compare_primary_by_prompt_bundle",
            "compare_judge_a_vs_judge_b",
            "compare_dev_vs_holdout",
        ]
    plot_cards: list[dict[str, Any]] = []
    for index, stem in enumerate(preferred):
        png_path = plots_dir / f"{stem}.png"
        csv_path = plots_dir / f"{stem}.csv"
        if not png_path.exists() and not csv_path.exists():
            continue
        plot_cards.append(
            {
                "title": stem.replace("_", " ").title(),
                "subtitle": None,
                "hero": index == 0,
                "csv_href": relative_href(csv_path, base_dir=experiment_dir) if csv_path.exists() else None,
                "png_href": relative_href(png_path, base_dir=experiment_dir) if png_path.exists() else None,
                "image_data_uri": image_data_uri(png_path) if png_path.exists() else None,
                "guidance": build_plot_guidance(stem),
            }
        )
    return plot_cards


def _build_artifact_links(experiment_dir: Path) -> list[dict[str, str]]:
    candidates = [
        ("Summary JSON", experiment_dir / "summary.json"),
        ("Best Candidate", experiment_dir / "best_candidate.json"),
        ("Compare Summary", experiment_dir / "compare_summary.json"),
        ("No Winner", experiment_dir / "no_winner.json"),
        ("Results CSV", experiment_dir / "results" / "results.csv"),
        ("Results JSONL", experiment_dir / "results" / "results.jsonl"),
        ("Candidate Diagnostics CSV", experiment_dir / "results" / "candidate_diagnostics.csv"),
        ("Candidate Diagnostics JSON", experiment_dir / "candidate_diagnostics.json"),
    ]
    links: list[dict[str, str]] = []
    for label, path in candidates:
        if path.exists():
            links.append({"label": label, "href": relative_href(path, base_dir=experiment_dir), "text": path.name})
    return links


def _build_provenance_items(
    winner_row: dict[str, Any] | None,
    *,
    summary: dict[str, Any],
    run_metadata: dict[str, Any],
    holdout: dict[str, Any],
) -> list[dict[str, str | None]]:
    items = [
        {
            "label": "Benchmark",
            "value": display_text(summary.get("benchmark_id"), missing="not recorded"),
            "note": None,
        },
        {
            "label": "Config",
            "value": display_text(run_metadata.get("config_path"), missing="not recorded"),
            "note": "Raw filesystem paths are kept here instead of the summary band.",
        },
        {
            "label": "Holdout",
            "value": holdout["status"],
            "note": f"score={format_score(holdout.get('score'), missing='not run')}" if holdout.get("score") is not None else None,
        },
    ]
    if winner_row is not None:
        items.extend(
            [
                {
                    "label": "Winner Model",
                    "value": display_text(winner_row.get("text_model_id"), missing="not recorded"),
                    "note": None,
                },
                {
                    "label": "Winner Prompt",
                    "value": display_text(winner_row.get("prompt_bundle_id"), missing="not recorded"),
                    "note": None,
                },
                {
                    "label": "Winner Retrieval",
                    "value": (
                        f"mode={display_text(winner_row.get('retrieval_mode'), missing='not configured')}; "
                        f"top_k={display_text(winner_row.get('retrieval_top_k'), missing='not configured')}"
                    ),
                    "note": (
                        f"rescue_enabled={display_text(winner_row.get('recall_rescue_enabled'), missing='not recorded')}; "
                        f"whole_document_mode={display_text(winner_row.get('whole_document_mode'), missing='not recorded')}"
                    ),
                },
                {
                    "label": "Winner Structure",
                    "value": display_text(winner_row.get("structured_output_mode"), missing="not recorded"),
                    "note": (
                        f"trust={_trust_note(winner_row)}; "
                        f"anchor_valid_rate={format_percent(winner_row.get('anchor_valid_rate'), missing='not recorded')}"
                    ),
                },
            ]
        )
    return items


def _build_candidate_table(
    rows: list[dict[str, Any]],
    *,
    study_type: str,
    primary_metric: str,
    winner_id: str | None,
) -> dict[str, Any]:
    columns: list[dict[str, str]]
    table_rows: list[dict[str, Any]] = []
    if study_type == "optimize":
        columns = [
            {"label": "Rank", "align": "right", "sort": "number"},
            {"label": "Candidate", "align": "left", "sort": "string"},
            {"label": "Role", "align": "left", "sort": "string"},
            {"label": primary_metric.title(), "align": "right", "sort": "number"},
            {"label": "Status", "align": "left", "sort": "string"},
            {"label": "Round", "align": "right", "sort": "number"},
            {"label": "Runtime", "align": "right", "sort": "number"},
            {"label": "Retrieval", "align": "left", "sort": "string"},
            {"label": "Structure", "align": "left", "sort": "string"},
            {"label": "Decision", "align": "left", "sort": "string"},
        ]
        winner_score = rows[0].get("primary_metric_value") if rows else None
        for index, row in enumerate(rows, start=1):
            delta = None
            if winner_score is not None and row.get("primary_metric_value") is not None:
                delta = row.get("primary_metric_value") - winner_score
            role = "incumbent" if row.get("candidate_id") == winner_id else "challenger"
            table_rows.append(
                {
                    "cells": [
                        build_table_cell(str(index), sort_value=index),
                        build_table_cell(
                            display_text(row.get("candidate_id"), missing="not recorded"),
                            subtext=f"parent={display_text(row.get('parent_candidate_id'), missing='—')}",
                            monospace=True,
                        ),
                        build_table_cell(role, badge=role, tone=status_tone(role)),
                        build_table_cell(
                            format_score(row.get("primary_metric_value"), missing="not scored"),
                            subtext=f"delta={format_delta(delta, missing='—')}",
                            sort_value=row.get("primary_metric_value") if row.get("primary_metric_value") is not None else -1,
                        ),
                        build_table_cell(status_label(row.get("score_status") or "unknown"), badge=status_label(row.get("score_status") or "unknown"), tone=status_tone(str(row.get("score_status") or "unknown"))),
                        build_table_cell(display_text(row.get("round_index"), missing="baseline"), sort_value=row.get("round_index") if row.get("round_index") is not None else -1),
                        build_table_cell(format_runtime(row.get("runtime_seconds")), sort_value=row.get("runtime_seconds") if row.get("runtime_seconds") is not None else -1),
                        build_table_cell(
                            display_text(row.get("retrieval_mode"), missing="not configured"),
                            subtext=f"top_k={display_text(row.get('retrieval_top_k'), missing='not configured')}",
                        ),
                        build_table_cell(
                            display_text(row.get("structured_output_mode"), missing="not recorded"),
                            subtext=(
                                f"trust={_trust_note(row)}; "
                                f"anchor_valid_rate={format_percent(row.get('anchor_valid_rate'), missing='not recorded')}"
                            ),
                            details=(
                                f"structure_reason={display_text(row.get('structured_output_reason'), missing='none')}; "
                                f"evidence_outcomes={display_text(row.get('evidence_anchor_outcome_counts'), missing='not recorded')}; "
                                f"judge_batches={display_text(row.get('judge_execution_summary'), missing='not recorded')}"
                            ),
                        ),
                        build_table_cell(
                            display_text(row.get("promotion_decision"), missing="not recorded"),
                            subtext=display_text(row.get("decision_reason"), missing="not recorded"),
                            details=reason_text(row, missing="no extra decision detail recorded"),
                        ),
                    ]
                }
            )
    else:
        columns = [
            {"label": "Rank", "align": "right", "sort": "number"},
            {"label": "Candidate", "align": "left", "sort": "string"},
            {"label": primary_metric.title(), "align": "right", "sort": "number"},
            {"label": "Gap To Winner", "align": "right", "sort": "number"},
            {"label": "Status", "align": "left", "sort": "string"},
            {"label": "Runtime", "align": "right", "sort": "number"},
            {"label": "Retrieval", "align": "left", "sort": "string"},
            {"label": "Structure", "align": "left", "sort": "string"},
            {"label": "Reason / Trust", "align": "left", "sort": "string"},
        ]
        winner_score = rows[0].get("primary_metric_value") if rows else None
        for index, row in enumerate(rows, start=1):
            gap = None
            if winner_score is not None and row.get("primary_metric_value") is not None:
                gap = row.get("primary_metric_value") - winner_score
            table_rows.append(
                {
                    "cells": [
                        build_table_cell(str(index), sort_value=index),
                        build_table_cell(
                            display_text(row.get("candidate_id"), missing="not recorded"),
                            subtext=candidate_label(row),
                            monospace=True,
                        ),
                        build_table_cell(
                            format_score(row.get("primary_metric_value"), missing="not scored"),
                            sort_value=row.get("primary_metric_value") if row.get("primary_metric_value") is not None else -1,
                        ),
                        build_table_cell(format_delta(gap, missing="—"), sort_value=gap if gap is not None else -9999),
                        build_table_cell(status_label(row.get("score_status") or "unknown"), badge=status_label(row.get("score_status") or "unknown"), tone=status_tone(str(row.get("score_status") or "unknown"))),
                        build_table_cell(format_runtime(row.get("runtime_seconds")), sort_value=row.get("runtime_seconds") if row.get("runtime_seconds") is not None else -1),
                        build_table_cell(
                            display_text(row.get("retrieval_mode"), missing="not configured"),
                            subtext=(
                                f"top_k={display_text(row.get('retrieval_top_k'), missing='not configured')}; "
                                f"rescue={display_text(row.get('recall_rescue_enabled'), missing='not recorded')}; "
                                f"whole_doc={display_text(row.get('whole_document_mode'), missing='not recorded')}"
                            ),
                        ),
                        build_table_cell(
                            display_text(row.get("structured_output_mode"), missing="not recorded"),
                            subtext=(
                                f"trust={_trust_note(row)}; "
                                f"anchor_valid_rate={format_percent(row.get('anchor_valid_rate'), missing='not recorded')}"
                            ),
                            details=(
                                f"structure_reason={display_text(row.get('structured_output_reason'), missing='none')}; "
                                f"evidence_outcomes={display_text(row.get('evidence_anchor_outcome_counts'), missing='not recorded')}; "
                                f"judge_batches={display_text(row.get('judge_execution_summary'), missing='not recorded')}"
                            ),
                        ),
                        build_table_cell(
                            display_text(row.get("unscored_reason"), missing=display_text(row.get("decision_reason"), missing="no issue recorded")),
                            subtext=display_text(row.get("score_explanation"), missing="no extra trust note recorded"),
                            details=reason_text(row, missing="no additional reason detail recorded"),
                        ),
                    ]
                }
            )
    return {
        "title": "Ranked Candidate Table",
        "subtitle": "All missing values are rendered explicitly rather than left blank.",
        "columns": columns,
        "rows": table_rows,
        "links": [{"label": "Results CSV", "href": "results/results.csv"}] if (Path("results") / "results.csv") else [],
    }


def build_experiment_report_view(experiment_dir: Path) -> dict[str, Any] | None:
    experiment_json = load_json_if_exists(experiment_dir / "experiment.json")
    if not experiment_json:
        return None

    summary = load_json_if_exists(experiment_dir / "summary.json")
    compare_summary = load_json_if_exists(experiment_dir / "compare_summary.json")
    best_candidate = load_json_if_exists(experiment_dir / "best_candidate.json")
    candidate_diagnostics = load_json_if_exists(experiment_dir / "candidate_diagnostics.json")
    run_metadata = load_json_if_exists(experiment_dir.parent / "run_metadata.json")

    primary_metric = str(summary.get("primary_metric") or compare_summary.get("primary_metric") or "content_correctness")
    diagnostics_rows = candidate_diagnostics.get("rows", []) if isinstance(candidate_diagnostics.get("rows"), list) else []
    results_rows = load_csv_rows(experiment_dir / "results" / "results.csv")
    candidate_rows = merge_candidate_rows(results_rows, diagnostics_rows, primary_metric=primary_metric)
    candidate_rows = sort_candidates(candidate_rows)
    study_type = str(experiment_json.get("study_type") or summary.get("study_type") or "compare")
    variant = study_variant(candidate_rows, study_type, experiment_id=str(experiment_json.get("experiment_id") or ""))
    winner_id = _winner_id(summary, best_candidate, compare_summary)
    winner_row = _winner_row(candidate_rows, winner_id)
    best_raw_row = _winner_row(candidate_rows, summary.get("best_raw_candidate_id"))
    holdout = _holdout_payload(summary)
    started_at, ended_at = _time_window(candidate_rows, run_metadata)
    counts = status_counts(candidate_rows)
    winner_label = "Incumbent" if study_type == "optimize" else "Winner"
    main_sentence = (
        _optimize_summary_sentence(
            winner_label=winner_label,
            winner_row=winner_row,
            rows=candidate_rows,
            primary_metric=primary_metric,
            summary=summary,
            holdout=holdout,
        )
        if study_type == "optimize"
        else _compare_summary_sentence(
            winner_label=winner_label,
            winner_row=winner_row,
            rows=candidate_rows,
            primary_metric=primary_metric,
            holdout=holdout,
            variant=variant,
        )
    )
    caveats = _build_caveats(candidate_rows, holdout=holdout, study_type=study_type)
    if str(run_metadata.get("status") or "").lower() == "running" and ended_at not in {"not recorded", "", None}:
        caveats.insert(0, "Wrapper run metadata still says running even though experiment artifacts show an end time; treat wrapper status as stale.")
    next_checks = _build_next_checks(candidate_rows, holdout=holdout, variant=variant, study_type=study_type)
    gap = _gap_to_runner_up(candidate_rows)

    page = {
        "title": f"{display_text(experiment_json.get('experiment_id'), missing='experiment')} decision report",
        "summary_sentence": main_sentence,
        "top_badges": [
            {"text": study_type, "tone": "good"},
            {"text": variant.replace("_", " "), "tone": "neutral"},
            {"text": holdout["status"], "tone": "warn" if holdout["status"] != "completed" else "good"},
            {"text": _status_mix_text(counts), "tone": "neutral"},
        ],
        "hero_meta": [
            {"label": "Winner Label", "value": winner_label, "note": "Study-type-specific semantics."},
            {"label": "Benchmark", "value": display_text(summary.get("benchmark_id"), missing="not recorded"), "note": None},
            {"label": "Benchmark Winner", "value": display_text(best_raw_row.get("candidate_id") if best_raw_row else None, missing="not recorded"), "note": format_score(best_raw_row.get("primary_metric_value") if best_raw_row else None)},
            {"label": "Recommended Default", "value": display_text(winner_row.get("candidate_id") if winner_row else None, missing="not recorded"), "note": _trust_note(winner_row) if winner_row else None},
            {"label": "Started", "value": started_at, "note": None},
            {"label": "Ended", "value": ended_at, "note": None},
            {"label": "Candidates", "value": str(len(candidate_rows)), "note": _status_mix_text(counts)},
            {"label": "Holdout", "value": holdout["status"], "note": display_text(holdout.get("skip_reason"), missing=None)},
        ],
        "executive_cards": [
            {
                "label": winner_label,
                "value": display_text(winner_row.get("candidate_id") if winner_row else None, missing="no winner recorded"),
                "note": candidate_label(winner_row) if winner_row else "No winner candidate record was available.",
                "badges": [{"text": winner_label.lower(), "tone": "good"}] if winner_row else [{"text": "no winner", "tone": "warn"}],
                "class_name": "",
            },
            {
                "label": f"Best Benchmark {primary_metric}",
                "value": format_score(best_raw_row.get("primary_metric_value") if best_raw_row else None),
                "note": f"benchmark_winner={display_text(best_raw_row.get('candidate_id') if best_raw_row else None, missing='not recorded')}; runner-up gap={format_delta(gap, missing='not available')}",
                "badges": [],
                "class_name": "",
            },
            {
                "label": "Trust / Caveats",
                "value": "healthy" if caveats == ["No major report caveats were recorded."] else "review needed",
                "note": caveats[0],
                "badges": [{"text": item.split(".")[0], "tone": "warn"} for item in caveats[:2]],
                "class_name": "",
            },
            {
                "label": "Next Check",
                "value": next_checks[0],
                "note": "; ".join(next_checks[1:]) if len(next_checks) > 1 else None,
                "badges": [{"text": "deterministic", "tone": "neutral"}],
                "class_name": "",
            },
        ],
        "decision_cards": [
            {
                "title": "Why This Candidate Won",
                "lead": "Deterministic explanation derived from score, status, runtime, and holdout state.",
                "items": _build_why_winner(winner_row, candidate_rows, primary_metric=primary_metric, holdout=holdout, study_type=study_type),
                "badges": [{"text": winner_label.lower(), "tone": "good"}] if winner_row else [{"text": "no winner", "tone": "warn"}],
            },
            {
                "title": "Why Others Did Not Win",
                "lead": "Grouped loss reasons rather than a raw artifact dump.",
                "items": _build_why_others(candidate_rows, winner_id),
                "badges": [{"text": "runner-ups", "tone": "neutral"}],
            },
            {
                "title": "Interpretation",
                "lead": "Study-aware takeaways generated from metrics and statuses.",
                "items": _build_interpretation(candidate_rows, study_type=study_type, variant=variant, summary=summary),
                "badges": [{"text": variant.replace("_", " "), "tone": "neutral"}],
            },
            {
                "title": "Trust And Caveats",
                "lead": "Human-facing trust summary; missing data is surfaced explicitly, not silently hidden.",
                "items": caveats,
                "badges": [{"text": "trust", "tone": "warn" if caveats and caveats[0] != "No major report caveats were recorded." else "good"}],
            },
            {
                "title": "Next Checks",
                "lead": "Deterministic follow-ups suggested by the recorded evidence.",
                "items": next_checks,
                "badges": [{"text": "follow-up", "tone": "neutral"}],
            },
        ],
        "candidate_table": _build_candidate_table(candidate_rows, study_type=study_type, primary_metric=primary_metric, winner_id=winner_id),
        "study_cards": _build_study_cards(candidate_rows, study_type=study_type, variant=variant, summary=summary),
        "plots": _build_plot_cards(experiment_dir, study_type=study_type, variant=variant),
        "artifact_links": _build_artifact_links(experiment_dir),
        "provenance_items": _build_provenance_items(winner_row, summary=summary, run_metadata=run_metadata, holdout=holdout),
    }
    return page


def generate_experiment_report(experiment_dir: Path) -> Path | None:
    page = build_experiment_report_view(experiment_dir)
    if page is None:
        return None
    report_html = render_template("experiment.html", page=page)
    report_path = experiment_dir / "report.html"
    report_path.write_text(report_html, encoding="utf-8")
    return report_path
