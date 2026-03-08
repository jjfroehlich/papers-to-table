from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from paper_table_agent.retrieval.index import RetrievalIndex
from paper_table_agent.llm.embeddings import EmbeddingClient
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
    embedder: EmbeddingClient | None = None,
) -> RerankResult:
    if not candidates:
        return RerankResult(chunks=[])
    if backend not in {"tfidf", "lmstudio", "stub", "hash"}:
        raise ValueError(f"Unsupported reranker backend: {backend}")
    texts = [chunk.retrieval_text for chunk in candidates]
    if backend == "tfidf":
        if index.vectorizer is None:
            raise ValueError("Missing vectorizer for tfidf reranking.")
        candidate_vecs = index.vectorizer.transform(texts).toarray()
        query_vec = index.vectorizer.transform([query]).toarray()
    else:
        if embedder is None:
            raise ValueError("Embedding client required for dense reranking.")
        candidate_vecs = embedder.embed_texts(texts)
        query_vec = embedder.embed_texts([query])
        if candidate_vecs.size == 0 or query_vec.size == 0:
            raise ValueError("Embedding backend returned empty reranker embeddings.")
    scores = cosine_similarity(query_vec, candidate_vecs)[0]
    order = np.argsort(scores)[::-1][:top_k]
    reranked: list[RerankedChunk] = []
    for idx in order:
        chunk = candidates[idx]
        reranked.append(
            RerankedChunk(
                chunk_id=chunk.chunk_id,
                chunk_pk=chunk.chunk_pk,
                chunk_idx=chunk.chunk_idx,
                text=chunk.text,
                text_raw=chunk.text_raw,
                retrieval_text=chunk.retrieval_text,
                text_norm=chunk.text_norm,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_type=chunk.chunk_type,
                score=float(scores[idx]),
                bm25_score=chunk.bm25_score,
                dense_score=chunk.dense_score,
            )
        )
    return RerankResult(chunks=reranked)
