from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import Candidate
from .utils import flatten_dict, sha256_text, stable_json_dumps, write_json


def candidate_signature_data(candidate: Candidate) -> dict[str, Any]:
    return {
        "prompt_bundle_id": candidate.prompt_bundle_id,
        "text_model_id": candidate.text_model_id,
        "vision_model_id": candidate.vision_model_id,
        "optimizer_knobs": candidate.optimizer_knobs,
        "parent_candidate_id": candidate.parent_candidate_id,
        "round_index": candidate.round_index,
    }


def candidate_hash(candidate: Candidate) -> str:
    return sha256_text(stable_json_dumps(candidate_signature_data(candidate)))


def make_candidate_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:04d}"


def build_candidate_from_dict(
    candidate_id: str,
    data: dict[str, Any],
    *,
    parent_candidate_id: str | None,
    round_index: int | None,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        prompt_bundle_id=str(data["prompt_bundle_id"]),
        text_model_id=str(data["text_model_id"]),
        vision_model_id=str(data.get("vision_model_id")) if data.get("vision_model_id") is not None else None,
        optimizer_knobs=dict(data.get("optimizer_knobs", {})),
        parent_candidate_id=parent_candidate_id,
        round_index=round_index,
    )


def materialize_candidate_bundle(base_dir: Path, candidate: Candidate, benchmark_id: str) -> Path:
    candidate_dir = base_dir / "candidates" / candidate.candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "candidate": candidate.to_dict(),
        "benchmark_id": benchmark_id,
        "candidate_hash": candidate_hash(candidate),
        "optimizer_knobs_flat": flatten_dict(candidate.optimizer_knobs),
    }
    write_json(candidate_dir / "candidate.json", manifest)
    return candidate_dir
