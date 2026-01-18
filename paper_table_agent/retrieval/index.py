from __future__ import annotations

import hashlib
import json
import pickle
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


def chunks_hash(chunks: list[Chunk]) -> str:
    hasher = hashlib.sha1()
    for chunk in chunks:
        hasher.update(chunk.chunk_id.encode("utf-8"))
        hasher.update(chunk.text.encode("utf-8"))
        hasher.update(str(chunk.page_start).encode("utf-8"))
        hasher.update(str(chunk.page_end).encode("utf-8"))
    return hasher.hexdigest()


def save_index(index: RetrievalIndex, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in to_dicts(index.chunks):
            handle.write(json.dumps(chunk) + "\n")
    np.save(output_dir / "embeddings.npy", index.embeddings)
    with (output_dir / "vectorizer.pkl").open("wb") as handle:
        pickle.dump(index.vectorizer, handle)
    (output_dir / "index_meta.json").write_text(
        json.dumps({"chunks_hash": chunks_hash(index.chunks)}, indent=2),
        encoding="utf-8",
    )


def load_index(output_dir: Path) -> RetrievalIndex | None:
    chunks_path = output_dir / "chunks.jsonl"
    embeddings_path = output_dir / "embeddings.npy"
    vectorizer_path = output_dir / "vectorizer.pkl"
    if not chunks_path.exists() or not embeddings_path.exists() or not vectorizer_path.exists():
        return None
    chunks: list[Chunk] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            chunks.append(
                Chunk(
                    chunk_id=payload["chunk_id"],
                    text=payload["text"],
                    page_start=int(payload["page_start"]),
                    page_end=int(payload["page_end"]),
                    source=payload.get("source", "page"),
                    neighbors=payload.get("neighbors", []),
                )
            )
    embeddings = np.load(embeddings_path)
    with vectorizer_path.open("rb") as handle:
        vectorizer = pickle.load(handle)
    tokens = [chunk.text.split() for chunk in chunks]
    bm25 = BM25Okapi(tokens)
    return RetrievalIndex(chunks=chunks, bm25=bm25, vectorizer=vectorizer, embeddings=embeddings)


def load_index_if_fresh(output_dir: Path, chunks: list[Chunk]) -> RetrievalIndex | None:
    meta_path = output_dir / "index_meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if meta.get("chunks_hash") != chunks_hash(chunks):
        return None
    return load_index(output_dir)
