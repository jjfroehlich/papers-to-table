from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceQuote(BaseModel):
    quote: str
    page: int
    locator_hint: str | None = None


class HeaderExtractionResult(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    confidence: float = 0.0


class AdjudicationResult(BaseModel):
    row_id: str | None = None
    status: str
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str | None = None


class QueryExpansionResult(BaseModel):
    queries: list[str]


class HydeResult(BaseModel):
    passage: str


class ProposalItem(BaseModel):
    column: str
    proposed_value: str | None
    status: str
    confidence: float
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = None


class GroupExtractionResult(BaseModel):
    proposals: list[ProposalItem]


class VerifyResult(BaseModel):
    column: str
    status: str
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    rationale: str | None = None
