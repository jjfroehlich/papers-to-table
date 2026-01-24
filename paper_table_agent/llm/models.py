from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class EvidenceQuote(BaseModel):
    quote: str
    quote_raw: str | None = None
    quote_normalized: str | None = None
    page: int | None = None
    locator_hint: str | None = None
    chunk_pk: str | None = None
    chunk_id: str | None = None
    chunk_idx: int | None = None
    highlight_status: str | None = None
    validation_mode: str | None = None


class HeaderExtractionResult(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    doi: str | None = None
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("year", mode="before")
    @classmethod
    def _coerce_year(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(value)
        return str(value) if isinstance(value, str) else None


class AdjudicationResult(BaseModel):
    row_id: str | None = None
    status: str
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str | None = None
    evidence: list[EvidenceQuote] = Field(default_factory=list)


class QueryExpansionResult(BaseModel):
    queries: list[str]


class HydeResult(BaseModel):
    passage: str


class ProposalItem(BaseModel):
    col_id: int | None = None
    column: str | None = None
    proposed_value: str | None
    status: str
    confidence: float
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    evidence_quality: str | None = None
    needs_more_evidence: bool | None = None
    search_hints: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class GroupExtractionResult(BaseModel):
    proposals: list[ProposalItem]


class VerifyResult(BaseModel):
    column: str
    status: str
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    rationale: str | None = None


class ProposalVerificationResult(BaseModel):
    column: str
    status: str
    rationale: str | None = None
    needs_more_evidence: bool = False
