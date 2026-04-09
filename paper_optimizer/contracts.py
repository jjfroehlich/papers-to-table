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
    summary_path: str | None = None
    working_dir: str | None = None
    output_path: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateResult:
    schema_version: str
    experiment_id: str
    study_type: str
    benchmark_id: str
    candidate_id: str
    parent_candidate_id: str | None
    round_index: int | None
    candidate_hash: str
    candidate_manifest_path: str
    candidate_bundle_dir: str
    prompt_bundle_id: str
    text_model_id: str
    vision_model_id: str | None
    optimizer_knobs_flat: dict[str, Any]
    primary_metrics: dict[str, float]
    guardrail_metrics: dict[str, float]
    diagnostic_metrics: dict[str, float]
    runtime_seconds: float | None
    runtime_metadata: dict[str, Any]
    started_at: str
    ended_at: str
    candidate_status: str
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


@dataclass(frozen=True)
class ProposerRequest:
    round_index: int
    max_candidates: int
    incumbent: dict[str, Any]
    allowed_prompt_bundle_ids: list[str]
    allowed_text_model_ids: list[str]
    allowed_vision_model_ids: list[str]
    allowed_numeric_knobs: dict[str, list[float | int]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposedCandidateDelta:
    prompt_bundle_id: str | None = None
    text_model_id: str | None = None
    vision_model_id: str | None = None
    optimizer_knobs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposerResponse:
    candidates: list[ProposedCandidateDelta] = field(default_factory=list)
    response_mode: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
