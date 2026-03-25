from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import uuid


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{ts}_{uuid.uuid4().hex[:8]}"


def stable_pdf_id(run_id: str, pdf_name: str, index: int) -> str:
    digest = hashlib.sha1(f"{run_id}:{index}:{pdf_name}".encode()).hexdigest()[:10]
    return f"pdf_{digest}"


def stable_cell_id(row_id: str, column_name: str) -> str:
    digest = hashlib.sha1(f"{row_id}:{column_name}".encode()).hexdigest()[:12]
    return f"cell_{digest}"


def new_proposal_id(run_id: str, pdf_id: str, cell_id: str) -> str:
    digest = hashlib.sha1(f"{run_id}:{pdf_id}:{cell_id}".encode()).hexdigest()[:12]
    return f"prop_{digest}"


def new_evidence_id(proposal_id: str, index: int) -> str:
    digest = hashlib.sha1(f"{proposal_id}:{index}".encode()).hexdigest()[:12]
    return f"ev_{digest}"


def new_review_decision_id(run_id: str, proposal_id: str, decided_at: str) -> str:
    digest = hashlib.sha1(f"{run_id}:{proposal_id}:{decided_at}".encode()).hexdigest()[:12]
    return f"dec_{digest}"
