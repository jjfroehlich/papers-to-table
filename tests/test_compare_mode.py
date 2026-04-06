from __future__ import annotations

from pathlib import Path

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.study import run_compare_mode


def test_compare_mode_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    run_compare_mode(base_config, benches, out)

    assert (out / "results" / "results.csv").exists()
    assert (out / "results" / "results.jsonl").exists()
    assert (out / "plots" / "compare_primary_by_candidate.png").exists()
    assert (out / "plots" / "compare_correctness_vs_runtime.png").exists()
