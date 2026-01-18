from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import HydeResult, QueryExpansionResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.retrieval.index import RetrievalIndex
from paper_table_agent.retrieval.rerank import rerank
from paper_table_agent.retrieval.retrieve import RetrievedChunk, reciprocal_rank_fusion, expand_with_neighbors, retrieve


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
    use_reranker: bool = True
    reranker_backend: str = "tfidf"


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
) -> RetrievalContext:
    debug: dict[str, Any] = {"queries": [], "runs": []}
    queries = [query]
    if config.use_query_expansion:
        queries = build_query_variants(helper_client, query, config.query_variants)
    debug["queries"] = queries

    runs: list[list[RetrievedChunk]] = []
    for q in queries:
        results = retrieve(index, q, top_k=config.top_k)
        runs.append(results)
        debug["runs"].append({"query": q, "results": results})

    if config.use_hyde:
        passage = build_hypothetical_passage(helper_client, query)
        if passage:
            hyde_results = retrieve(index, passage, top_k=config.top_k)
            runs.append(hyde_results)
            debug["runs"].append({"query": "[HyDE]", "results": hyde_results})

    fused = reciprocal_rank_fusion(runs, k=config.rrf_k)
    if config.use_reranker:
        reranked = rerank(index, query, fused, top_k=config.rerank_k, backend=config.reranker_backend).chunks
    else:
        reranked = fused[: config.rerank_k]
    expanded = expand_with_neighbors(index, reranked, max_total=config.max_context_chunks)
    trimmed = _trim_to_token_limit(expanded, config.max_context_tokens)
    debug["reranked"] = reranked
    return RetrievalContext(chunks=trimmed, debug=debug)


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
