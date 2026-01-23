from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable
import hashlib

import httpx
import numpy as np


@dataclass
class EmbeddingConfig:
    base_url: str
    api_key: str | None
    model: str
    timeout_s: float = 60.0
    max_retries: int = 2
    batch_size: int = 64


class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=self.config.timeout_s)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        embeddings: list[list[float]] = []
        for batch in _batched(texts, self.config.batch_size):
            embeddings.extend(self._embed_batch(batch))
        return np.array(embeddings, dtype=np.float32)

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        url = f"{self.config.base_url}/embeddings"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        payload = {"model": self.config.model, "input": batch}
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            response = self._client.post(url, json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise RuntimeError(
                        f"Embedding HTTP error {response.status_code}: {response.text}"
                    ) from exc
                time.sleep(1 + attempt)
                continue
            data = response.json().get("data", [])
            ordered = _order_embeddings(data, len(batch))
            if ordered is None:
                raise RuntimeError("Embedding response missing expected indices.")
            return ordered
        raise RuntimeError(f"Embedding request failed: {last_error}")


class StubEmbeddingClient:
    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha1(text.encode("utf-8")).digest()
            values = [byte / 255.0 for byte in digest[: self.dimension]]
            vectors.append(values)
        return np.array(vectors, dtype=np.float32)


def _order_embeddings(data: Iterable[dict[str, object]], expected_len: int) -> list[list[float]] | None:
    ordered: list[list[float] | None] = [None] * expected_len
    for item in data:
        index = item.get("index")
        embedding = item.get("embedding")
        if index is None or embedding is None:
            continue
        if not isinstance(index, int):
            continue
        if 0 <= index < expected_len:
            ordered[index] = embedding  # type: ignore[assignment]
    if any(item is None for item in ordered):
        return None
    return [item for item in ordered if item is not None]


def _batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    for idx in range(0, len(items), batch_size):
        yield items[idx : idx + batch_size]
