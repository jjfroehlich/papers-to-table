from __future__ import annotations

from typing import Any

from .contracts import CandidateResult


def _metric_value(result: CandidateResult, metric_name: str) -> float | None:
    if metric_name == "runtime_seconds":
        return result.runtime_seconds
    if metric_name in result.primary_metrics:
        return result.primary_metrics[metric_name]
    if metric_name in result.guardrail_metrics:
        return result.guardrail_metrics[metric_name]
    if metric_name in result.diagnostic_metrics:
        return result.diagnostic_metrics[metric_name]
    return None


def degraded_score_policy(config: dict[str, Any]) -> str:
    return str(config.get("degraded_score_policy", "warn") or "warn")


def is_degraded_score(result: CandidateResult) -> bool:
    return result.score_status == "scored_degraded"


def _secondary_objective_winner(
    incumbent: CandidateResult,
    challenger: CandidateResult,
    objectives: list[dict[str, Any]],
) -> str | None:
    for objective in objectives:
        metric_name = str(objective.get("metric") or "").strip()
        if not metric_name:
            continue
        direction = str(objective.get("direction") or "max").strip().lower()
        min_improvement = float(objective.get("min_improvement", 0.0) or 0.0)
        incumbent_value = _metric_value(incumbent, metric_name)
        challenger_value = _metric_value(challenger, metric_name)
        if incumbent_value is None or challenger_value is None:
            continue
        delta = challenger_value - incumbent_value
        if direction == "min":
            if (-delta) > min_improvement:
                return metric_name
            if delta > 0:
                return None
            continue
        if delta > min_improvement:
            return metric_name
        if delta < 0:
            return None
    return None


def _guardrail_ok(metric_name: str, value: float | None, incumbent_value: float | None, cfg: dict[str, Any]) -> tuple[bool, str]:
    if value is None:
        return False, f"missing guardrail metric: {metric_name}"

    if "min" in cfg and value < float(cfg["min"]):
        return False, f"{metric_name} below min"
    if "max" in cfg and value > float(cfg["max"]):
        return False, f"{metric_name} above max"

    if incumbent_value is not None:
        if "max_delta" in cfg and (value - incumbent_value) > float(cfg["max_delta"]):
            return False, f"{metric_name} delta above max_delta"
        if "min_delta" in cfg and (value - incumbent_value) < float(cfg["min_delta"]):
            return False, f"{metric_name} delta below min_delta"

    return True, "ok"


def _deterministic_gate_ok(result: CandidateResult, *, role: str) -> tuple[bool, str]:
    if result.candidate_status != "completed":
        return False, f"{role} candidate did not complete"

    gate = result.metadata.get("deterministic_gate", {}) if isinstance(result.metadata, dict) else {}
    if not isinstance(gate, dict):
        return False, f"{role} deterministic gate metadata missing"
    if not gate.get("passed", False):
        failures = gate.get("failures", [])
        if isinstance(failures, list) and failures:
            return False, f"{role} deterministic checks failed: {failures[0]}"
        return False, f"{role} deterministic checks failed"
    return True, "ok"


def evaluate_promotion(
    incumbent: CandidateResult,
    challenger: CandidateResult,
    acceptance_cfg: dict[str, Any],
) -> tuple[bool, str]:
    incumbent_ok, incumbent_reason = _deterministic_gate_ok(incumbent, role="incumbent")
    if not incumbent_ok:
        return False, incumbent_reason

    challenger_ok, challenger_reason = _deterministic_gate_ok(challenger, role="challenger")
    if not challenger_ok:
        return False, challenger_reason

    if degraded_score_policy(acceptance_cfg) == "disallow" and is_degraded_score(challenger):
        return False, "degraded_score_disallowed"

    primary_metric = acceptance_cfg["primary_metric"]
    min_improvement = float(acceptance_cfg.get("min_improvement", 0.0))

    incumbent_primary = _metric_value(incumbent, primary_metric)
    challenger_primary = _metric_value(challenger, primary_metric)
    if incumbent_primary is None or challenger_primary is None:
        missing_reason = challenger.unscored_reason or incumbent.unscored_reason
        return False, f"primary metric missing{': ' + missing_reason if missing_reason else ''}"

    guardrails = acceptance_cfg.get("guardrails", {})
    for metric_name, cfg in guardrails.items():
        challenger_value = _metric_value(challenger, metric_name)
        incumbent_value = _metric_value(incumbent, metric_name)
        ok, reason = _guardrail_ok(metric_name, challenger_value, incumbent_value, cfg)
        if not ok:
            return False, reason

    primary_delta = challenger_primary - incumbent_primary
    if primary_delta < min_improvement:
        tie_break_cfg = acceptance_cfg.get("tie_break", {}) if isinstance(acceptance_cfg.get("tie_break"), dict) else {}
        epsilon = float(tie_break_cfg.get("epsilon", 0.0) or 0.0)
        secondary_objectives = tie_break_cfg.get("secondary_objectives", []) if isinstance(tie_break_cfg.get("secondary_objectives"), list) else []
        if abs(primary_delta) <= epsilon and secondary_objectives:
            winner_metric = _secondary_objective_winner(incumbent, challenger, secondary_objectives)
            if winner_metric is not None:
                return True, f"promoted_on_tie_break:{winner_metric}"
        return False, "primary improvement below threshold"

    return True, "promoted"
