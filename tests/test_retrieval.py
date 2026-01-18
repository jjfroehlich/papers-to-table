from paper_table_agent.retrieval.chunking import Chunk
from paper_table_agent.retrieval.index import build_index
from paper_table_agent.retrieval.retrieve import retrieve


def test_dense_retrieval_scores():
    chunks = [
        Chunk(chunk_id="c1", text="gene editing method", page_start=1, page_end=1, source="page", neighbors=[]),
        Chunk(chunk_id="c2", text="control group", page_start=2, page_end=2, source="page", neighbors=[]),
    ]
    index = build_index(chunks)
    results = retrieve(index, "gene editing", top_k=2)
    assert results
    assert any(result.dense_score > 0 for result in results)
