from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from paper_table_agent.retrieval.index import RetrievalIndex


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


def retrieve(index: RetrievalIndex, query: str, top_k: int = 8) -> list[RetrievedChunk]:
    bm25_scores = index.bm25.get_scores(query.split())
    query_vec = index.vectorizer.transform([query]).toarray()
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
                )
            )
            seen.add(neighbor)
            if len(expanded) >= max_total:
                return expanded
    return expanded
