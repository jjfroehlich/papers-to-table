from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from paper_table_agent.retrieval.index import RetrievalIndex
from paper_table_agent.llm.embeddings import EmbeddingClient


@dataclass
class RetrievedChunk:
    chunk_id: str
    chunk_pk: str
    chunk_idx: int
    text: str
    text_raw: str
    text_norm: str
    page_start: int
    page_end: int
    chunk_type: str
    score: float
    bm25_score: float
    dense_score: float


@dataclass
class RerankedChunk:
    chunk_id: str
    chunk_pk: str
    chunk_idx: int
    text: str
    text_raw: str
    text_norm: str
    page_start: int
    page_end: int
    chunk_type: str
    score: float
    bm25_score: float
    dense_score: float


def retrieve(
    index: RetrievalIndex,
    query: str,
    top_k: int = 8,
    embedder: EmbeddingClient | None = None,
    use_dense: bool = True,
) -> list[RetrievedChunk]:
    if not index.chunks or index.embeddings.size == 0:
        return []
    bm25_scores = index.bm25.get_scores(query.split())
    if use_dense:
        if index.embedding_backend == "tfidf":
            if index.vectorizer is None:
                raise ValueError("Missing vectorizer for tfidf retrieval.")
            query_vec = index.vectorizer.transform([query]).toarray()
        else:
            if embedder is None:
                raise ValueError("Embedding client required for dense retrieval.")
            query_vec = embedder.embed_texts([query])
        if query_vec.size == 0:
            raise ValueError("Embedding backend returned empty query embedding.")
        dense_scores = cosine_similarity(query_vec, index.embeddings)[0]
    else:
        dense_scores = np.zeros(len(bm25_scores))
    if use_dense:
        combined = 0.5 * np.array(bm25_scores) + 0.5 * np.array(dense_scores)
    else:
        combined = np.array(bm25_scores)
    top_indices = combined.argsort()[-top_k:][::-1]
    results: list[RetrievedChunk] = []
    for idx in top_indices:
        chunk = index.chunks[idx]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                chunk_pk=chunk.chunk_pk,
                chunk_idx=chunk.chunk_idx,
                text=chunk.text,
                text_raw=chunk.text_raw,
                text_norm=chunk.text_norm,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_type=chunk.chunk_type,
                score=float(combined[idx]),
                bm25_score=float(bm25_scores[idx]),
                dense_score=float(dense_scores[idx]),
            )
        )
    return results


def expand_with_neighbors(index: RetrievalIndex, retrieved: list[RetrievedChunk], max_total: int = 12) -> list[RetrievedChunk]:
    id_map = {chunk.chunk_id: chunk for chunk in index.chunks}
    seen = {chunk.chunk_id for chunk in retrieved}
    expanded = list(retrieved)
    for chunk in retrieved:
        neighbors = id_map[chunk.chunk_id].neighbors
        for neighbor in neighbors:
            if neighbor in seen:
                continue
            original = id_map[neighbor]
            expanded.append(
                RetrievedChunk(
                    chunk_id=original.chunk_id,
                    chunk_pk=original.chunk_pk,
                    chunk_idx=original.chunk_idx,
                    text=original.text,
                    text_raw=original.text_raw,
                    text_norm=original.text_norm,
                    page_start=original.page_start,
                    page_end=original.page_end,
                    chunk_type=original.chunk_type,
                    score=chunk.score * 0.8,
                    bm25_score=chunk.bm25_score * 0.8,
                    dense_score=chunk.dense_score * 0.8,
                )
            )
            seen.add(neighbor)
            if len(expanded) >= max_total:
                return expanded
    return expanded


def expand_with_window(
    index: RetrievalIndex,
    retrieved: list[RetrievedChunk],
    window: int = 1,
    max_total: int = 12,
) -> list[RetrievedChunk]:
    if window <= 0:
        return retrieved
    idx_map = {chunk.chunk_idx: chunk for chunk in index.chunks}
    seen = {chunk.chunk_id for chunk in retrieved}
    expanded = list(retrieved)
    for chunk in retrieved:
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            neighbor_idx = chunk.chunk_idx + offset
            if neighbor_idx not in idx_map:
                continue
            original = idx_map[neighbor_idx]
            if original.chunk_id in seen:
                continue
            expanded.append(
                RetrievedChunk(
                    chunk_id=original.chunk_id,
                    chunk_pk=original.chunk_pk,
                    chunk_idx=original.chunk_idx,
                    text=original.text,
                    text_raw=original.text_raw,
                    text_norm=original.text_norm,
                    page_start=original.page_start,
                    page_end=original.page_end,
                    chunk_type=original.chunk_type,
                    score=chunk.score * 0.7,
                    bm25_score=chunk.bm25_score * 0.7,
                    dense_score=chunk.dense_score * 0.7,
                )
            )
            seen.add(original.chunk_id)
            if len(expanded) >= max_total:
                return expanded
    return expanded


def reciprocal_rank_fusion(
    runs: Iterable[list[RetrievedChunk]],
    k: int = 60,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    meta: dict[str, RetrievedChunk] = {}
    for run in runs:
        for rank, chunk in enumerate(run):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            if chunk.chunk_id not in meta:
                meta[chunk.chunk_id] = chunk
    fused = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    results: list[RetrievedChunk] = []
    for chunk_id, score in fused:
        chunk = meta[chunk_id]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                chunk_pk=chunk.chunk_pk,
                chunk_idx=chunk.chunk_idx,
                text=chunk.text,
                text_raw=chunk.text_raw,
                text_norm=chunk.text_norm,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_type=chunk.chunk_type,
                score=score,
                bm25_score=chunk.bm25_score,
                dense_score=chunk.dense_score,
            )
        )
    return results
