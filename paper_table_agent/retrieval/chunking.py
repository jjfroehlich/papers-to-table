from __future__ import annotations

from dataclasses import dataclass
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
        chunk_id = f"page-{idx + 1}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=text.strip(),
                page_start=idx + 1,
                page_end=idx + 1,
                source="page",
                neighbors=[],
            )
        )
    _assign_neighbors(chunks)
    return chunks


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
