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
    text: str
    page_start: int
    page_end: int
    score: float
    bm25_score: float
    dense_score: float


@dataclass
class RerankedChunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float
    bm25_score: float
    dense_score: float


def retrieve(
    index: RetrievalIndex,
    query: str,
    top_k: int = 8,
    embedder: EmbeddingClient | None = None,
) -> list[RetrievedChunk]:
    bm25_scores = index.bm25.get_scores(query.split())
    if index.embedding_backend == "tfidf":
        if index.vectorizer is None:
            raise ValueError("Missing vectorizer for tfidf retrieval.")
        query_vec = index.vectorizer.transform([query]).toarray()
    else:
        if embedder is None:
            raise ValueError("Embedding client required for LM Studio retrieval.")
        query_vec = embedder.embed_texts([query])
    dense_scores = cosine_similarity(query_vec, index.embeddings)[0]
    combined = 0.5 * np.array(bm25_scores) + 0.5 * np.array(dense_scores)
    top_indices = combined.argsort()[-top_k:][::-1]
    results: list[RetrievedChunk] = []
    for idx in top_indices:
        chunk = index.chunks[idx]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
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
                    text=original.text,
                    page_start=original.page_start,
                    page_end=original.page_end,
                    score=chunk.score * 0.8,
                    bm25_score=chunk.bm25_score * 0.8,
                    dense_score=chunk.dense_score * 0.8,
                )
            )
            seen.add(neighbor)
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
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                score=score,
                bm25_score=chunk.bm25_score,
                dense_score=chunk.dense_score,
            )
        )
    return results
