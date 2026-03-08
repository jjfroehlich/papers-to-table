from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Iterable, Any

from paper_table_agent.pdf.parsed_document import ParsedDocument
from paper_table_agent.text.normalization import normalize_for_matching, normalize_key, normalize_text


@dataclass
class Chunk:
    chunk_id: str
    chunk_pk: str
    chunk_idx: int
    text: str
    text_raw: str
    retrieval_text: str
    text_norm: str
    page_start: int
    page_end: int
    chunk_type: str
    neighbors: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


def build_chunks(
    page_text: list[str],
    sections: list[dict[str, str]] | None = None,
    pdf_id: str | None = None,
    parsed_document: ParsedDocument | None = None,
) -> list[Chunk]:
    if parsed_document and parsed_document.elements:
        chunks = _build_chunks_from_elements(parsed_document, pdf_id)
    else:
        chunks = _build_fallback_chunks(page_text, sections, pdf_id)
    _assign_neighbors(chunks)
    return chunks


def _build_chunks_from_elements(parsed_document: ParsedDocument, pdf_id: str | None) -> list[Chunk]:
    chunks: list[Chunk] = []
    for idx, element in enumerate(parsed_document.elements, start=1):
        text_raw = element.text.strip()
        if not text_raw:
            continue
        text = normalize_text(text_raw) or text_raw
        element_type = element.element_type or "paragraph"
        chunk_type = element_type
        chunk_id = normalize_key(f"{element_type}-{idx}")
        retrieval_text = _build_retrieval_text(
            text=text,
            title=parsed_document.title,
            heading=element.heading,
            page_start=element.page_start,
            page_end=element.page_end,
            chunk_type=chunk_type,
        )
        chunk = Chunk(
            chunk_id=chunk_id,
            chunk_pk=_chunk_pk(chunk_id, pdf_id),
            chunk_idx=len(chunks) + 1,
            text=text,
            text_raw=text_raw,
            retrieval_text=retrieval_text,
            text_norm=normalize_for_matching(text_raw or text),
            page_start=element.page_start,
            page_end=element.page_end,
            chunk_type=chunk_type,
            neighbors=[],
            metadata={
                "source_element_type": element.element_type,
                "source_element_id": element.element_id,
                "heading": element.heading,
                "provenance": element.provenance,
            },
        )
        chunks.append(chunk)
        if chunk_type == "table_region":
            summary = _table_summary(text)
            if summary:
                summary_id = normalize_key(f"table-summary-{idx}")
                chunks.append(
                    Chunk(
                        chunk_id=summary_id,
                        chunk_pk=_chunk_pk(summary_id, pdf_id),
                        chunk_idx=len(chunks) + 1,
                        text=summary,
                        text_raw=summary,
                        retrieval_text=_build_retrieval_text(
                            text=summary,
                            title=parsed_document.title,
                            heading=element.heading,
                            page_start=element.page_start,
                            page_end=element.page_end,
                            chunk_type="table_cell_summary",
                        ),
                        text_norm=normalize_for_matching(summary),
                        page_start=element.page_start,
                        page_end=element.page_end,
                        chunk_type="table_cell_summary",
                        neighbors=[],
                        metadata={"source_element_type": "table_region", "source_element_id": element.element_id},
                    )
                )
    return chunks


def _build_fallback_chunks(page_text: list[str], sections: list[dict[str, str]] | None, pdf_id: str | None) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_idx = 0
    for idx, text in enumerate(page_text):
        page_number = idx + 1
        cleaned = text.strip()
        normalized = normalize_text(cleaned)
        chunk_idx += 1
        chunk_id = normalize_key(f"page-{page_number}")
        base_text = normalized or cleaned
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                chunk_pk=_chunk_pk(chunk_id, pdf_id),
                chunk_idx=chunk_idx,
                text=base_text,
                text_raw=cleaned,
                retrieval_text=_build_retrieval_text(base_text, None, None, page_number, page_number, "page"),
                text_norm=normalize_for_matching(cleaned or base_text),
                page_start=page_number,
                page_end=page_number,
                chunk_type="page",
                neighbors=[],
            )
        )
        for para_index, paragraph in enumerate(_split_paragraphs(cleaned)):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            paragraph_normalized = normalize_text(paragraph)
            if not paragraph_normalized or len(paragraph_normalized.split()) < 4:
                continue
            segments = _split_long_text(paragraph_normalized)
            raw_segments = _split_long_text(paragraph)
            for segment_index, segment in enumerate(segments, start=1):
                if not segment.strip():
                    continue
                chunk_idx += 1
                chunk_id = normalize_key(f"para-{page_number}-{para_index + 1}-{segment_index}")
                raw_segment = raw_segments[min(segment_index - 1, len(raw_segments) - 1)] if raw_segments else segment
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        chunk_pk=_chunk_pk(chunk_id, pdf_id),
                        chunk_idx=chunk_idx,
                        text=segment,
                        text_raw=raw_segment,
                        retrieval_text=_build_retrieval_text(segment, None, None, page_number, page_number, "paragraph"),
                        text_norm=normalize_for_matching(segment),
                        page_start=page_number,
                        page_end=page_number,
                        chunk_type="paragraph",
                        neighbors=[],
                    )
                )
    if sections:
        for idx, section in enumerate(sections):
            text = section.get("text") or ""
            if not text.strip():
                continue
            title = section.get("title") or "Section"
            section_raw = f"{title}\n{text.strip()}"
            section_normalized = normalize_text(section_raw)
            if not section_normalized:
                continue
            chunk_idx += 1
            chunk_id = normalize_key(f"section-{idx + 1}")
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    chunk_pk=_chunk_pk(chunk_id, pdf_id),
                    chunk_idx=chunk_idx,
                    text=section_normalized,
                    text_raw=section_raw,
                    retrieval_text=_build_retrieval_text(section_normalized, None, title, 1, 1, "section"),
                    text_norm=normalize_text(section_normalized),
                    page_start=1,
                    page_end=1,
                    chunk_type="section",
                    neighbors=[],
                )
            )
    return chunks


def _build_retrieval_text(
    text: str,
    title: str | None,
    heading: str | None,
    page_start: int,
    page_end: int,
    chunk_type: str,
) -> str:
    context = [f"type:{chunk_type}"]
    if title:
        context.append(f"title:{title.strip()}")
    if heading:
        context.append(f"section:{heading.strip()}")
    if page_start == page_end:
        context.append(f"page:{page_start}")
    else:
        context.append(f"pages:{page_start}-{page_end}")
    prefix = " | ".join(context)
    return f"{prefix}\n{text.strip()}".strip()


def _table_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    header = lines[0][:160]
    numeric_rows = sum(1 for line in lines if sum(ch.isdigit() for ch in line) >= 3)
    return f"Table summary: {header}. Rows~{len(lines)}, numeric_rows~{numeric_rows}."


def _split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    return [chunk for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]


def _split_long_text(text: str, max_chars: int = 1200) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[.!?])\s+", text)
    segments: list[str] = []
    buffer = ""
    for part in parts:
        if not part:
            continue
        if len(buffer) + len(part) + 1 > max_chars and buffer:
            segments.append(buffer.strip())
            buffer = part
        else:
            buffer = f"{buffer} {part}".strip()
    if buffer:
        segments.append(buffer.strip())
    return segments


def _assign_neighbors(chunks: list[Chunk]) -> None:
    for index, chunk in enumerate(chunks):
        neighbors: list[str] = []
        if index > 0:
            neighbors.append(chunks[index - 1].chunk_id)
        if index < len(chunks) - 1:
            neighbors.append(chunks[index + 1].chunk_id)
        chunk.neighbors = neighbors


def to_dicts(chunks: Iterable[Chunk]) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_pk": chunk.chunk_pk,
            "chunk_idx": chunk.chunk_idx,
            "text": chunk.text,
            "text_raw": chunk.text_raw,
            "retrieval_text": chunk.retrieval_text,
            "text_norm": chunk.text_norm,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_type": chunk.chunk_type,
            "neighbors": chunk.neighbors,
            "metadata": chunk.metadata,
        }
        for chunk in chunks
    ]


def _chunk_pk(chunk_id: str, pdf_id: str | None = None) -> str:
    normalized = normalize_key(chunk_id)
    scoped = f"{pdf_id}::{normalized}" if pdf_id else normalized
    return hashlib.sha1(scoped.encode("utf-8")).hexdigest()
