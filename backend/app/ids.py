from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-") or "item"


def stable_hash(*parts: object, length: int = 10) -> str:
    digest = hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return digest[:length]


def make_run_id(seed: str) -> str:
    return f"run-{stable_hash(seed, length=12)}"


def make_pdf_id(run_id: str, pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    return f"pdf-{_slug(path.stem)}-{stable_hash(run_id, path.name)}"


def make_row_id(index: int, title: str) -> str:
    return f"row-{index + 1:04d}-{stable_hash(title, index, length=8)}"


def make_cell_id(row_id: str, column_name: str) -> str:
    return f"cell-{row_id}-{_slug(column_name)}"


def make_proposal_id(run_id: str, cell_id: str) -> str:
    return f"proposal-{stable_hash(run_id, cell_id, length=14)}"


def make_evidence_id(proposal_id: str, page: int, source_type: str) -> str:
    return f"evidence-{stable_hash(proposal_id, page, source_type, length=14)}"


def make_review_decision_id(proposal_id: str, decision: str) -> str:
    return f"review-{stable_hash(proposal_id, decision, length=14)}"


def make_chunk_id(pdf_id: str, page: int, kind: str, ordinal: int) -> str:
    return f"chunk-{stable_hash(pdf_id, page, kind, ordinal, length=14)}"
