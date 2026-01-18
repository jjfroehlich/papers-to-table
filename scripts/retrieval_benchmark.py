from __future__ import annotations

import argparse
import json
from pathlib import Path

from paper_table_agent.retrieval.index import load_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval sanity benchmark")
    parser.add_argument("--run_dir", required=True, type=Path)
    parser.add_argument("--pdf_id", required=True)
    parser.add_argument("--queries", required=True, type=Path, help="JSON list of query strings")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    index = load_index(args.run_dir / "artifacts" / "retrieval_indexes" / args.pdf_id)
    if not index:
        raise SystemExit("Retrieval index not found; run parsing/indexing first.")
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    results = []
    for query in queries:
        context = retrieve_context(index, query, RetrievalConfig())
        results.append(
            {
                "query": query,
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "score": chunk.score,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "text": chunk.text,
                    }
                    for chunk in context.chunks
                ],
            }
        )
    output = args.output or args.run_dir / "artifacts" / "retrieval_indexes" / args.pdf_id / "benchmark.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote benchmark results to {output}")


if __name__ == "__main__":
    main()
