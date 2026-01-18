from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass
class Chunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    source: str
    neighbors: list[str]


def build_chunks(page_text: list[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for idx, text in enumerate(page_text):
        page_number = idx + 1
        cleaned = text.strip()
        if cleaned:
            chunks.append(
                Chunk(
                    chunk_id=f"page-{page_number}",
                    text=cleaned,
                    page_start=page_number,
                    page_end=page_number,
                    source="page",
                    neighbors=[],
                )
            )
        for para_index, paragraph in enumerate(_split_paragraphs(cleaned)):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"para-{page_number}-{para_index + 1}",
                    text=paragraph,
                    page_start=page_number,
                    page_end=page_number,
                    source="paragraph",
                    neighbors=[],
                )
            )
    _assign_neighbors(chunks)
    return chunks


def _split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    return [chunk for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]


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
            "text": chunk.text,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "source": chunk.source,
            "neighbors": chunk.neighbors,
        }
        for chunk in chunks
    ]
