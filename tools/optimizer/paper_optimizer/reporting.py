from __future__ import annotations

import base64
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import read_json


_CONFIG_CACHE: dict[str, dict[str, Any]] = {}


def load_json_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def image_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _config_value(config_path: str | None, key_path: list[str]) -> Any:
    if not config_path:
        return None
    cached = _CONFIG_CACHE.get(config_path)
    if cached is None:
        try:
            cached = read_json(Path(config_path))
        except Exception:
            cached = {}
        _CONFIG_CACHE[config_path] = cached
    current: Any = cached
    for key in key_path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def relative_href(target: Path, *, base_dir: Path) -> str:
    return os.path.relpath(target.resolve(), start=base_dir.resolve()).replace("\\", "/")


def safe_float(value: Any) -> float | None:
    if value in (None, "", "None", "null", "n/a", "N/A", "NA"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(number)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in {"", "None", "null"}:
        return True
    return False


def first_present(mapping: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if not is_missing(value):
            return value
    return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, "", "None", "null"):
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def display_text(value: Any, *, missing: str = "not recorded") -> str:
    if is_missing(value):
        return missing
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def format_score(value: Any, *, missing: str = "not scored", digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return missing
    formatted = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return formatted if formatted else "0"


def format_runtime(value: Any, *, missing: str = "not recorded") -> str:
    seconds = safe_float(value)
    if seconds is None:
        return missing
    if seconds >= 3600:
        return f"{seconds / 3600:.2f} h"
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f} s"


def format_delta(value: Any, *, missing: str = "not available", digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return missing
    sign = "+" if number > 0 else ""
    formatted = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return f"{sign}{formatted}"


def format_percent(value: Any, *, missing: str = "not recorded", digits: int = 1) -> str:
    number = safe_float(value)
    if number is None:
        return missing
    return f"{number * 100:.{digits}f}%"


def format_timestamp(value: Any, *, missing: str = "not recorded") -> str:
    if is_missing(value):
        return missing
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    tz = dt.strftime("%Z") or "UTC"
    return dt.strftime(f"%Y-%m-%d %H:%M {tz}")


def status_from_row(row: dict[str, Any], *, primary_metric: str | None = None) -> str:
    explicit = str(row.get("score_status") or "").strip()
    if explicit:
        return explicit
    candidate_status = str(row.get("candidate_status") or "").strip().lower()
    if candidate_status and candidate_status != "completed":
        return "failed"
    scored = parse_bool(row.get("scored"))
    if scored is True:
        return "scored"
    primary_value = primary_value_from_row(row, primary_metric=primary_metric)
    if primary_value is not None:
        return "scored"
    if not is_missing(row.get("unscored_reason")):
        return "unscored"
    return "unscored"


def status_label(status: str) -> str:
    mapping = {
        "scored": "scored",
        "scored_degraded": "scored degraded",
        "unscored": "unscored",
        "failed": "failed",
    }
    return mapping.get(status, status or "unknown")


def status_tone(status: str) -> str:
    return {
        "scored": "good",
        "scored_degraded": "warn",
        "unscored": "warn",
        "failed": "bad",
        "winner": "good",
        "incumbent": "good",
        "holdout_passed": "good",
        "holdout_failed": "bad",
        "holdout_skipped": "warn",
        "info": "neutral",
    }.get(status, "neutral")


def primary_value_from_row(row: dict[str, Any], *, primary_metric: str | None = None) -> float | None:
    keys = ["primary_metric_value", "primary_score"]
    if primary_metric:
        keys.extend([f"primary.{primary_metric}", f"primary.{primary_metric}_mean"])
    return safe_float(first_present(row, keys))


def reason_text(row: dict[str, Any], *, missing: str = "not recorded") -> str:
    reason = first_present(row, ["unscored_reason", "decision_reason", "score_explanation"])
    detail = first_present(row, ["unscored_reason_detail", "structured_output_reason"])
    if is_missing(reason) and is_missing(detail):
        return missing
    if is_missing(detail):
        return display_text(reason, missing=missing)
    if is_missing(reason):
        return display_text(detail, missing=missing)
    return f"{display_text(reason, missing=missing)}: {display_text(detail, missing=missing)}"


def candidate_label(row: dict[str, Any]) -> str:
    model = display_text(row.get("text_model_id"), missing="model not recorded")
    prompt = display_text(row.get("prompt_bundle_id"), missing="prompt not recorded")
    return f"{display_text(row.get('candidate_id'), missing='candidate')} · {model} · {prompt}"


def merge_candidate_rows(
    results_rows: list[dict[str, Any]],
    diagnostics_rows: list[dict[str, Any]],
    *,
    primary_metric: str | None = None,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in results_rows:
        candidate_id = str(row.get("candidate_id") or "")
        key = candidate_id or f"row_{len(order)}"
        if key not in merged:
            merged[key] = {}
            order.append(key)
        merged[key].update(row)
    for row in diagnostics_rows:
        candidate_id = str(row.get("candidate_id") or "")
        key = candidate_id or f"diag_{len(order)}"
        if key not in merged:
            merged[key] = {}
            order.append(key)
        for field, value in row.items():
            if not is_missing(value) or field not in merged[key]:
                merged[key][field] = value
    normalized = [normalize_candidate_row(merged[key], primary_metric=primary_metric) for key in order]
    return normalized


def normalize_candidate_row(row: dict[str, Any], *, primary_metric: str | None = None) -> dict[str, Any]:
    primary_value = primary_value_from_row(row, primary_metric=primary_metric)
    resolved_config_path = first_present(row, ["main_app_resolved_config_path"])
    normalized = {
        "candidate_id": first_present(row, ["candidate_id"]),
        "parent_candidate_id": first_present(row, ["parent_candidate_id"]),
        "round_index": safe_int(first_present(row, ["round_index"])),
        "study_type": first_present(row, ["study_type"]),
        "candidate_status": first_present(row, ["candidate_status"]),
        "score_status": status_from_row(row, primary_metric=primary_metric),
        "scored": parse_bool(first_present(row, ["scored"])),
        "unscored_reason": first_present(row, ["unscored_reason"]),
        "unscored_reason_detail": first_present(row, ["unscored_reason_detail"]),
        "primary_metric_value": primary_value,
        "runtime_seconds": safe_float(first_present(row, ["runtime_seconds"])),
        "started_at": first_present(row, ["started_at"]),
        "ended_at": first_present(row, ["ended_at"]),
        "text_model_id": first_present(row, ["text_model_id"]),
        "prompt_bundle_id": first_present(row, ["prompt_bundle_id"]),
        "vision_model_id": first_present(row, ["vision_model_id"]),
        "retrieval_mode": first_present(row, ["retrieval_mode", "main_retrieval_mode", "knob.retrieval_mode"]) or _config_value(resolved_config_path, ["retrieval", "mode"]),
        "retrieval_top_k": first_present(row, ["retrieval_top_k", "knob.retrieval_top_k"]) or _config_value(resolved_config_path, ["retrieval", "top_k"]),
        "recall_rescue_enabled": parse_bool(first_present(row, ["recall_rescue_enabled", "knob.recall_rescue_enabled"])) if first_present(row, ["recall_rescue_enabled", "knob.recall_rescue_enabled"]) is not None else parse_bool(_config_value(resolved_config_path, ["retrieval", "recall_rescue_enabled"])),
        "whole_document_mode": parse_bool(first_present(row, ["whole_document_mode", "knob.whole_document_mode"])) if first_present(row, ["whole_document_mode", "knob.whole_document_mode"]) is not None else parse_bool(_config_value(resolved_config_path, ["retrieval", "whole_document_mode"])),
        "whole_document_max_chars": first_present(row, ["whole_document_max_chars", "knob.whole_document_max_chars"]) or _config_value(resolved_config_path, ["retrieval", "whole_document_max_chars"]),
        "recall_rescue_used": parse_bool(first_present(row, ["recall_rescue_used"])),
        "recall_rescue_invocation_count": safe_int(first_present(row, ["recall_rescue_invocation_count"])),
        "structured_output_mode": first_present(row, ["structured_output_mode", "main_structured_output_mode"]),
        "structured_output_reason": first_present(row, ["structured_output_reason", "main_structured_output_reason"]),
        "prompt_only_degraded_mode_used": parse_bool(first_present(row, ["prompt_only_degraded_mode_used"])),
        "parse_repair_used": parse_bool(first_present(row, ["parse_repair_used"])),
        "extraction_contract_valid": parse_bool(first_present(row, ["extraction_contract_valid"])),
        "extraction_contract_warnings": first_present(row, ["extraction_contract_warnings"]),
        "promotion_decision": first_present(row, ["promotion_decision"]),
        "decision_reason": first_present(row, ["decision_reason"]),
        "score_explanation": first_present(row, ["score_explanation"]),
        "judge_disagreement": safe_float(first_present(row, ["judge_disagreement", "diagnostic.judge_disagreement"])),
        "correctness_judge_a": safe_float(first_present(row, ["correctness_judge_a", "primary.correctness_judge_a", "diagnostic.correctness_judge_a"])),
        "correctness_judge_b": safe_float(first_present(row, ["correctness_judge_b", "primary.correctness_judge_b", "diagnostic.correctness_judge_b"])),
        "scored_cell_count": safe_int(first_present(row, ["scored_cell_count", "diagnostic.scored_cell_count"])),
        "judge_text_scored_cell_count": safe_int(first_present(row, ["judge_text_scored_cell_count", "diagnostic.judge_text_scored_cell_count"])),
        "unscored_text_cell_count": safe_int(first_present(row, ["unscored_text_cell_count", "diagnostic.unscored_text_cell_count"])),
        "judge_request_failed_count": safe_int(first_present(row, ["judge_request_failed_count", "diagnostic.judge_request_failed_count"])),
        "missing_proposal_count": safe_int(first_present(row, ["missing_proposal_count", "diagnostic.missing_proposal_count"])),
        "filled_on_gold_empty_count": safe_int(first_present(row, ["filled_on_gold_empty_count", "diagnostic.filled_on_gold_empty_count"])),
        "candidate_manifest_path": first_present(row, ["candidate_manifest_path"]),
        "candidate_bundle_dir": first_present(row, ["candidate_bundle_dir"]),
        "main_app_run_path": first_present(row, ["main_app_run_path"]),
        "main_app_resolved_config_path": first_present(row, ["main_app_resolved_config_path"]),
        "main_app_overlay_path": first_present(row, ["main_app_overlay_path"]),
        "eval_output_path": first_present(row, ["eval_output_path"]),
        "eval_summary_path": first_present(row, ["eval_summary_path"]),
    }
    return normalized


def sort_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"scored": 0, "scored_degraded": 1, "unscored": 2, "failed": 3}
    return sorted(
        rows,
        key=lambda row: (
            priority.get(str(row.get("score_status") or ""), 9),
            -(row.get("primary_metric_value") if row.get("primary_metric_value") is not None else float("-inf")),
            row.get("runtime_seconds") if row.get("runtime_seconds") is not None else float("inf"),
            display_text(row.get("candidate_id"), missing="zzz"),
        ),
    )


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"scored": 0, "scored_degraded": 0, "unscored": 0, "failed": 0}
    for row in rows:
        status = str(row.get("score_status") or "").strip() or "unscored"
        counts[status] = counts.get(status, 0) + 1
    return counts


def study_variant(rows: list[dict[str, Any]], study_type: str, experiment_id: str | None = None) -> str:
    if study_type != "compare":
        return study_type
    retrieval_modes = {display_text(row.get("retrieval_mode"), missing="") for row in rows if not is_missing(row.get("retrieval_mode"))}
    retrieval_top_k = {display_text(row.get("retrieval_top_k"), missing="") for row in rows if not is_missing(row.get("retrieval_top_k"))}
    prompts = {display_text(row.get("prompt_bundle_id"), missing="") for row in rows if not is_missing(row.get("prompt_bundle_id"))}
    models = {display_text(row.get("text_model_id"), missing="") for row in rows if not is_missing(row.get("text_model_id"))}
    experiment_name = (experiment_id or "").lower()
    if len(retrieval_modes) > 1 or len(retrieval_top_k) > 1 or "retrieval" in experiment_name:
        return "retrieval_compare"
    if len(prompts) > 1 or "prompt" in experiment_name:
        return "prompt_compare"
    if len(models) > 1 or "model" in experiment_name:
        return "model_compare"
    return "compare"


def build_table_cell(
    text: str,
    *,
    subtext: str | None = None,
    badge: str | None = None,
    tone: str | None = None,
    sort_value: str | float | int | None = None,
    monospace: bool = False,
    details: str | None = None,
) -> dict[str, Any]:
    return {
        "text": text,
        "subtext": subtext,
        "badge": badge,
        "tone": tone or "neutral",
        "sort": sort_value if sort_value is not None else text,
        "monospace": monospace,
        "details": details,
    }


def build_plot_guidance(stem: str) -> dict[str, str]:
    guidance = {
        "compare_primary_by_candidate": {
            "what": "Primary score for each compared candidate.",
            "how": "Higher bars are better. Bars marked NA were not scored and should not be treated as ties.",
            "watch": "Look for a clear leader and for any missing-score bars clustered around the top ranks.",
        },
        "compare_correctness_vs_runtime": {
            "what": "Primary score against runtime for each candidate.",
            "how": "Higher is better on y and lower is better on x, so the upper-left region is strongest.",
            "watch": "A tiny score gain with a large runtime increase may not be worth promoting operationally.",
        },
        "compare_score_status_counts": {
            "what": "Count of scored, degraded, unscored, and failed candidates.",
            "how": "Treat this as a run-health summary before trusting the ranking table.",
            "watch": "Large unscored or failed counts mean the winner may be provisional.",
        },
        "compare_unscored_reasons": {
            "what": "Why candidates did not produce a usable score.",
            "how": "Taller bars indicate repeated failure modes rather than isolated incidents.",
            "watch": "One dominant reason often points to a fixable contract or judge issue.",
        },
        "compare_primary_by_text_model": {
            "what": "Best score reached by each text model family.",
            "how": "Use it to compare model ceilings, not single-candidate runtime tradeoffs.",
            "watch": "If one model wins only narrowly, inspect candidate-level variance before standardizing on it.",
        },
        "compare_primary_by_prompt_bundle": {
            "what": "Best score reached by each prompt bundle.",
            "how": "Treat higher bars as stronger prompt ceilings for this benchmark.",
            "watch": "A prompt that wins while also degrading structure less is usually the safer default.",
        },
        "compare_primary_by_retrieval_top_k": {
            "what": "Best score reached at each retrieval depth.",
            "how": "Read it as a sweep of retrieval depth rather than a single-candidate ranking.",
            "watch": "A flat or declining curve suggests extra retrieval is adding cost without helping quality.",
        },
        "compare_primary_by_knob_retrieval_top_k": {
            "what": "Best score reached at each retrieval depth.",
            "how": "Higher bars show the strongest observed result for each top_k setting.",
            "watch": "If the best score peaks early, larger contexts may be unnecessary.",
        },
        "compare_judge_a_vs_judge_b": {
            "what": "Agreement between judge A and judge B on candidate correctness.",
            "how": "Points near the diagonal indicate agreement; farther points indicate higher disagreement.",
            "watch": "Wide spread means ranking confidence is lower even when the mean score looks strong.",
        },
        "compare_dev_vs_holdout": {
            "what": "Dev score versus holdout score for the same candidates.",
            "how": "Parallel lines suggest the dev ordering generalizes; divergence suggests overfitting.",
            "watch": "A winner that drops sharply on holdout needs closer review before adoption.",
        },
        "optimize_best_by_round": {
            "what": "Best score observed in each optimization round.",
            "how": "Read it round by round to see whether challengers found better points in the search space.",
            "watch": "Flat lines indicate a ceiling, duplicate search, or acceptance gates blocking movement.",
        },
        "optimize_history_best_so_far": {
            "what": "Incumbent best-so-far score over time.",
            "how": "Upward steps mean genuine optimization progress; flat segments mean the incumbent held.",
            "watch": "Long flat stretches suggest the search surface or acceptance policy may need revision.",
        },
        "optimize_score_delta_by_round": {
            "what": "Score improvement or regression relative to the current incumbent by round.",
            "how": "Positive bars show improvement opportunities; zero or negative bars show stalled search.",
            "watch": "Small positive deltas inside the tie zone may still fail promotion.",
        },
        "optimize_decision_counts_by_round": {
            "what": "Promotion, rejection, and incumbent counts by round.",
            "how": "Use it to separate search activity from actual accepted progress.",
            "watch": "Many rejections with few unique challengers often indicates search exhaustion.",
        },
        "optimize_runtime_by_round": {
            "what": "Average runtime per optimization round.",
            "how": "Compare runtime trend against score trend to judge efficiency.",
            "watch": "Rising runtime without better scores usually means diminishing returns.",
        },
        "optimize_score_status_counts": {
            "what": "Count of scored, degraded, unscored, and failed optimize candidates.",
            "how": "Read this before trusting a stable incumbent as a meaningful success.",
            "watch": "Many unscored challengers can hide unexplored good configurations.",
        },
        "optimize_unscored_reasons": {
            "what": "Primary reasons optimize candidates did not produce usable scores.",
            "how": "Repeated bars indicate systematic bottlenecks in the search loop.",
            "watch": "Dominant contract or judge failures should usually be fixed before widening the search.",
        },
        "optimize_all_scores_by_round": {
            "what": "All scored candidate outcomes by round.",
            "how": "Dense clusters show the search spread; higher points show exceptional challengers.",
            "watch": "If the cloud narrows quickly, the search may have converged early.",
        },
        "optimize_primary_by_knob_retrieval_top_k": {
            "what": "Primary score by retrieval depth within optimize candidates.",
            "how": "Use it to see whether retrieval depth is part of the winning pattern.",
            "watch": "If only one depth appears near the top, the knob may deserve tighter bounds.",
        },
        "pipeline_stage_trajectory": {
            "what": "Best stage score from early compare stages through final optimize.",
            "how": "Upward moves show genuine pipeline gains; flat moves show validation or no net improvement.",
            "watch": "A late flat stage means the earlier stage likely found the real winner.",
        },
        "pipeline_stage_durations": {
            "what": "Approximate stage runtime based on candidate durations.",
            "how": "Use it to identify which stage consumed most of the overnight budget.",
            "watch": "A long stage with little score gain is the first place to optimize the pipeline.",
        },
        "pipeline_candidate_frontier": {
            "what": "All pipeline candidates plotted by score and runtime, colored by stage.",
            "how": "Upper-left is strongest. Compare stages to see whether later stages found better tradeoffs.",
            "watch": "If the frontier is already dominated by an early stage, later stages mostly validated it.",
        },
    }
    return guidance.get(
        stem,
        {
            "what": "A diagnostic plot generated for this study.",
            "how": "Read the axes and legend first, then compare relative position and spread.",
            "watch": "Treat missing or degraded candidates as a trust signal, not just a visual nuisance.",
        },
    )
