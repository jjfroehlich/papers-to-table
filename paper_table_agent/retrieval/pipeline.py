from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.embeddings import EmbeddingClient
from paper_table_agent.llm.models import HydeResult, QueryExpansionResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.retrieval.index import RetrievalIndex
from paper_table_agent.retrieval.rerank import rerank
from paper_table_agent.retrieval.retrieve import (
    RetrievedChunk,
    reciprocal_rank_fusion,
    expand_with_neighbors,
    expand_with_window,
    retrieve,
)


@dataclass
class RetrievalConfig:
    top_k: int = 12
    rerank_k: int = 12
    max_context_chunks: int = 16
    query_variants: int = 4
    use_hyde: bool = True
    use_query_expansion: bool = True
    rrf_k: int = 60
    max_context_tokens: int = 1800
    context_window: int = 1
    include_section_chunks: bool = True
    section_chunk_limit: int = 6
    summary_enabled: bool = True
    summary_max_chunks: int = 12
    summary_max_tokens: int = 1000
    use_reranker: bool = True
    use_dense: bool = True
    embedding_backend: str = "tfidf"
    embedding_model: str | None = None
    reranker_backend: str = "tfidf"
    reranker_model: str | None = None


@dataclass
class RetrievalContext:
    chunks: list[RetrievedChunk]
    debug: dict[str, Any]


def build_query_variants(client: LlmClient | None, query: str, n: int) -> list[str]:
    if not client or n <= 0:
        return [query]
    prompt = render_prompt("query_expand.md", query=query)
    try:
        result = client.complete_json(prompt, QueryExpansionResult)
    except Exception:
        return [query]
    queries = [q.strip() for q in result.queries if q.strip()]
    if not queries:
        return [query]
    return queries[:n]


def build_hypothetical_passage(client: LlmClient | None, query: str) -> str | None:
    if not client:
        return None
    prompt = render_prompt("hyde.md", query=query)
    try:
        result = client.complete_json(prompt, HydeResult)
    except Exception:
        return None
    return result.passage.strip() if result.passage else None


def retrieve_context(
    index: RetrievalIndex,
    query: str,
    config: RetrievalConfig,
    helper_client: LlmClient | None = None,
    embedder: EmbeddingClient | None = None,
    reranker_embedder: EmbeddingClient | None = None,
) -> RetrievalContext:
    debug: dict[str, Any] = {"queries": [], "runs": [], "fallbacks": [], "backend": {}}
    queries = [query]
    if config.use_query_expansion:
        queries = build_query_variants(helper_client, query, config.query_variants)
    debug["queries"] = queries
    debug["backend"] = {
        "use_dense": config.use_dense,
        "use_reranker": config.use_reranker,
        "embedding_backend": config.embedding_backend,
        "reranker_backend": config.reranker_backend,
    }

    runs: list[list[RetrievedChunk]] = []
    for q in queries:
        try:
            results = retrieve(index, q, top_k=config.top_k, embedder=embedder, use_dense=config.use_dense)
        except ValueError as exc:
            debug["fallbacks"].append({"stage": "retrieve", "query": q, "error": str(exc)})
            results = retrieve(index, q, top_k=config.top_k, embedder=None, use_dense=False)
        runs.append(results)
        debug["runs"].append(
            {
                "query": q,
                "results": [
                    {
                        "chunk_id": item.chunk_id,
                        "chunk_idx": item.chunk_idx,
                        "score": item.score,
                    }
                    for item in results
                ],
            }
        )

    if config.use_hyde:
        passage = build_hypothetical_passage(helper_client, query)
        if passage:
            try:
                hyde_results = retrieve(index, passage, top_k=config.top_k, embedder=embedder, use_dense=config.use_dense)
            except ValueError as exc:
                debug["fallbacks"].append({"stage": "retrieve", "query": "[HyDE]", "error": str(exc)})
                hyde_results = retrieve(index, passage, top_k=config.top_k, embedder=None, use_dense=False)
            runs.append(hyde_results)
            debug["runs"].append(
                {
                    "query": "[HyDE]",
                    "results": [
                        {
                            "chunk_id": item.chunk_id,
                            "chunk_idx": item.chunk_idx,
                            "score": item.score,
                        }
                        for item in hyde_results
                    ],
                }
            )

    fused = reciprocal_rank_fusion(runs, k=config.rrf_k)
    if config.use_reranker:
        try:
            reranked = rerank(
                index,
                query,
                fused,
                top_k=config.rerank_k,
                backend=config.reranker_backend,
                embedder=reranker_embedder,
            ).chunks
        except ValueError as exc:
            debug["fallbacks"].append({"stage": "rerank", "error": str(exc)})
            reranked = fused[: config.rerank_k]
    else:
        reranked = fused[: config.rerank_k]
    expanded = expand_with_neighbors(index, reranked, max_total=config.max_context_chunks)
    expanded = expand_with_window(index, expanded, window=config.context_window, max_total=config.max_context_chunks)
    if config.include_section_chunks:
        expanded = _include_section_chunks(index, query, expanded, limit=config.section_chunk_limit)
    trimmed = _trim_to_token_limit(expanded, config.max_context_tokens)
    debug["reranked"] = [
        {
            "chunk_id": item.chunk_id,
            "chunk_idx": item.chunk_idx,
            "score": item.score,
        }
        for item in reranked
    ]
    return RetrievalContext(chunks=trimmed, debug=debug)


def _include_section_chunks(
    index: RetrievalIndex,
    query: str,
    chunks: list[RetrievedChunk],
    limit: int,
) -> list[RetrievedChunk]:
    if limit <= 0:
        return chunks
    scores = index.bm25.get_scores(query.split()) if index.bm25 else []
    section_candidates: list[tuple[float, RetrievedChunk]] = []
    for idx, chunk in enumerate(index.chunks):
        if chunk.chunk_type != "section":
            continue
        score = float(scores[idx]) if idx < len(scores) else 0.0
        section_candidates.append(
            (
                score,
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
                    bm25_score=score,
                    dense_score=0.0,
                ),
            )
        )
    if not section_candidates:
        return chunks
    section_candidates.sort(key=lambda item: item[0], reverse=True)
    seen = {chunk.chunk_id for chunk in chunks}
    expanded = list(chunks)
    for _score, section in section_candidates[:limit]:
        if section.chunk_id in seen:
            continue
        expanded.append(section)
        seen.add(section.chunk_id)
    return expanded


def _trim_to_token_limit(chunks: Iterable[RetrievedChunk], max_tokens: int) -> list[RetrievedChunk]:
    total = 0
    trimmed: list[RetrievedChunk] = []
    for chunk in chunks:
        tokens = len(chunk.text.split())
        if total + tokens > max_tokens:
            break
        trimmed.append(chunk)
        total += tokens
    return trimmed
