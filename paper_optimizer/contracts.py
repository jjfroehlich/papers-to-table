from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    prompt_bundle_id: str
    text_model_id: str
    vision_model_id: str | None
    optimizer_knobs: dict[str, Any]
    parent_candidate_id: str | None = None
    round_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaunchResult:
    success: bool
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    started_at: str
    ended_at: str
    duration_seconds: float
    run_id: str | None = None
    run_path: str | None = None
    output_path: str | None = None


@dataclass
class CandidateResult:
    schema_version: str
    experiment_id: str
    study_type: str
    benchmark_id: str
    candidate_id: str
    parent_candidate_id: str | None
    round_index: int | None
    prompt_bundle_id: str
    text_model_id: str
    vision_model_id: str | None
    optimizer_knobs_flat: dict[str, Any]
    primary_metrics: dict[str, float]
    guardrail_metrics: dict[str, float]
    diagnostic_metrics: dict[str, float]
    runtime_seconds: float
    started_at: str
    ended_at: str
    promotion_decision: str
    decision_reason: str
    main_app_run_ref: dict[str, Any]
    eval_output_ref: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoundSummary:
    round_index: int
    incumbent_id_before: str
    promoted_candidate_id: str | None
    incumbent_id_after: str
    challenger_ids: list[str]
    decision_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
