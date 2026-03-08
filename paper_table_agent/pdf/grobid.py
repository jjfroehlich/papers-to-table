from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx

from paper_table_agent.config import GrobidConfig
from paper_table_agent.pdf.parsed_document import ParsedDocument, ParsedElement


@dataclass
class GrobidResult:
    title: str | None
    authors: list[str]
    abstract: str | None
    sections: list[dict[str, Any]]
    references: list[str]


def extract_grobid(path: Path, config: GrobidConfig) -> GrobidResult:
    url = f"{config.server_url.rstrip('/')}/api/processFulltextDocument"
    params = {"consolidateHeader": "1", "consolidateCitations": "1"}
    if config.parse_references:
        params["includeRawCitations"] = "1"
    with path.open("rb") as handle:
        response = httpx.post(url, params=params, files={"input": handle})
    response.raise_for_status()
    return _parse_tei(response.text, parse_references=config.parse_references)


def save_grobid(result: GrobidResult, output_dir: Path, pdf_id: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": result.title,
        "authors": result.authors,
        "abstract": result.abstract,
        "sections": result.sections,
        "references": result.references,
    }
    (output_dir / f"{pdf_id}_grobid.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _parse_tei(xml_text: str, parse_references: bool) -> GrobidResult:
    root = ElementTree.fromstring(xml_text)
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    title = _first_text(root, ".//tei:fileDesc/tei:titleStmt/tei:title", ns)
    authors = [
        _collapse_text(node)
        for node in root.findall(".//tei:fileDesc/tei:titleStmt/tei:author", ns)
    ]
    abstract = _first_text(root, ".//tei:profileDesc/tei:abstract", ns)
    sections: list[dict[str, Any]] = []
    for div in root.findall(".//tei:text/tei:body/tei:div", ns):
        heading = _first_text(div, "./tei:head", ns)
        body_text = _collapse_text(div)
        if not body_text:
            continue
        sections.append(
            {
                "title": heading,
                "text": body_text,
            }
        )
    references: list[str] = []
    if parse_references:
        for bibl in root.findall(".//tei:listBibl/tei:biblStruct", ns):
            text = _collapse_text(bibl)
            if text:
                references.append(text)
    return GrobidResult(title=title, authors=authors, abstract=abstract, sections=sections, references=references)


def _first_text(node: ElementTree.Element, path: str, ns: dict[str, str]) -> str | None:
    found = node.find(path, ns)
    if found is None:
        return None
    return _collapse_text(found) or None


def _collapse_text(node: ElementTree.Element) -> str:
    parts = []
    for text in node.itertext():
        cleaned = " ".join(text.split())
        if cleaned:
            parts.append(cleaned)
    return " ".join(parts).strip()


def grobid_to_parsed_document(result: GrobidResult, pdf_id: str, page_text: list[str]) -> ParsedDocument:
    elements: list[ParsedElement] = []
    order = 0
    if result.abstract:
        order += 1
        elements.append(ParsedElement(element_id=f"grobid-{order}", element_type="abstract", text=result.abstract, page_start=1, page_end=1, order=order, heading="Abstract", provenance={"source": "grobid"}))
    for section in result.sections:
        title = section.get("title") or "Section"
        body = section.get("text") or ""
        if title:
            order += 1
            elements.append(ParsedElement(element_id=f"grobid-{order}", element_type="section_header", text=title, page_start=1, page_end=1, order=order, heading=title, provenance={"source": "grobid"}))
        if body:
            order += 1
            elements.append(ParsedElement(element_id=f"grobid-{order}", element_type="paragraph", text=body, page_start=1, page_end=1, order=order, heading=title, provenance={"source": "grobid"}))
    for ref in result.references:
        order += 1
        elements.append(ParsedElement(element_id=f"grobid-{order}", element_type="reference_block", text=ref, page_start=max(1, len(page_text)), page_end=max(1, len(page_text)), order=order, provenance={"source": "grobid"}))
    if not elements:
        for idx, text in enumerate(page_text, start=1):
            order += 1
            elements.append(ParsedElement(element_id=f"grobid-{order}", element_type="paragraph", text=text, page_start=idx, page_end=idx, order=order, provenance={"source": "grobid_fallback"}))
    return ParsedDocument(pdf_id=pdf_id, title=result.title, page_text=page_text, elements=elements)
