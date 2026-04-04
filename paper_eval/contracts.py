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
    extras: dict[str, Any] = field(default_factory=dict)

    def flat_metadata(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "run_mode": self.run_mode,
            "provider_token": self.provider_token,
            "text_model_id": self.text_model_id,
            "vision_model_id": self.vision_model_id,
            "parser_identity": self.parser_identity,
            "parser_version": self.parser_version,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "schema_hash": self.schema_hash,
            "schema_version": self.schema_version,
            "config_hash": self.config_hash,
        }


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
    row_index: int | None = None
    normalized_gold: Any = None
    normalized_proposed: Any = None
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
