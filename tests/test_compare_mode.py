from __future__ import annotations

import json
from pathlib import Path

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.study import run_compare_mode


def test_compare_mode_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    run_compare_mode(base_config, benches, out)

    assert (out / "best_candidate.json").exists()
    assert (out / "summary.json").exists()
    assert (out / "results" / "results.csv").exists()
    assert (out / "results" / "results.jsonl").exists()
    assert (out / "plots" / "compare_primary_by_candidate.png").exists()
    assert (out / "plots" / "compare_correctness_vs_runtime.png").exists()
    assert (out / "plots" / "compare_primary_by_text_model.png").exists()
    assert (out / "plots" / "compare_primary_by_knob_retrieval_top_k.png").exists()

    best_candidate = json.loads((out / "best_candidate.json").read_text(encoding="utf-8"))
    assert best_candidate["candidate_id"]
    assert best_candidate["text_model_id"]
    assert best_candidate["prompt_bundle_id"]
    assert isinstance(best_candidate["optimizer_knobs_flat"], dict)
