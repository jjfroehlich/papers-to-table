from __future__ import annotations

from pathlib import Path

from paper_optimizer.bundle import build_candidate_from_dict, candidate_hash, materialize_candidate_bundle


def test_candidate_hash_stable(tmp_path: Path) -> None:
    data = {
        "prompt_bundle_id": "p1",
        "text_model_id": "m1",
        "vision_model_id": None,
        "optimizer_knobs": {"k": 5},
    }
    c1 = build_candidate_from_dict("cand_0001", data, parent_candidate_id=None, round_index=1)
    c2 = build_candidate_from_dict("cand_0001", data, parent_candidate_id=None, round_index=1)
    assert candidate_hash(c1) == candidate_hash(c2)

    candidate_dir = materialize_candidate_bundle(tmp_path, c1, "bench_dev")
    assert (candidate_dir / "candidate.json").exists()
