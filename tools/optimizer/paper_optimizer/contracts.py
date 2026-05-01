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
    scored: bool = False
    score_status: str = "failed"
    unscored_reason: str | None = None
    unscored_reason_detail: str | None = None
    runtime_seconds: float | None = None
    runtime_metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    ended_at: str = ""
    candidate_status: str = ""
    promotion_decision: str = ""
    decision_reason: str = ""
    structured_output_mode: str | None = None
    structured_output_reason: str | None = None
    prompt_only_degraded_mode_used: bool = False
    parse_repair_used: bool = False
    extraction_contract_valid: bool | None = None
    extraction_contract_warnings: list[str] = field(default_factory=list)
    retrieval_mode: str | None = None
    retrieval_top_k: int | None = None
    recall_rescue_enabled: bool | None = None
    whole_document_mode: bool | None = None
    whole_document_max_chars: int | None = None
    recall_rescue_used: bool | None = None
    recall_rescue_invocation_count: int | None = None
    whole_document_used_count: int | None = None
    main_app_run_ref: dict[str, Any] = field(default_factory=dict)
    eval_output_ref: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    suite_id: str | None = None
    replicate_index: int | None = None
    replicate_id: str | None = None

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
