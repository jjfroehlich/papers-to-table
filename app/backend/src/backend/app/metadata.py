from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from .parsing import _DOI_PATTERN, _YEAR_PATTERN

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_PMID_PATTERN = re.compile(r"\bPMID\s*:?\s*(\d{5,})\b", re.IGNORECASE)


class MatchingMetadata(BaseModel):
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract_snippet: Optional[str] = None


class MetadataFieldResolution(BaseModel):
    extraction_lane: str = "metadata_front_matter"
    field_kind: str
    state: str
    proposed_value: Optional[str] = None
    quote_text: Optional[str] = None
    page_number: Optional[int] = None
    source_type: str = "none"
    source: str = "fallback_required"
    failure_attribution: Optional[str] = None
    fallback_reasons: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)


class MatchingMetadataDebug(BaseModel):
    metadata: MatchingMetadata
    field_diagnostics: dict[str, MetadataFieldResolution] = Field(default_factory=dict)
    front_matter_diagnostics: dict[str, object] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


def is_metadata_field(column_name: str, column_description: str = "") -> Optional[str]:
    combined = f"{column_name} {column_description}".strip().lower()
    patterns = [
        ("doi", ["doi", "digital object identifier"]),
        ("journal", ["journal", "publication venue", "venue", "conference"]),
        ("link", ["url", "link", "website", "web address"]),
        ("abstract", ["abstract", "summary"]),
        ("title", ["title", "paper title", "article title"]),
        ("authors", ["authors", "author list", "first author"]),
        ("year", ["publication year", "year published", "publication date"]),
        ("pmid", ["pmid", "pubmed"]),
    ]
    for kind, hints in patterns:
        if any(hint in combined for hint in hints):
            return kind
    return None


def extract_matching_metadata(doc_dict: dict) -> MatchingMetadata:
    return extract_matching_metadata_debug(doc_dict).metadata


def extract_matching_metadata_debug(doc_dict: dict) -> MatchingMetadataDebug:
    meta = doc_dict.get("metadata") if isinstance(doc_dict.get("metadata"), dict) else {}
    blocks = _front_matter_blocks(doc_dict)
    full_text = str(doc_dict.get("full_text") or "")

    title_candidate = _title_candidate(meta, blocks)
    authors = _coerce_authors(meta.get("authors"))
    year_candidate = _year_candidate(meta, blocks, full_text, allow_full_text_fallback=True)
    doi_candidate = _doi_candidate(meta, blocks, full_text, allow_full_text_fallback=True)
    abstract_text, _abstract_page = _find_abstract(blocks)
    metadata = MatchingMetadata(
        title=title_candidate.get("value") if title_candidate else None,
        authors=authors,
        year=int(year_candidate["value"]) if year_candidate and year_candidate.get("value") else None,
        doi=doi_candidate.get("value") if doi_candidate else None,
        abstract_snippet=abstract_text[:500] if abstract_text else None,
    )

    field_diagnostics: dict[str, MetadataFieldResolution] = {}
    for field_kind, column_name, description in [
        ("title", "Title", "Paper title"),
        ("authors", "Authors", "Author list"),
        ("year", "Publication Year", "Publication year"),
        ("doi", "DOI", "Digital object identifier"),
        ("abstract", "Abstract", "Paper abstract"),
    ]:
        resolution = resolve_metadata_field(column_name, description, doc_dict)
        if resolution is not None:
            field_diagnostics[field_kind] = resolution

    front_matter_diagnostics = {
        "parser_used": str(doc_dict.get("parser_used") or "unknown"),
        "front_matter_page_limit": 2,
        "front_matter_block_limit": 40,
        "front_matter_block_count": len(blocks),
        "front_matter_detected": bool(blocks),
        "front_matter_pages": sorted(
            {
                _coerce_page(block.get("page_number"))
                for block in blocks
                if _coerce_page(block.get("page_number")) is not None
            }
        ),
        "front_matter_block_types": [str(block.get("block_type") or "unknown") for block in blocks[:20]],
        "parser_metadata_present": bool(meta),
        "full_text_available": bool(full_text.strip()),
    }
    missing_fields = [
        field_name
        for field_name, value in {
            "title": metadata.title,
            "authors": metadata.authors,
            "year": metadata.year,
            "doi": metadata.doi,
        }.items()
        if not value
    ]
    return MatchingMetadataDebug(
        metadata=metadata,
        field_diagnostics=field_diagnostics,
        front_matter_diagnostics=front_matter_diagnostics,
        missing_fields=missing_fields,
    )


def resolve_metadata_field(column_name: str, column_description: str, doc_dict: dict) -> Optional[MetadataFieldResolution]:
    field_kind = is_metadata_field(column_name, column_description)
    if field_kind is None:
        return None

    meta = doc_dict.get("metadata") if isinstance(doc_dict.get("metadata"), dict) else {}
    blocks = _front_matter_blocks(doc_dict)
    full_text = str(doc_dict.get("full_text") or "")
    parser_used = str(doc_dict.get("parser_used") or "unknown")
    diagnostics: dict[str, object] = {
        "parser_used": parser_used,
        "front_matter_block_count": len(blocks),
        "front_matter_detected": bool(blocks),
        "front_matter_pages": sorted(
            {
                _coerce_page(block.get("page_number"))
                for block in blocks
                if _coerce_page(block.get("page_number")) is not None
            }
        ),
        "parser_metadata_present": bool(meta),
    }

    if field_kind == "doi":
        block_doi_candidates = _regex_block_candidates(blocks, _DOI_PATTERN, source="front_matter_block")
        parser_doi = _normalize_doi(_coerce_text(meta.get("doi")))
        candidates = _dedupe_candidates(
            ([
                _candidate(parser_doi, source="parser_metadata"),
                *block_doi_candidates,
            ] if parser_doi else block_doi_candidates)
        )
    elif field_kind == "link":
        candidates = _dedupe_candidates(_regex_block_candidates(blocks, _URL_PATTERN, source="front_matter_block"))
    elif field_kind == "pmid":
        candidates = _dedupe_candidates(_regex_block_candidates(blocks, _PMID_PATTERN, source="front_matter_block", group=1))
    elif field_kind == "abstract":
        abstract_text, abstract_page = _find_abstract(blocks)
        parser_abstract = _coerce_text(meta.get("abstract"))
        candidates = _dedupe_candidates(
            [
                _candidate(parser_abstract, source="parser_metadata", page_number=abstract_page),
                _candidate(abstract_text, source="front_matter_block", page_number=abstract_page),
            ]
        )
    elif field_kind == "journal":
        candidates = _dedupe_candidates(_find_journal_candidates(blocks))
    elif field_kind == "title":
        title_candidate = _title_candidate(meta, blocks)
        candidates = _dedupe_candidates([title_candidate] if title_candidate is not None else [])
    elif field_kind == "authors":
        authors = _coerce_authors(meta.get("authors"))
        joined = "; ".join(authors) if authors else None
        page_number = _find_text_page(blocks, joined)
        candidates = _dedupe_candidates([_candidate(joined, source="parser_metadata", page_number=page_number)])
    else:
        year_candidate = _year_candidate(meta, blocks, full_text, allow_full_text_fallback=False)
        candidates = _dedupe_candidates([year_candidate] if year_candidate is not None else [])

    diagnostics["candidate_count"] = len(candidates)
    diagnostics["candidate_sources"] = [candidate["source"] for candidate in candidates]
    diagnostics["candidate_values"] = [candidate["value"] for candidate in candidates]
    diagnostics["candidates"] = [
        {
            "value": candidate.get("value"),
            "source": candidate.get("source"),
            "page_number": candidate.get("page_number"),
            "quote_text": candidate.get("quote_text"),
        }
        for candidate in candidates
    ]

    if len(candidates) == 1:
        candidate = candidates[0]
        return MetadataFieldResolution(
            field_kind=field_kind,
            state="found",
            proposed_value=candidate["value"],
            quote_text=candidate.get("quote_text") or candidate["value"],
            page_number=candidate.get("page_number"),
            source_type="direct_quote" if candidate.get("quote_text") else "quote_plus_page",
            source=str(candidate.get("source") or "front_matter_block"),
            diagnostics=diagnostics,
        )

    if len(candidates) > 1:
        return MetadataFieldResolution(
            field_kind=field_kind,
            state="unclear",
            source="front_matter_conflict",
            failure_attribution="evidence_ambiguity",
            fallback_reasons=["multiple_front_matter_candidates"],
            diagnostics=diagnostics,
        )

    parser_gap = not meta and not blocks and not full_text.strip()
    fallback_reasons = ["parser_metadata_missing", "front_matter_no_match"]
    return MetadataFieldResolution(
        field_kind=field_kind,
        state="unclear",
        source="fallback_required",
        failure_attribution="parser_gap" if parser_gap else "retrieval_miss",
        fallback_reasons=fallback_reasons,
        diagnostics=diagnostics,
    )


def _front_matter_blocks(doc_dict: dict, *, max_pages: int = 2, max_blocks: int = 40) -> list[dict]:
    blocks = doc_dict.get("blocks") if isinstance(doc_dict.get("blocks"), list) else []
    selected: list[dict] = []
    for block in blocks:
        page_number = int(block.get("page_number", 999) or 999)
        if page_number > max_pages:
            continue
        text = _coerce_text(block.get("text"))
        if not text:
            continue
        selected.append(block)
        if len(selected) >= max_blocks:
            break
    return selected


def _find_title_from_blocks(blocks: list[dict]) -> Optional[str]:
    for block in blocks:
        block_type = str(block.get("block_type") or "")
        text = _coerce_text(block.get("text"))
        if block_type in {"heading", "section_heading"} and text and 15 < len(text) < 300:
            return text
    for block in blocks:
        text = _coerce_text(block.get("text"))
        if text and 20 < len(text) < 300:
            lowered = text.lower()
            if not any(token in lowered for token in ["doi", "journal", "published", "received"]):
                return text
    return None


def _find_abstract(blocks: list[dict]) -> tuple[Optional[str], Optional[int]]:
    for block in blocks:
        block_type = str(block.get("block_type") or "")
        text = _coerce_text(block.get("text"))
        if not text:
            continue
        if block_type == "abstract" or text.lower().startswith("abstract"):
            cleaned = text[8:].strip(": .\n") if text.lower().startswith("abstract") else text
            return cleaned, _coerce_page(block.get("page_number"))
    return None, None


def _find_journal_candidates(blocks: list[dict]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for block in blocks:
        text = _coerce_text(block.get("text"))
        if not text:
            continue
        lowered = text.lower()
        if any(token in lowered for token in ["journal", "proceedings", "conference", "nature", "science", "cell", "biorxiv", "medrxiv"]):
            candidates.append(
                _candidate(
                    text,
                    source="front_matter_block",
                    quote_text=text,
                    page_number=_coerce_page(block.get("page_number")),
                )
            )
    return candidates


def _title_candidate(meta: dict, blocks: list[dict]) -> Optional[dict[str, object]]:
    parser_title = _coerce_text(meta.get("title"))
    if parser_title:
        return _candidate(
            parser_title,
            source="parser_metadata",
            page_number=_find_text_page(blocks, parser_title),
        )
    front_matter_title = _find_title_from_blocks(blocks)
    if front_matter_title:
        return _candidate(
            front_matter_title,
            source="front_matter_block",
            quote_text=front_matter_title,
            page_number=_find_text_page(blocks, front_matter_title),
        )
    return None


def _doi_candidate(
    meta: dict,
    blocks: list[dict],
    full_text: str,
    *,
    allow_full_text_fallback: bool,
) -> Optional[dict[str, object]]:
    parser_doi = _normalize_doi(_coerce_text(meta.get("doi")))
    if parser_doi:
        return _candidate(parser_doi, source="parser_metadata")
    block_candidates = _regex_block_candidates(blocks, _DOI_PATTERN, source="front_matter_block")
    if block_candidates:
        return block_candidates[0]
    if allow_full_text_fallback:
        full_text_doi = _extract_first_regex(_DOI_PATTERN, full_text)
        if full_text_doi:
            return _candidate(full_text_doi, source="full_text_fallback")
    return None


def _year_candidate(
    meta: dict,
    blocks: list[dict],
    full_text: str,
    *,
    allow_full_text_fallback: bool,
) -> Optional[dict[str, object]]:
    parser_year = _coerce_year(meta.get("year"))
    if parser_year is not None:
        return _candidate(
            str(parser_year),
            source="parser_metadata",
            page_number=_find_year_page(blocks, parser_year),
        )
    block_year_candidates = _year_block_candidates(blocks)
    if block_year_candidates:
        return block_year_candidates[0]
    if allow_full_text_fallback:
        full_text_year = _extract_year_from_text(full_text)
        if full_text_year is not None:
            return _candidate(str(full_text_year), source="full_text_fallback")
    return None


def _regex_block_candidates(
    blocks: list[dict],
    pattern: re.Pattern[str],
    *,
    source: str,
    group: int = 0,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for block in blocks:
        text = _coerce_text(block.get("text"))
        if not text:
            continue
        match = pattern.search(text)
        if not match:
            continue
        value = _coerce_text(match.group(group))
        if not value:
            continue
        candidates.append(
            _candidate(
                value,
                source=source,
                quote_text=text,
                page_number=_coerce_page(block.get("page_number")),
            )
        )
    return candidates


def _year_block_candidates(blocks: list[dict]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for block in blocks:
        text = _coerce_text(block.get("text"))
        if not text:
            continue
        match = _YEAR_PATTERN.search(text)
        if not match:
            continue
        value = _coerce_text(match.group(0))
        if not value:
            continue
        candidates.append(
            _candidate(
                value,
                source="front_matter_block",
                quote_text=text,
                page_number=_coerce_page(block.get("page_number")),
            )
        )
    return candidates


def _candidate(
    value: Optional[str],
    *,
    source: str,
    quote_text: Optional[str] = None,
    page_number: Optional[int] = None,
) -> dict[str, object]:
    return {
        "value": value,
        "source": source,
        "quote_text": quote_text,
        "page_number": page_number,
    }


def _dedupe_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = _coerce_text(candidate.get("value"))
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidate = dict(candidate)
        candidate["value"] = value
        if not candidate.get("quote_text"):
            candidate["quote_text"] = value
        deduped.append(candidate)
    return deduped


def _first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def _coerce_text(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        text = "; ".join(str(item).strip() for item in value if str(item).strip())
    else:
        text = str(value).strip()
    return text or None


def _coerce_authors(value: object) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        authors = [str(item).strip() for item in value if str(item).strip()]
        return authors or None
    text = str(value).strip()
    if not text:
        return None
    return [part.strip() for part in re.split(r";|\band\b", text, flags=re.IGNORECASE) if part.strip()] or None


def _coerce_year(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _extract_year_from_text(text: str) -> Optional[int]:
    matches = _YEAR_PATTERN.findall(text)
    if not matches:
        return None
    return int(matches[0])


def _extract_first_regex(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    if not match:
        return None
    return _coerce_text(match.group(0))


def _normalize_doi(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = re.sub(r"^https?://(dx\.)?doi\.org/", "", value.strip(), flags=re.IGNORECASE)
    normalized = re.sub(r"^doi:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.rstrip(".")
    return normalized or None


def _coerce_page(value: object) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _find_text_page(blocks: list[dict], text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    lowered = text.casefold()
    for block in blocks:
        block_text = _coerce_text(block.get("text"))
        if block_text and lowered in block_text.casefold():
            return _coerce_page(block.get("page_number"))
    return None


def _find_year_page(blocks: list[dict], year_value: Optional[int]) -> Optional[int]:
    if year_value is None:
        return None
    year_text = str(year_value)
    for block in blocks:
        block_text = _coerce_text(block.get("text"))
        if block_text and year_text in block_text:
            return _coerce_page(block.get("page_number"))
    return None
