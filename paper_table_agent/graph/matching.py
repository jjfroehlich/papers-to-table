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


def extract_header(client: LlmClient, text: str) -> HeaderExtractionResult:
    prompt = render_prompt("match_header_extract.md", text=text)
    return client.complete_json(prompt, HeaderExtractionResult)


def shortlist_candidates(header: HeaderExtractionResult, rows: list[dict[str, Any]], top_k: int) -> list[RowCandidate]:
    titles = {row["row_id"]: row.get("title", "") for row in rows}
    matches = process.extract(header.title or "", titles, scorer=fuzz.token_sort_ratio, limit=top_k)
    header_authors = _author_last_names(header.authors)
    candidates: list[RowCandidate] = []
    for _, score, row_id in matches:
        row = next(row for row in rows if row["row_id"] == row_id)
        year = str(row.get("year") or "")
        if header.year and year:
            try:
                year_value = int(year)
                header_value = int(header.year)
                if header_value not in {year_value, year_value - 1, year_value + 1}:
                    continue
            except ValueError:
                pass
        overlap = _author_overlap(header_authors, _author_last_names([row.get("authors", "")]))
        adjusted = score + overlap * 5.0
        candidates.append(
            RowCandidate(
                row_id=row_id,
                title=row.get("title") or "",
                authors=row.get("authors") or "",
                year=year,
                score=adjusted,
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


def _author_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def adjudicate_match(client: LlmClient, header: HeaderExtractionResult, candidates: list[RowCandidate]) -> AdjudicationResult:
    prompt = render_prompt(
        "match_adjudicate.md",
        header=json.dumps(header.model_dump(mode="json")),
        candidates=json.dumps([candidate.__dict__ for candidate in candidates], indent=2),
    )
    return client.complete_json(prompt, AdjudicationResult)


def build_match_record(pdf_id: str, result: AdjudicationResult) -> dict[str, Any]:
    return {
        "match_id": str(uuid.uuid4()),
        "pdf_id": pdf_id,
        "row_id": result.row_id,
        "confidence": result.confidence,
        "status": result.status,
        "evidence": [],
        "rationale": result.rationale,
    }
