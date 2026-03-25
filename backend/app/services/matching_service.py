from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..artifacts import ArtifactStore
from ..models import MatchOutcome, ParsedDocument


def _norm(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


class MatchingService:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def _extract_metadata(self, doc: ParsedDocument, pdf_path: str) -> dict[str, Any]:
        title = doc.metadata.title or Path(pdf_path).stem.replace("_", " ")
        year = doc.metadata.publication_year
        if year is None:
            m = re.search(r"(19|20)\d{2}", doc.normalized_text[:300])
            if m:
                year = int(m.group(0))
        return {
            "title": title,
            "authors": doc.metadata.authors,
            "publication_year": year,
            "identifiers": doc.metadata.identifiers,
        }

    def _score(self, row: pd.Series, metadata: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        score = 0
        reasons: dict[str, Any] = {}
        row_title = _norm(row.get("Title"))
        doc_title = _norm(metadata["title"])
        if doc_title and row_title == doc_title:
            score += 60
            reasons["title"] = "exact"
        elif doc_title and (doc_title in row_title or row_title in doc_title):
            score += 35
            reasons["title"] = "partial"
        row_year = str(row.get("Publication Year", "")).strip()
        doc_year = str(metadata.get("publication_year") or "").strip()
        if row_year and doc_year and row_year == doc_year:
            score += 30
            reasons["year"] = "exact"
        row_authors = _norm(row.get("Authors"))
        if metadata["authors"]:
            tokens = {_norm(a).split(" ")[-1] for a in metadata["authors"] if _norm(a)}
            author_hit = any(token and token in row_authors for token in tokens)
            if author_hit:
                score += 20
                reasons["authors"] = "surname_overlap"
        return score, reasons

    def match(self, run_dir: Path, parsed_docs: list[dict[str, Any]], table_path: Path) -> dict[str, Any]:
        table_df = pd.read_excel(table_path) if table_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(table_path)
        outcomes: list[dict[str, Any]] = []
        matched_by_row: dict[int, list[int]] = {}
        for idx, raw_doc in enumerate(parsed_docs):
            doc = ParsedDocument.model_validate(raw_doc)
            metadata = self._extract_metadata(doc, raw_doc["source_pdf_path"])
            scored_rows: list[dict[str, Any]] = []
            for row_idx, row in table_df.iterrows():
                score, reasons = self._score(row, metadata)
                if score > 0:
                    scored_rows.append({"row_index": int(row_idx), "score": score, "reasons": reasons})
            scored_rows.sort(key=lambda item: item["score"], reverse=True)
            outcome = MatchOutcome.UNMATCHED.value
            chosen_row_index = None
            if scored_rows:
                top = scored_rows[0]
                second = scored_rows[1] if len(scored_rows) > 1 else None
                if top["score"] < 45:
                    outcome = MatchOutcome.UNMATCHED.value
                elif second and (top["score"] - second["score"] < 15):
                    outcome = MatchOutcome.AMBIGUOUS.value
                else:
                    outcome = MatchOutcome.MATCHED.value
                    chosen_row_index = top["row_index"]
            result = {
                "pdf_id": doc.pdf_id,
                "source_pdf_path": doc.source_pdf_path,
                "metadata": metadata,
                "match_outcome": outcome,
                "matched_row_index": chosen_row_index,
                "candidates": scored_rows[:3],
            }
            outcomes.append(result)
            if outcome == MatchOutcome.MATCHED.value and chosen_row_index is not None:
                matched_by_row.setdefault(chosen_row_index, []).append(idx)

        for _, indices in matched_by_row.items():
            if len(indices) > 1:
                for i in indices:
                    outcomes[i]["match_outcome"] = MatchOutcome.DUPLICATE_ROW_CONFLICT.value
                    outcomes[i]["conflict_pdf_ids"] = [
                        outcomes[j]["pdf_id"] for j in indices if j != i
                    ]
                    outcomes[i]["matched_row_index"] = None

        self.store.write_json(run_dir / "matching" / "summary.json", {"results": outcomes})
        self.store.atomic_write(
            run_dir / "matching" / "results.jsonl",
            "\n".join([json.dumps(result) for result in outcomes]) + ("\n" if outcomes else ""),
        )
        return {"results": outcomes}
