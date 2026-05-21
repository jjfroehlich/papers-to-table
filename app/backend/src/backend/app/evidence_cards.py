from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .artifacts import write_json


class EvidenceCard(BaseModel):
    schema_version: str = "evidence_card.v1"
    run_id: str
    pdf_id: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    doi: str | None = None
    abstract: str | None = None
    methods_snippets: list[str] = Field(default_factory=list)
    results_snippets: list[str] = Field(default_factory=list)
    figure_catalog: list[dict[str, Any]] = Field(default_factory=list)
    table_snippets: list[str] = Field(default_factory=list)
    detected_numbers: list[str] = Field(default_factory=list)
    parser_warnings: list[str] = Field(default_factory=list)
    generated_at: str


def _trim(text: object, *, limit: int = 900) -> str | None:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return None
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _block_text(block: dict[str, Any]) -> str | None:
    return _trim(block.get("text"), limit=700)


def _section_matches(block: dict[str, Any], pattern: str) -> bool:
    section = str(block.get("section_context") or block.get("heading") or "").lower()
    text = str(block.get("text") or "").lower()
    return bool(re.search(pattern, f"{section} {text}"))


def build_evidence_card(run_id: str, doc_dict: dict[str, Any]) -> EvidenceCard:
    metadata = doc_dict.get("metadata") if isinstance(doc_dict.get("metadata"), dict) else {}
    blocks = [block for block in doc_dict.get("blocks", []) or [] if isinstance(block, dict)]

    abstract = next(
        (
            _block_text(block)
            for block in blocks
            if str(block.get("block_type") or "").lower() == "abstract"
            or _section_matches(block, r"\babstract\b")
        ),
        None,
    )
    methods = [
        text
        for block in blocks
        if _section_matches(block, r"\b(method|materials|protocol|experimental|assay)\b")
        for text in [_block_text(block)]
        if text
    ][:5]
    results = [
        text
        for block in blocks
        if _section_matches(block, r"\b(result|finding|evaluation|performance|analysis)\b")
        for text in [_block_text(block)]
        if text
    ][:5]
    tables = [
        text
        for block in blocks
        if str(block.get("block_type") or "").lower() == "table_region"
        for text in [_block_text(block)]
        if text
    ][:4]

    figure_catalog: list[dict[str, Any]] = []
    for figure in doc_dict.get("figures", []) or []:
        if not isinstance(figure, dict):
            continue
        figure_catalog.append(
            {
                "figure_ref": figure.get("figure_id") or figure.get("id"),
                "page_number": figure.get("page_number"),
                "caption": _trim(figure.get("caption_text"), limit=500),
                "has_crop": bool(figure.get("crop_path")),
                "has_full_page": bool(figure.get("full_page_path")),
            }
        )

    full_text = str(doc_dict.get("full_text") or "")
    numbers = re.findall(r"(?<!\w)(?:\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?[a-zA-Z/]+|\d+(?:,\d{3})*)(?!\w)", full_text)
    detected_numbers = []
    seen: set[str] = set()
    for number in numbers:
        key = number.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        detected_numbers.append(number.strip())
        if len(detected_numbers) >= 25:
            break

    authors = metadata.get("authors")
    if isinstance(authors, str):
        author_list = [item.strip() for item in re.split(r";|,", authors) if item.strip()]
    elif isinstance(authors, list):
        author_list = [str(item).strip() for item in authors if str(item).strip()]
    else:
        author_list = []

    return EvidenceCard(
        run_id=run_id,
        pdf_id=str(doc_dict.get("pdf_id") or ""),
        title=_trim(metadata.get("title") or doc_dict.get("title"), limit=300),
        authors=author_list[:20],
        year=_trim(metadata.get("year"), limit=20),
        doi=_trim(metadata.get("doi"), limit=100),
        abstract=abstract,
        methods_snippets=methods,
        results_snippets=results,
        figure_catalog=figure_catalog[:30],
        table_snippets=tables,
        detected_numbers=detected_numbers,
        parser_warnings=[
            str(item)
            for item in (doc_dict.get("parse_warnings") or doc_dict.get("warnings") or [])
            if str(item).strip()
        ][:20],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def get_evidence_card_path(run_dir: pathlib.Path, pdf_id: str) -> pathlib.Path:
    safe_pdf = re.sub(r'[\\/:*?"<>|]', "_", pdf_id).strip("._") or "paper"
    return run_dir / "evidence_cards" / f"{safe_pdf}.json"


def persist_evidence_card(run_dir: pathlib.Path, card: EvidenceCard) -> pathlib.Path:
    path = get_evidence_card_path(run_dir, card.pdf_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, card.model_dump())
    return path
