from __future__ import annotations

import hashlib
import random
import string
import time
from datetime import datetime, timezone


def generate_run_id() -> str:
    """run_20240315_143022_abc123 format"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"run_{ts}_{suffix}"


def generate_cell_id(row_id: str, column_name: str) -> str:
    """Deterministic hash from row_id + column_name"""
    h = hashlib.sha256(f"{row_id}::{column_name}".encode()).hexdigest()[:12]
    return f"cell_{h}"


def generate_pdf_id(filename: str) -> str:
    """Stable within a run from filename"""
    h = hashlib.sha256(filename.encode()).hexdigest()[:12]
    stem = filename.rsplit(".", 1)[0][:20].replace(" ", "_")
    return f"pdf_{stem}_{h}"


def generate_proposal_id(run_id: str, cell_id: str) -> str:
    ts = int(time.time() * 1000)
    return f"prop_{run_id}_{cell_id}_{ts}"


def generate_evidence_id(proposal_id: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"ev_{proposal_id}_{suffix}"


def generate_review_decision_id(proposal_id: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"rev_{proposal_id}_{suffix}"


def generate_row_id(row_index: int, title: str = "") -> str:
    """Deterministic row id from index + title"""
    h = hashlib.sha256(f"{row_index}::{title}".encode()).hexdigest()[:12]
    return f"row_{h}"
