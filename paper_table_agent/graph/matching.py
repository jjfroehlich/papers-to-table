from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import fitz
from rapidfuzz import fuzz, process

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import AdjudicationResult, HeaderExtractionResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.text.normalization import normalize_key


@dataclass
class RowCandidate:
    row_id: str
    title: str
    authors: str
    year: str
    doi: str
    score: float
    title_score: float
    author_score: float
    year_bonus: float
    doi_bonus: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "score": round(self.score, 4),
            "title_score": round(self.title_score, 4),
            "author_score": round(self.author_score, 4),
            "year_bonus": round(self.year_bonus, 4),
            "doi_bonus": round(self.doi_bonus, 4),
        }


def extract_header(client: LlmClient, text: str, pdf_id: str | None = None) -> HeaderExtractionResult:
    prompt = render_prompt("match_header_extract.md", _prompt_meta={"pdf_id": pdf_id}, text=text)
    return client.complete_json(prompt, HeaderExtractionResult)


def extract_header_with_repair(
    client: LlmClient,
    text: str,
    pdf_path: str,
    pdf_id: str | None = None,
) -> HeaderExtractionResult:
    header = extract_header(client, text, pdf_id=pdf_id)
    if not header.doi:
        header.doi = _extract_doi(text)
    if _header_is_valid(header, text):
        return header
    repair_prompt = render_prompt(
        "match_header_repair.md",
        _prompt_meta={"pdf_id": pdf_id},
        text=text,
        previous=json.dumps(header.model_dump(mode="json"), indent=2),
    )
    repaired = client.complete_json(repair_prompt, HeaderExtractionResult)
    if not repaired.doi:
        repaired.doi = _extract_doi(text)
    if _header_is_valid(repaired, text):
        return repaired
    fallback = _deterministic_header_from_pdf(pdf_path)
    if fallback.title or fallback.authors or fallback.year:
        return fallback
    return repaired


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
    header_authors = {normalize_key(name).casefold() for name in _author_last_names(header.authors)}
    header_doi = _normalize_doi(header.doi)
    candidates: list[RowCandidate] = []
    row_lookup = {row["row_id"]: row for row in rows}
    for _, score, row_id in matches:
        row = row_lookup.get(row_id)
        if not row:
            continue
        year = str(row.get("year") or "")
        doi = str(row.get("doi") or "")
        author_score = _author_overlap(header_authors, _author_last_names(_split_authors(row.get("authors", ""))))
        title_score = score / 100.0
        year_bonus = _year_bonus(header.year, year, year_tolerance)
        doi_bonus = 0.12 if header_doi and _normalize_doi(doi) == header_doi else 0.0
        combined = min(1.0, title_score * 0.75 + author_score * 0.15 + year_bonus + doi_bonus)
        candidates.append(
            RowCandidate(
                row_id=row_id,
                title=row.get("title") or "",
                authors=row.get("authors") or "",
                year=year,
                doi=doi,
                score=combined,
                title_score=title_score,
                author_score=author_score,
                year_bonus=year_bonus,
                doi_bonus=doi_bonus,
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_k]


def _header_is_valid(header: HeaderExtractionResult, text: str) -> bool:
    normalized_text = _normalize_header_text(text)
    title_ok = False
    if header.title:
        title_ok = _normalize_header_text(header.title) in normalized_text
    authors_ok = False
    header_authors = _author_last_names(header.authors)
    if header_authors:
        authors_ok = any(name in normalized_text for name in header_authors)
    year_ok = True
    if header.year:
        year_ok = header.year in _extract_years(text)
    return title_ok and authors_ok and year_ok


def _extract_years(text: str) -> set[str]:
    return set(re.findall(r"\\b(?:19|20)\\d{2}\\b", text))


def _normalize_header_text(text: str) -> str:
    return normalize_key(text).casefold()


def _deterministic_header_from_pdf(pdf_path: str) -> HeaderExtractionResult:
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return HeaderExtractionResult(title=None, authors=[], year=None, evidence=[], confidence=0.0)
    if doc.page_count == 0:
        doc.close()
        return HeaderExtractionResult(title=None, authors=[], year=None, evidence=[], confidence=0.0)
    page = doc.load_page(0)
    blocks = page.get_text("dict").get("blocks", [])
    line_candidates: list[tuple[float, float, str]] = []
    for block in blocks:
        for line in block.get("lines", []):
            line_text = " ".join(span.get("text", "").strip() for span in line.get("spans", [])).strip()
            if not line_text:
                continue
            sizes = [float(span.get("size") or 0.0) for span in line.get("spans", [])]
            size = max(sizes) if sizes else 0.0
            bbox = line.get("bbox") or [0, 0, 0, 0]
            y = float(bbox[1])
            line_candidates.append((size, y, line_text))
    line_candidates.sort(key=lambda item: (-item[0], item[1]))
    title_lines = [text for _, _, text in line_candidates[:2]]
    title = " ".join(title_lines).strip()
    author_lines = [text for _, _, text in line_candidates[2:5]]
    authors = _split_authors(" ".join(author_lines))
    page_text = page.get_text("text")
    year_matches = re.findall(r"\\b(?:19|20)\\d{2}\\b", page_text)
    year = year_matches[0] if year_matches else None
    doi = _extract_doi(page_text)
    doc.close()
    return HeaderExtractionResult(
        title=title or None,
        authors=authors,
        year=year,
        doi=doi,
        evidence=[],
        confidence=0.4,
    )


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


def _extract_doi(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"10\\.\\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return match.group(0) if match else None


def _normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return cleaned


def deterministic_match(
    header: HeaderExtractionResult,
    candidates: list[RowCandidate],
    threshold: float,
    margin: float,
) -> AdjudicationResult | None:
    above = [candidate for candidate in candidates if candidate.score >= threshold]
    if len(above) == 1:
        best = above[0]
        next_best = candidates[1].score if len(candidates) > 1 else 0.0
        if best.score - next_best < margin:
            return None
        return AdjudicationResult(
            row_id=best.row_id,
            status="matched",
            top_candidates=[candidate.to_payload() for candidate in candidates],
            confidence=best.score,
            rationale="Single candidate above threshold",
            evidence=header.evidence,
        )
    if len(candidates) == 1 and candidates[0].score >= threshold:
        best = candidates[0]
        return AdjudicationResult(
            row_id=best.row_id,
            status="matched",
            top_candidates=[candidate.to_payload() for candidate in candidates],
            confidence=best.score,
            rationale="Single candidate available and above threshold",
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


def adjudicate_match(
    client: LlmClient,
    header: HeaderExtractionResult,
    candidates: list[RowCandidate],
    pdf_id: str | None = None,
) -> AdjudicationResult:
    prompt = render_prompt(
        "match_adjudicate.md",
        _prompt_meta={"pdf_id": pdf_id},
        header=json.dumps(header.model_dump(mode="json")),
        candidates=json.dumps([candidate.to_payload() for candidate in candidates], indent=2),
    )
    result = client.complete_json(prompt, AdjudicationResult)
    valid, reason = _validate_adjudication(result, candidates)
    if valid:
        return _coerce_single_candidate(result, candidates)
    repair_prompt = render_prompt(
        "match_adjudicate_repair.md",
        _prompt_meta={"pdf_id": pdf_id},
        header=json.dumps(header.model_dump(mode="json")),
        candidates=json.dumps([candidate.to_payload() for candidate in candidates], indent=2),
        previous=json.dumps(result.model_dump(mode="json"), indent=2),
        issue=reason,
    )
    repaired = client.complete_json(repair_prompt, AdjudicationResult)
    valid, _ = _validate_adjudication(repaired, candidates)
    if valid:
        return _coerce_single_candidate(repaired, candidates)
    return AdjudicationResult(
        row_id=None,
        status="unmatched",
        top_candidates=[candidate.to_payload() for candidate in candidates],
        confidence=0.0,
        rationale=f"Invalid adjudication output: {reason}",
        evidence=header.evidence,
    )


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


def _validate_adjudication(result: AdjudicationResult, candidates: list[RowCandidate]) -> tuple[bool, str]:
    valid_status = {"matched", "ambiguous", "unmatched"}
    if result.status not in valid_status:
        return False, f"Invalid status {result.status}"
    candidate_ids = {candidate.row_id for candidate in candidates}
    if result.status == "matched":
        if not result.row_id or result.row_id not in candidate_ids:
            return False, "Matched status requires row_id from candidates"
    if result.status != "matched" and result.row_id:
        return False, "row_id is only valid when status=matched"
    if result.status == "ambiguous" and result.row_id:
        return False, "Ambiguous status cannot include row_id"
    if result.status == "ambiguous" and len(candidates) <= 1:
        return False, "Ambiguous is invalid with a single candidate"
    return True, ""


def _coerce_single_candidate(result: AdjudicationResult, candidates: list[RowCandidate]) -> AdjudicationResult:
    if len(candidates) == 1 and result.status == "ambiguous":
        only = candidates[0]
        return AdjudicationResult(
            row_id=only.row_id,
            status="matched",
            top_candidates=result.top_candidates or [only.to_payload()],
            confidence=max(result.confidence, only.score),
            rationale="Single candidate coerced to matched",
            evidence=result.evidence,
        )
    return result
