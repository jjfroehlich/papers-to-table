from pathlib import Path

from paper_table_agent.pdf.parser import parse_pdf
from paper_table_agent.retrieval.chunking import Chunk, build_chunks
from paper_table_agent.retrieval.index import build_index
from paper_table_agent.llm.embeddings import HashEmbeddingClient
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.retrieval.retrieve import retrieve


def test_dense_retrieval_scores():
    chunks = [
        Chunk(
            chunk_id="c1",
            chunk_pk="pk1",
            chunk_idx=1,
            text="gene editing method",
            text_raw="gene editing method",
            text_norm="gene editing method",
            page_start=1,
            page_end=1,
            chunk_type="page",
            neighbors=[],
        ),
        Chunk(
            chunk_id="c2",
            chunk_pk="pk2",
            chunk_idx=2,
            text="control group",
            text_raw="control group",
            text_norm="control group",
            page_start=2,
            page_end=2,
            chunk_type="page",
            neighbors=[],
        ),
    ]
    index = build_index(chunks)
    results = retrieve(index, "gene editing", top_k=2)
    assert results
    assert any(result.dense_score > 0 for result in results)


def test_retrieval_smoke_fixture_pdf():
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    parsed = parse_pdf(fixture_pdf)
    chunks = build_chunks(parsed.page_text)
    index = build_index(chunks)
    context = retrieve_context(
        index,
        "Minimal Paper",
        RetrievalConfig(use_dense=False, use_reranker=False, use_query_expansion=False, use_hyde=False),
        helper_client=None,
        embedder=None,
        reranker_embedder=None,
    )
    assert context.chunks
    assert any("Minimal Paper" in chunk.text_raw for chunk in context.chunks)


def test_hash_embedding_backend_retrieval():
    chunks = [
        Chunk(
            chunk_id="c1",
            chunk_pk="pk1",
            chunk_idx=1,
            text="gene editing method",
            text_raw="gene editing method",
            text_norm="gene editing method",
            page_start=1,
            page_end=1,
            chunk_type="page",
            neighbors=[],
        ),
        Chunk(
            chunk_id="c2",
            chunk_pk="pk2",
            chunk_idx=2,
            text="control group",
            text_raw="control group",
            text_norm="control group",
            page_start=2,
            page_end=2,
            chunk_type="page",
            neighbors=[],
        ),
    ]
    index = build_index(chunks, embedding_backend="hash", embedding_client=HashEmbeddingClient())
    results = retrieve(index, "gene editing", top_k=2, embedder=HashEmbeddingClient(), use_dense=True)
    assert results
