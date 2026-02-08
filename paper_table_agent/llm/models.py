from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    quote: str = Field(alias="quote_text")
    source_ref: str | None = None
    anchor_id: str | None = None
    why_it_matters: str | None = None
    why_it_supports: str | None = Field(default=None, alias="why_it_supports")
    numeric_value: str | float | None = None
    quote_raw: str | None = None
    quote_normalized: str | None = None
    quote_start: int | None = None
    quote_end: int | None = None
    page: int | None = None
    locator_hint: str | None = None
    pdf_id: str | None = None
    chunk_pk: str | None = None
    chunk_id: str | None = None
    chunk_idx: int | None = None
    highlight_status: str | None = None
    highlight_strategy: str | None = None
    highlight_match_score: float | None = None
    highlight_rejection_reason: str | None = None
    rects: list[list[float]] | None = None
    validation_mode: str | None = None


class HeaderExtractionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    doi: str | None = None
    evidence: list[EvidenceQuote] = Field(default_factory=list, alias="evidence_items")
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
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    row_id: str | None = None
    status: str
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str | None = None
    evidence: list[EvidenceQuote] = Field(default_factory=list, alias="evidence_items")

    @field_validator("top_candidates", mode="before")
    @classmethod
    def _coerce_top_candidates(cls, value: object) -> list[dict[str, Any]]:
        if value is None:
            return []
        payload = value
        if isinstance(value, str):
            payload = _parse_jsonish(value) or [value]
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        results: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                results.append(item)
                continue
            if isinstance(item, str):
                parsed = _parse_jsonish(item)
                if isinstance(parsed, dict):
                    results.append(parsed)
                else:
                    results.append({"row_id": item})
        return results

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, value: object) -> list[EvidenceQuote]:
        if value is None:
            return []
        payload = value
        if isinstance(value, str):
            payload = _parse_jsonish(value) or [value]
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        results: list[EvidenceQuote] = []
        for item in payload:
            if isinstance(item, EvidenceQuote):
                results.append(item)
            elif isinstance(item, dict):
                results.append(EvidenceQuote.model_validate(item))
            elif isinstance(item, str):
                results.append(EvidenceQuote.model_validate({"quote_text": item}))
        return results


def _parse_jsonish(value: str) -> object | None:
    try:
        return json.loads(value)
    except Exception:
        return None


class QueryExpansionResult(BaseModel):
    queries: list[str]


class HydeResult(BaseModel):
    passage: str


class ContextSummaryResult(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)


class PaperMemoryResult(BaseModel):
    summary: str
    notes: list[dict[str, Any]] = Field(default_factory=list)


class ProposalItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    col_id: int | None = None
    column: str | None = None
    proposed_value: str | None
    status: str
    confidence: float
    evidence: list[EvidenceQuote] = Field(default_factory=list, alias="evidence_items")
    evidence_quality: str | None = None
    needs_more_evidence: bool | None = None
    needs_more_context: bool | None = None
    search_hints: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = Field(default=None, alias="rationale")


class GroupExtractionResult(BaseModel):
    proposals: list[ProposalItem]


class VerifyResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    column: str
    status: str
    evidence: list[EvidenceQuote] = Field(default_factory=list, alias="evidence_items")
    rationale: str | None = None


class ProposalVerificationResult(BaseModel):
    column: str
    status: str
    rationale: str | None = None
    needs_more_evidence: bool = False
