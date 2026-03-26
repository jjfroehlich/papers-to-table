"""
Batch 3 — MVP retrieval artifacts.

Implements:
- T045: Typed chunk generation (paragraph, section, caption, table regions)
- T046: Contextualized retrieval_text + source-preserving display_text
- T047: MVP retrieval assembly defaults (top_k=6, neighbor window, no reranking/HyDE)
- T048: Persist retrieval artifacts and diagnostics
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .artifacts import RunArtifacts
    from .parsing import ParsedDocument

logger = logging.getLogger(__name__)

# Chunk types
PARA = "paragraph"
SECTION = "section"
CAPTION = "caption"
TABLE = "table"

# MVP default
DEFAULT_TOP_K = 6


# ---------------------------------------------------------------------------
# T045 — RetrievalChunk schema
# ---------------------------------------------------------------------------


class RetrievalChunk(BaseModel):
    """One typed retrieval unit from a parsed document."""

    chunk_id: str
    pdf_id: str
    chunk_type: str  # paragraph | section | caption | table
    display_text: str  # source-preserving text for evidence display
    retrieval_text: str  # contextualized text for retrieval scoring (T046)
    page_no: int
    block_id: str | None = None
    reading_order: int = 0
    section_header: str | None = None
    figure_ref: str | None = None


class RetrievalResult(BaseModel):
    """Retrieval result for one (pdf_id, column_name) query."""

    pdf_id: str
    column_name: str
    query: str
    top_k: int = DEFAULT_TOP_K
    selected_chunks: list[RetrievalChunk] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    neighbor_chunk_ids: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# T045+T046 — Build typed chunks from a ParsedDocument
# ---------------------------------------------------------------------------


def build_chunks(doc: "ParsedDocument") -> list[RetrievalChunk]:
    """
    T045: Build typed retrieval chunks for paragraph, section, caption, and table regions.
    T046: Enrich each chunk with contextualized retrieval_text while keeping display_text
          source-preserving.
    """
    chunks: list[RetrievalChunk] = []
    current_section: str | None = None
    chunk_index = 0

    for block in doc.reading_order_blocks:
        btype = block.block_type.lower()

        # Track current section header for contextualization
        if btype in ("section_header", "title"):
            current_section = block.text.strip()

        # Build context prefix for retrieval_text (T046)
        ctx_parts: list[str] = []
        if current_section:
            ctx_parts.append(f"[Section: {current_section}]")

        # Determine chunk type
        if btype in ("section_header",):
            chunk_type = SECTION
        elif btype == "caption":
            chunk_type = CAPTION
        elif block.table_region or btype == "table":
            chunk_type = TABLE
        else:
            chunk_type = PARA

        # Source-preserving display text
        display = block.text

        # Contextualized retrieval text includes section header prefix
        retrieval = " ".join(ctx_parts + [block.normalized_text]).strip()
        if not retrieval:
            retrieval = display

        cid = f"chunk_{doc.pdf_id}_{chunk_index:04d}"
        chunks.append(
            RetrievalChunk(
                chunk_id=cid,
                pdf_id=doc.pdf_id,
                chunk_type=chunk_type,
                display_text=display,
                retrieval_text=retrieval,
                page_no=block.page_no,
                block_id=block.block_id,
                reading_order=block.reading_order,
                section_header=current_section,
                figure_ref=block.figure_ref,
            )
        )
        chunk_index += 1

    # Add table-region chunks from doc.tables (may not overlap with blocks)
    for table in doc.tables:
        if table.markdown_text:
            cid = f"chunk_{doc.pdf_id}_tbl_{table.table_id}"
            ctx_parts = [f"[Table, page {table.page_no}]"]
            chunks.append(
                RetrievalChunk(
                    chunk_id=cid,
                    pdf_id=doc.pdf_id,
                    chunk_type=TABLE,
                    display_text=table.markdown_text,
                    retrieval_text=" ".join(ctx_parts + [table.markdown_text.lower()]),
                    page_no=table.page_no,
                    block_id=None,
                    reading_order=9999,
                )
            )

    return chunks


# ---------------------------------------------------------------------------
# T047 — Simple sparse BM25-lite retrieval (no reranking / HyDE / query expansion)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens for BM25 retrieval scoring."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _idf(term: str, doc_freqs: Counter[str], num_docs: int) -> float:
    df = doc_freqs[term]
    if df == 0:
        return 0.0
    return math.log((num_docs - df + 0.5) / (df + 0.5) + 1)


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_freqs: Counter[str],
    num_docs: int,
    k1: float = 1.5,
    b: float = 0.75,
    avg_dl: float = 50.0,
) -> float:
    tf_map = Counter(doc_tokens)
    dl = len(doc_tokens)
    score = 0.0
    for term in set(query_tokens):
        if term not in tf_map:
            continue
        tf = tf_map[term]
        idf = _idf(term, doc_freqs, num_docs)
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1)))
    return score


def retrieve_chunks_for_query(
    chunks: list[RetrievalChunk],
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[RetrievalChunk], list[float]]:
    """
    T047: Sparse BM25-lite retrieval over retrieval_text fields.

    Returns (selected_chunks, scores) sorted by score descending.
    No reranking, HyDE, or query expansion per spec.
    """
    if not chunks:
        return [], []

    tokenized_docs = [_tokenize(c.retrieval_text) for c in chunks]
    query_tokens = _tokenize(query)

    if not query_tokens:
        return chunks[:top_k], [0.0] * min(top_k, len(chunks))

    # Build corpus-level document frequencies
    doc_freqs: Counter[str] = Counter()
    for tokens in tokenized_docs:
        for term in set(tokens):
            doc_freqs[term] += 1

    num_docs = len(tokenized_docs)
    avg_dl = sum(len(t) for t in tokenized_docs) / num_docs

    scored = [
        (i, _bm25_score(query_tokens, tokens, doc_freqs, num_docs, avg_dl=avg_dl))
        for i, tokens in enumerate(tokenized_docs)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected_indices = [i for i, _ in scored[:top_k]]
    selected_scores = [s for _, s in scored[:top_k]]

    return [chunks[i] for i in selected_indices], selected_scores


def _add_neighbor_window(
    selected: list[RetrievalChunk],
    all_chunks: list[RetrievalChunk],
) -> list[str]:
    """
    T047: Include one neighbor window around selected text chunks.

    Returns the list of neighbor chunk_ids (not already in selected).
    """
    selected_ids = {c.chunk_id for c in selected}
    # Index chunks by chunk_id for fast lookup
    id_to_idx: dict[str, int] = {c.chunk_id: i for i, c in enumerate(all_chunks)}

    neighbor_ids: list[str] = []
    for chunk in selected:
        if chunk.chunk_type not in (PARA, SECTION):
            continue  # Only expand text chunks
        idx = id_to_idx.get(chunk.chunk_id)
        if idx is None:
            continue
        for neighbor_idx in (idx - 1, idx + 1):
            if 0 <= neighbor_idx < len(all_chunks):
                neighbor = all_chunks[neighbor_idx]
                if neighbor.chunk_id not in selected_ids:
                    neighbor_ids.append(neighbor.chunk_id)
                    selected_ids.add(neighbor.chunk_id)

    return neighbor_ids


def build_retrieval_result(
    doc: "ParsedDocument",
    chunks: list[RetrievalChunk],
    column_name: str,
    column_description: str,
    top_k: int = DEFAULT_TOP_K,
) -> RetrievalResult:
    """
    T047: Assemble a RetrievalResult for one (pdf_id, column_name) pair.

    Query is built from column name + description.
    """
    query = f"{column_name}: {column_description}".strip()
    selected, scores = retrieve_chunks_for_query(chunks, query=query, top_k=top_k)
    neighbor_ids = _add_neighbor_window(selected, chunks)

    return RetrievalResult(
        pdf_id=doc.pdf_id,
        column_name=column_name,
        query=query,
        top_k=top_k,
        selected_chunks=selected,
        scores=scores,
        neighbor_chunk_ids=neighbor_ids,
        diagnostics={
            "total_chunks": len(chunks),
            "selected_count": len(selected),
            "neighbor_count": len(neighbor_ids),
        },
    )


# ---------------------------------------------------------------------------
# T048 — Persist retrieval artifacts
# ---------------------------------------------------------------------------


def persist_retrieval_result(
    artifacts: "RunArtifacts",
    result: RetrievalResult,
) -> None:
    """
    T048: Persist selected chunks, contextualized text, source-preserving display text,
    and diagnostics to the retrieval artifact folder.
    """
    pdf_id = result.pdf_id
    col_safe = re.sub(r"[^\w\-]", "_", result.column_name)[:60]
    base = f"retrieval/{pdf_id}/{col_safe}"

    # Full result (chunk metadata + scores)
    result_payload: dict[str, Any] = {
        "pdf_id": pdf_id,
        "column_name": result.column_name,
        "query": result.query,
        "top_k": result.top_k,
        "diagnostics": result.diagnostics,
        "selected_chunks": [c.model_dump(mode="json") for c in result.selected_chunks],
        "scores": result.scores,
        "neighbor_chunk_ids": result.neighbor_chunk_ids,
    }
    artifacts.write_json(f"{base}/result.json", result_payload)


def persist_chunks(
    artifacts: "RunArtifacts",
    pdf_id: str,
    chunks: list[RetrievalChunk],
) -> None:
    """T048: Persist the full chunk list for a PDF."""
    payload = [c.model_dump(mode="json") for c in chunks]
    artifacts.write_json(f"retrieval/{pdf_id}/chunks.json", payload)


def load_chunks(
    artifacts: "RunArtifacts",
    pdf_id: str,
) -> list[RetrievalChunk]:
    """Load persisted chunks for a PDF."""
    try:
        rows = artifacts.read_json(f"retrieval/{pdf_id}/chunks.json")
        return [RetrievalChunk.model_validate(r) for r in rows]
    except FileNotFoundError:
        return []


def load_retrieval_result(
    artifacts: "RunArtifacts",
    pdf_id: str,
    column_name: str,
) -> RetrievalResult | None:
    """Load a persisted retrieval result."""
    col_safe = re.sub(r"[^\w\-]", "_", column_name)[:60]
    try:
        data = artifacts.read_json(f"retrieval/{pdf_id}/{col_safe}/result.json")
        return RetrievalResult.model_validate(data)
    except FileNotFoundError:
        return None
