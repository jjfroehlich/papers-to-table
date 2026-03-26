from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..artifacts import ArtifactStore
from ..models import ParsedDocument


class RetrievalService:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    @staticmethod
    def _chunk_type(text: str) -> str:
        lowered = text.lower()
        if lowered.startswith("figure") or " fig." in lowered:
            return "caption"
        if "table" in lowered[:24]:
            return "table_region"
        if len(text) > 280:
            return "section"
        return "paragraph"

    def build_retrieval_artifacts(
        self,
        run_dir: Path,
        parsed_docs: list[dict[str, Any]],
        top_k: int,
    ) -> dict[str, list[dict[str, Any]]]:
        all_chunks: list[dict[str, Any]] = []
        by_pdf: dict[str, list[dict[str, Any]]] = {}

        for raw_doc in parsed_docs:
            doc = ParsedDocument.model_validate(raw_doc)
            chunks: list[dict[str, Any]] = []
            for block in doc.blocks:
                display_text = block.text.strip()
                if not display_text:
                    continue
                contextual = f"[Page {block.page}] {display_text}"
                chunk = {
                    "chunk_id": f"{doc.pdf_id}_{block.block_id}",
                    "pdf_id": doc.pdf_id,
                    "page": block.page,
                    "chunk_type": self._chunk_type(display_text),
                    "retrieval_text": contextual,
                    "display_text": display_text,
                    "reading_order": block.reading_order,
                    "neighbor_window": 1,
                }
                chunks.append(chunk)

            chunks.sort(key=lambda item: (item["page"], item["reading_order"]))
            by_pdf[doc.pdf_id] = chunks
            all_chunks.extend(chunks)

        self.store.atomic_write(
            run_dir / "retrieval" / "chunks.jsonl",
            "\n".join(json.dumps(chunk) for chunk in all_chunks) + ("\n" if all_chunks else ""),
        )
        self.store.write_json(
            run_dir / "retrieval" / "diagnostics.json",
            {
                "top_k": top_k,
                "include_tables": True,
                "include_captions": True,
                "neighbor_window": 1,
                "reranker_enabled": False,
                "hyde_enabled": False,
                "query_expansion_enabled": False,
                "chunk_counts": {key: len(value) for key, value in by_pdf.items()},
            },
        )
        return by_pdf
