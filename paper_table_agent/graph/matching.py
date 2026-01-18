from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import AdjudicationResult, HeaderExtractionResult
from paper_table_agent.llm.prompts import render_prompt


@dataclass
class RowCandidate:
    row_id: str
    title: str
    authors: str
    year: str
    score: float
    title_score: float
    author_score: float
    year_bonus: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "score": round(self.score, 4),
            "title_score": round(self.title_score, 4),
            "author_score": round(self.author_score, 4),
            "year_bonus": round(self.year_bonus, 4),
        }


def extract_header(client: LlmClient, text: str) -> HeaderExtractionResult:
    prompt = render_prompt("match_header_extract.md", text=text)
    return client.complete_json(prompt, HeaderExtractionResult)


def shortlist_candidates(
    header: HeaderExtractionResult,
    rows: list[dict[str, Any]],
    top_k: int,
    year_tolerance: int = 1,
) -> list[RowCandidate]:
    if not header.title:
        return []
    titles = {row["row_id"]: row.get("title", "") for row in rows}
    matches = process.extract(header.title, titles, scorer=fuzz.token_sort_ratio, limit=top_k)
    header_authors = _author_last_names(header.authors)
    candidates: list[RowCandidate] = []
    row_lookup = {row["row_id"]: row for row in rows}
    for _, score, row_id in matches:
        row = row_lookup.get(row_id)
        if not row:
            continue
        year = str(row.get("year") or "")
        author_score = _author_overlap(header_authors, _author_last_names(_split_authors(row.get("authors", ""))))
        title_score = score / 100.0
        year_bonus = _year_bonus(header.year, year, year_tolerance)
        combined = min(1.0, title_score * 0.8 + author_score * 0.2 + year_bonus)
        candidates.append(
            RowCandidate(
                row_id=row_id,
                title=row.get("title") or "",
                authors=row.get("authors") or "",
                year=year,
                score=combined,
                title_score=title_score,
                author_score=author_score,
                year_bonus=year_bonus,
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_k]


def _author_last_names(authors: list[str]) -> set[str]:
    names: set[str] = set()
    for author in authors:
        parts = str(author).replace(",", " ").split()
        if parts:
            names.add(parts[-1].lower())
    return names


def _split_authors(authors: str | list[str]) -> list[str]:
    if isinstance(authors, list):
        return [str(author).strip() for author in authors if str(author).strip()]
    cleaned = authors.replace(" and ", ",").replace(";", ",")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def _author_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def _year_bonus(header_year: str | None, row_year: str | None, tolerance: int) -> float:
    if not header_year or not row_year:
        return 0.0
    try:
        header_value = int(header_year)
        row_value = int(row_year)
    except ValueError:
        return 0.0
    if abs(header_value - row_value) <= tolerance:
        return 0.02
    return 0.0


def deterministic_match(
    header: HeaderExtractionResult,
    candidates: list[RowCandidate],
    threshold: float,
) -> AdjudicationResult | None:
    above = [candidate for candidate in candidates if candidate.score >= threshold]
    if len(above) == 1:
        best = above[0]
        return AdjudicationResult(
            row_id=best.row_id,
            status="matched",
            top_candidates=[candidate.to_payload() for candidate in candidates],
            confidence=best.score,
            rationale="Single candidate above threshold",
            evidence=header.evidence,
        )
    if not above:
        return AdjudicationResult(
            row_id=None,
            status="unmatched",
            top_candidates=[candidate.to_payload() for candidate in candidates],
            confidence=0.0,
            rationale="No candidates above threshold",
            evidence=header.evidence,
        )
    return None


def adjudicate_match(client: LlmClient, header: HeaderExtractionResult, candidates: list[RowCandidate]) -> AdjudicationResult:
    prompt = render_prompt(
        "match_adjudicate.md",
        header=json.dumps(header.model_dump(mode="json")),
        candidates=json.dumps([candidate.to_payload() for candidate in candidates], indent=2),
    )
    return client.complete_json(prompt, AdjudicationResult)


def build_match_record(pdf_id: str, result: AdjudicationResult) -> dict[str, Any]:
    return {
        "match_id": str(uuid.uuid4()),
        "pdf_id": pdf_id,
        "row_id": result.row_id,
        "confidence": result.confidence,
        "status": result.status,
        "evidence": [item.model_dump(mode="json") for item in result.evidence],
        "rationale": result.rationale,
    }
