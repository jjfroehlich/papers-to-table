from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable

from paper_table_agent.text.normalization import normalize_for_matching, normalize_key, normalize_text


@dataclass
class Chunk:
    chunk_id: str
    chunk_pk: str
    chunk_idx: int
    text: str
    text_raw: str
    text_norm: str
    page_start: int
    page_end: int
    chunk_type: str
    neighbors: list[str]


def build_chunks(
    page_text: list[str],
    sections: list[dict[str, str]] | None = None,
    pdf_id: str | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_idx = 0
    for idx, text in enumerate(page_text):
        page_number = idx + 1
        cleaned = text.strip()
        normalized = normalize_text(cleaned)
        chunk_idx += 1
        chunk_id = normalize_key(f"page-{page_number}")
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                chunk_pk=_chunk_pk(chunk_id, pdf_id),
                chunk_idx=chunk_idx,
                text=normalized or cleaned,
                text_raw=cleaned,
                text_norm=normalize_for_matching(cleaned or normalized),
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
                text_norm = normalize_for_matching(segment)
                raw_segment = raw_segments[min(segment_index - 1, len(raw_segments) - 1)] if raw_segments else segment
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        chunk_pk=_chunk_pk(chunk_id, pdf_id),
                        chunk_idx=chunk_idx,
                        text=segment,
                        text_raw=raw_segment,
                        text_norm=text_norm,
                        page_start=page_number,
                        page_end=page_number,
                        chunk_type="paragraph",
                        neighbors=[],
                    )
                )
    _assign_neighbors(chunks)
    if sections:
        section_chunks: list[Chunk] = []
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
            section_chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    chunk_pk=_chunk_pk(chunk_id, pdf_id),
                    chunk_idx=chunk_idx,
                    text=section_normalized,
                    text_raw=section_raw,
                    text_norm=normalize_text(section_normalized),
                    page_start=1,
                    page_end=1,
                    chunk_type="section",
                    neighbors=[],
                )
            )
        _assign_neighbors(section_chunks)
        chunks.extend(section_chunks)
    return chunks


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
            "text_norm": chunk.text_norm,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_type": chunk.chunk_type,
            "neighbors": chunk.neighbors,
        }
        for chunk in chunks
    ]


def _chunk_pk(chunk_id: str, pdf_id: str | None = None) -> str:
    normalized = normalize_key(chunk_id)
    scoped = f"{pdf_id}::{normalized}" if pdf_id else normalized
    return hashlib.sha1(scoped.encode("utf-8")).hexdigest()
