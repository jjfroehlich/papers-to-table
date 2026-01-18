from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from paper_table_agent.retrieval.index import RetrievalIndex
from paper_table_agent.retrieval.retrieve import RetrievedChunk, RerankedChunk


@dataclass
class RerankResult:
    chunks: list[RerankedChunk]


def rerank(
    index: RetrievalIndex,
    query: str,
    candidates: list[RetrievedChunk],
    top_k: int = 12,
    backend: str = "tfidf",
) -> RerankResult:
    if not candidates:
        return RerankResult(chunks=[])
    if backend != "tfidf":
        raise ValueError(f"Unsupported reranker backend: {backend}")
    texts = [chunk.text for chunk in candidates]
    candidate_vecs = index.vectorizer.transform(texts).toarray()
    query_vec = index.vectorizer.transform([query]).toarray()
    scores = cosine_similarity(query_vec, candidate_vecs)[0]
    order = np.argsort(scores)[::-1][:top_k]
    reranked: list[RerankedChunk] = []
    for idx in order:
        chunk = candidates[idx]
        reranked.append(
            RerankedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                score=float(scores[idx]),
                bm25_score=chunk.bm25_score,
                dense_score=chunk.dense_score,
            )
        )
    return RerankResult(chunks=reranked)
