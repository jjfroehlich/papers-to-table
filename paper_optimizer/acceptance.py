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

    primary_metric = acceptance_cfg["primary_metric"]
    min_improvement = float(acceptance_cfg.get("min_improvement", 0.0))

    incumbent_primary = _metric_value(incumbent, primary_metric)
    challenger_primary = _metric_value(challenger, primary_metric)
    if incumbent_primary is None or challenger_primary is None:
        return False, "primary metric missing"

    if (challenger_primary - incumbent_primary) < min_improvement:
        return False, "primary improvement below threshold"

    guardrails = acceptance_cfg.get("guardrails", {})
    for metric_name, cfg in guardrails.items():
        challenger_value = _metric_value(challenger, metric_name)
        incumbent_value = _metric_value(incumbent, metric_name)
        ok, reason = _guardrail_ok(metric_name, challenger_value, incumbent_value, cfg)
        if not ok:
            return False, reason

    return True, "promoted"
