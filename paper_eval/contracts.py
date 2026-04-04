from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STRUCTURED_FIELD_TYPES = {"boolean", "categorical", "numeric"}


@dataclass(frozen=True)
class NumericTolerance:
    abs_tol: float = 0.0
    rel_tol: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"abs_tol": self.abs_tol, "rel_tol": self.rel_tol}


@dataclass
class ColumnSchema:
    name: str
    field_type: str | None = None
    description: str | None = None
    allowed_values: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    scoring_policy: str | None = None
    numeric_tolerance: NumericTolerance | None = None


@dataclass
class EvaluatorSchema:
    columns: dict[str, ColumnSchema] = field(default_factory=dict)
    global_numeric_tolerance: NumericTolerance = field(default_factory=NumericTolerance)

    def column(self, column_name: str) -> ColumnSchema | None:
        return self.columns.get(column_name)


@dataclass
class EvidenceItem:
    page: int | None = None
    quote_text: str | None = None
    evidence_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMetadata:
    run_id: str
    run_dir: Path
    run_mode: str | None = None
    provider_token: str | None = None
    text_model_id: str | None = None
    vision_model_id: str | None = None
    parser_identity: str | None = None
    parser_version: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None
    schema_hash: str | None = None
    schema_version: str | None = None
    config_hash: str | None = None
    page_count: int | None = None
    gold_source_ref: str | None = None
    gold_table_hash: str | None = None
    gold_table_snapshot_path: str | None = None
    masked_table_hash: str | None = None
    masked_table_snapshot_path: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def flat_metadata(self) -> dict[str, Any]:
        row = {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "mode": self.run_mode,
            "run_mode": self.run_mode,
            "provider_token": self.provider_token,
            "model_id": self.text_model_id,
            "text_model_id": self.text_model_id,
            "vision_model_id": self.vision_model_id,
            "parser_identity": self.parser_identity,
            "parser_version": self.parser_version,
            "parser_identity_version": _join_identity_and_version(self.parser_identity, self.parser_version),
            "prompt_identity": self.prompt_version or self.prompt_hash,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "schema_identity": self.schema_version or self.schema_hash,
            "schema_hash": self.schema_hash,
            "schema_version": self.schema_version,
            "config_hash": self.config_hash,
            "page_count": self.page_count,
            "gold_source_ref": self.gold_source_ref,
            "gold_table_hash": self.gold_table_hash,
            "gold_table_snapshot_path": self.gold_table_snapshot_path,
            "masked_table_hash": self.masked_table_hash,
            "masked_table_snapshot_path": self.masked_table_snapshot_path,
        }
        row.update(_flatten_scalar_mapping(self.extras))
        return row


@dataclass
class ProposalRecord:
    run_id: str
    row_id: str
    column_name: str
    cell_id: str
    proposed_value: Any
    pdf_id: str | None = None
    state: str | None = None
    support: Any = None
    field_type: str | None = None
    allowed_values: list[str] = field(default_factory=list)
    numeric_value_form: str | None = None
    scoring_policy: str | None = None
    aliases: dict[str, str] = field(default_factory=dict)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    row_index: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def join_key(self) -> tuple[str, str]:
        return (self.row_id, self.column_name)


@dataclass
class LoadedRun:
    run_dir: Path
    metadata: RunMetadata
    proposals: list[ProposalRecord]
    page_text_by_page: dict[int, str] = field(default_factory=dict)
    contract_warnings: list[str] = field(default_factory=list)


@dataclass
class GoldCell:
    row_id: str
    column_name: str
    raw_value: Any
    is_present: bool
    sheet_name: str | None = None
    cell_id: str | None = None
    row_index: int | None = None

    @property
    def join_key(self) -> tuple[str, str]:
        return (self.row_id, self.column_name)


@dataclass
class GoldDataset:
    source_path: Path
    sheet_name: str | None
    cells: list[GoldCell]


@dataclass
class NormalizedNumber:
    kind: str
    lower: float
    upper: float
    approx: bool = False
    raw_text: str | None = None

    @property
    def is_scalar(self) -> bool:
        return self.lower == self.upper

    @property
    def center(self) -> float:
        return (self.lower + self.upper) / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "lower": self.lower,
            "upper": self.upper,
            "approx": self.approx,
            "raw_text": self.raw_text,
        }


@dataclass
class ResolvedFieldConfig:
    column_name: str
    field_type: str
    scoring_policy: str
    description: str | None = None
    allowed_values: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    numeric_tolerance: NumericTolerance = field(default_factory=NumericTolerance)


@dataclass
class ComparisonResult:
    is_correct: bool
    normalized_gold: Any
    normalized_proposed: Any
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredCell:
    record_kind: str
    run_id: str
    row_id: str | None
    column_name: str | None
    cell_id: str | None
    gold_value: Any
    proposed_value: Any
    field_type: str | None
    scoring_policy: str | None
    is_gold_present: bool
    is_gold_empty: bool
    was_scored: bool
    is_correct: bool | None
    join_status: str
    comparison_kind: str
    evidence_outcome: str
    proposal_count: int
    anchor_valid: bool = False
    evidence_present_but_unvalidated: bool = False
    row_index: int | None = None
    normalized_gold: Any = None
    normalized_proposed: Any = None
    judge_provider: str | None = None
    judge_configured_model_id: str | None = None
    judge_resolved_model_id: str | None = None
    judge_verdict: str | None = None
    judge_model_id: str | None = None
    judge_prompt_version: str | None = None
    judge_prompt_hash: str | None = None
    judge_temperature: float | None = None
    judge_input_hash: str | None = None
    diagnostic_flags: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    selected_proposal_state: str | None = None


@dataclass
class RunSummary:
    run_id: str
    run_dir: Path
    gold_source: Path
    gold_sheet: str | None
    metrics: dict[str, Any]
    metadata: dict[str, Any]
    contract_warnings: list[str] = field(default_factory=list)
    join_diagnostics: list[str] = field(default_factory=list)


@dataclass
class EvidenceValidationResult:
    outcome: str
    anchor_valid: bool
    evidence_present_but_unvalidated: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgeConfig:
    model_id: str
    provider: str = "lm_studio"
    api_base: str | None = None
    api_key: str | None = None
    prompt_version: str = "batch3-text-judge-v1"
    temperature: float = 0.0
    max_field_name_chars: int = 80
    max_field_description_chars: int = 240
    max_value_chars: int = 600
    max_evidence_chars: int = 240
    max_output_tokens: int = 120


@dataclass(frozen=True)
class JudgeRequest:
    run_id: str
    row_id: str | None
    column_name: str
    cell_id: str | None
    field_description: str | None
    gold_value: str
    proposed_value: str
    normalized_gold: str
    normalized_proposed: str
    evidence_excerpt: str | None
    prompt_version: str
    prompt_hash: str
    input_hash: str
    was_truncated: bool


@dataclass(frozen=True)
class JudgeResponse:
    verdict: str
    rationale_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgeRecord:
    run_id: str
    row_id: str | None
    column_name: str
    cell_id: str | None
    judge_provider: str
    judge_configured_model_id: str
    judge_resolved_model_id: str | None
    judge_model_id: str
    judge_prompt_version: str
    judge_prompt_hash: str
    judge_temperature: float
    judge_verdict: str
    judge_input_hash: str
    rationale_label: str | None = None
    request_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    input_was_truncated: bool = False
    normalized_gold: str | None = None
    normalized_proposed: str | None = None
    evidence_excerpt: str | None = None


@dataclass
class ScoreRunResult:
    scored_cells: list[ScoredCell]
    judge_records: list[JudgeRecord] = field(default_factory=list)


def _join_identity_and_version(identity: str | None, version: str | None) -> str | None:
    if identity and version:
        return f"{identity}@{version}"
    return identity or version


def _flatten_scalar_mapping(payload: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        flattened_key = f"{prefix}{key}" if not prefix else f"{prefix}__{key}"
        if isinstance(value, dict):
            flat.update(_flatten_scalar_mapping(value, prefix=flattened_key))
        elif isinstance(value, list):
            if all(not isinstance(item, (dict, list)) for item in value):
                flat[flattened_key] = "|".join("" if item is None else str(item) for item in value)
        elif value is None or isinstance(value, (str, int, float, bool)):
            flat[flattened_key] = value
    return flat
