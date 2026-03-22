from __future__ import annotations

from difflib import SequenceMatcher

from .ids import make_chunk_id
from .models import BlockType, ParsedDocument, RetrievalChunk, RetrievalSettings, SchemaColumn


def build_retrieval_chunks(doc: ParsedDocument) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []
    for ordinal, block in enumerate(doc.blocks, start=1):
        chunks.append(
            RetrievalChunk(
                chunk_id=make_chunk_id(doc.pdf_id, block.page, block.block_type.value, ordinal),
                pdf_id=doc.pdf_id,
                page=block.page,
                block_type=block.block_type,
                retrieval_text=block.retrieval_text or block.text,
                display_text=block.source_text or block.text,
                score=0,
                bbox=block.bbox,
                neighbor_ids=block.neighbors,
                metadata=block.metadata,
            )
        )
    for figure in doc.figures:
        chunks.append(
            RetrievalChunk(
                chunk_id=make_chunk_id(doc.pdf_id, figure.page, BlockType.CAPTION.value, len(chunks) + 1),
                pdf_id=doc.pdf_id,
                page=figure.page,
                block_type=BlockType.CAPTION,
                retrieval_text=figure.caption,
                display_text=figure.caption,
                score=0,
                metadata={"figure_id": figure.figure_id},
            )
        )
    return chunks


def select_chunks(chunks: list[RetrievalChunk], column: SchemaColumn, row: dict, settings: RetrievalSettings) -> list[RetrievalChunk]:
    query = f"{column.column_name} {column.description} {row.get('Title', '')}".lower()
    scored: list[RetrievalChunk] = []
    for chunk in chunks:
        score = SequenceMatcher(None, query, chunk.retrieval_text.lower()[:500]).ratio()
        if column.figure_likely and chunk.block_type in {BlockType.CAPTION, BlockType.TABLE}:
            score += 0.1
        chunk.score = round(score, 4)
        scored.append(chunk)
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: settings.top_k]
