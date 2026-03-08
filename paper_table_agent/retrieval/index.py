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
from paper_table_agent.llm.embeddings import EmbeddingClient


@dataclass
class RetrievalIndex:
    chunks: list[Chunk]
    bm25: BM25Okapi
    vectorizer: TfidfVectorizer | None
    embeddings: np.ndarray
    embedding_backend: str = "tfidf"
    embedding_model: str | None = None


def build_index(
    chunks: list[Chunk],
    embedding_backend: str = "tfidf",
    embedding_client: EmbeddingClient | None = None,
    embedding_model: str | None = None,
) -> RetrievalIndex:
    if embedding_backend not in {"tfidf", "lmstudio", "stub", "hash"}:
        raise ValueError(f"Unsupported embedding backend: {embedding_backend}")
    texts = [chunk.retrieval_text for chunk in chunks]
    if not texts or not any(text.strip() for text in texts):
        embeddings = np.empty((0, 0), dtype=np.float32) if embedding_backend == "tfidf" else embedding_client.embed_texts([])  # type: ignore[union-attr]
        return RetrievalIndex(chunks=[], bm25=BM25Okapi([["__empty__"]]), vectorizer=None, embeddings=embeddings, embedding_backend=embedding_backend, embedding_model=embedding_model)
    tokens = [text.split() for text in texts]
    bm25 = BM25Okapi(tokens)
    vectorizer: TfidfVectorizer | None = None
    if embedding_backend == "tfidf":
        vectorizer = TfidfVectorizer()
        embeddings = vectorizer.fit_transform(texts).toarray()
    else:
        if embedding_client is None:
            raise ValueError("Embedding client required for dense embeddings.")
        embeddings = embedding_client.embed_texts(texts)
    return RetrievalIndex(chunks=chunks, bm25=bm25, vectorizer=vectorizer, embeddings=embeddings, embedding_backend=embedding_backend, embedding_model=embedding_model)


def chunks_hash(chunks: list[Chunk]) -> str:
    hasher = hashlib.sha1()
    for chunk in chunks:
        hasher.update(chunk.chunk_id.encode("utf-8"))
        hasher.update(chunk.retrieval_text.encode("utf-8"))
        hasher.update(str(chunk.page_start).encode("utf-8"))
        hasher.update(str(chunk.page_end).encode("utf-8"))
    return hasher.hexdigest()


def save_index(index: RetrievalIndex, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in to_dicts(index.chunks):
            handle.write(json.dumps(chunk) + "\n")
    np.save(output_dir / "embeddings.npy", index.embeddings)
    if index.vectorizer is not None:
        with (output_dir / "vectorizer.pkl").open("wb") as handle:
            pickle.dump(index.vectorizer, handle)
    (output_dir / "index_meta.json").write_text(json.dumps({"chunks_hash": chunks_hash(index.chunks), "embedding_backend": index.embedding_backend, "embedding_model": index.embedding_model}, indent=2), encoding="utf-8")


def load_index(output_dir: Path) -> RetrievalIndex | None:
    chunks_path = output_dir / "chunks.jsonl"
    embeddings_path = output_dir / "embeddings.npy"
    vectorizer_path = output_dir / "vectorizer.pkl"
    if not chunks_path.exists() or not embeddings_path.exists():
        return None
    chunks: list[Chunk] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            chunks.append(Chunk(
                chunk_id=payload["chunk_id"], chunk_pk=payload.get("chunk_pk", ""), chunk_idx=int(payload.get("chunk_idx", 0)),
                text=payload["text"], text_raw=payload.get("text_raw", payload["text"]), retrieval_text=payload.get("retrieval_text", payload["text"]),
                text_norm=payload.get("text_norm", payload["text"]), page_start=int(payload["page_start"]), page_end=int(payload["page_end"]),
                chunk_type=payload.get("chunk_type", payload.get("source", "page")), neighbors=payload.get("neighbors", []), metadata=payload.get("metadata", {}),
            ))
    embeddings = np.load(embeddings_path)
    bm25 = BM25Okapi([c.retrieval_text.split() for c in chunks]) if chunks else BM25Okapi([["__empty__"]])
    meta_path = output_dir / "index_meta.json"
    backend, model = "tfidf", None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            backend, model = meta.get("embedding_backend", "tfidf"), meta.get("embedding_model")
        except json.JSONDecodeError:
            pass
    vectorizer = None
    if backend == "tfidf":
        if not vectorizer_path.exists():
            return None
        with vectorizer_path.open("rb") as handle:
            vectorizer = pickle.load(handle)
    return RetrievalIndex(chunks=chunks, bm25=bm25, vectorizer=vectorizer, embeddings=embeddings, embedding_backend=backend, embedding_model=model)


def load_index_if_fresh(output_dir: Path, chunks: list[Chunk], embedding_backend: str = "tfidf", embedding_model: str | None = None) -> RetrievalIndex | None:
    index = load_index(output_dir)
    if index is None:
        return None
    if chunks_hash(chunks) != chunks_hash(index.chunks):
        return None
    if index.embedding_backend != embedding_backend:
        return None
    if (index.embedding_model or None) != (embedding_model or None):
        return None
    return index
