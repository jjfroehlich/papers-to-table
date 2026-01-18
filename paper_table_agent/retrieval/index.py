from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from paper_table_agent.retrieval.chunking import Chunk, to_dicts


@dataclass
class RetrievalIndex:
    chunks: list[Chunk]
    bm25: BM25Okapi
    vectorizer: TfidfVectorizer
    embeddings: np.ndarray


def build_index(chunks: list[Chunk]) -> RetrievalIndex:
    texts = [chunk.text for chunk in chunks]
    tokens = [text.split() for text in texts]
    bm25 = BM25Okapi(tokens)
    vectorizer = TfidfVectorizer()
    embeddings = vectorizer.fit_transform(texts).toarray()
    return RetrievalIndex(chunks=chunks, bm25=bm25, vectorizer=vectorizer, embeddings=embeddings)


def save_index(index: RetrievalIndex, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in to_dicts(index.chunks):
            handle.write(json.dumps(chunk) + "\n")
    np.save(output_dir / "embeddings.npy", index.embeddings)
    (output_dir / "vectorizer.json").write_text(
        json.dumps(index.vectorizer.get_params(), indent=2),
        encoding="utf-8",
    )
