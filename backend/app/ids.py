from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone


def _normalize(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"\s+", "_", lowered)
    lowered = re.sub(r"[^a-z0-9_\-]", "", lowered)
    return lowered


def generate_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"run_{stamp}_{suffix}"


def make_cell_id(row_id: str, column_name: str) -> str:
    basis = f"{_normalize(row_id)}::{_normalize(column_name)}"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"cell_{digest}"


def make_pdf_id(filename: str, index: int) -> str:
    normalized = _normalize(filename)
    digest = hashlib.sha1(f"{index}:{normalized}".encode("utf-8")).hexdigest()[:10]
    return f"pdf_{digest}"


def make_proposal_id(run_id: str, pdf_id: str, cell_id: str) -> str:
    digest = hashlib.sha1(f"{run_id}:{pdf_id}:{cell_id}".encode("utf-8")).hexdigest()[:12]
    return f"proposal_{digest}"


def make_evidence_id(run_id: str, proposal_id: str, ordinal: int) -> str:
    digest = hashlib.sha1(f"{run_id}:{proposal_id}:{ordinal}".encode("utf-8")).hexdigest()[:12]
    return f"evidence_{digest}"


def make_review_decision_id(run_id: str, proposal_id: str, ordinal: int) -> str:
    digest = hashlib.sha1(f"{run_id}:{proposal_id}:{ordinal}".encode("utf-8")).hexdigest()[:12]
    return f"decision_{digest}"
