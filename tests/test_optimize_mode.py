from __future__ import annotations

from pathlib import Path

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.search_space import load_search_space
from paper_optimizer.study import run_optimize_mode


def test_optimize_mode_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)
    out = tmp_path / "optimize_exp"
    run_optimize_mode(base_config, benches, search_space, out)

    assert (out / "best_candidate.json").exists()
    assert (out / "rounds" / "round_0001.json").exists()
    assert (out / "plots" / "optimize_best_by_round.png").exists()
    assert (out / "plots" / "optimize_history_best_so_far.png").exists()
    assert (out / "plots" / "optimize_decision_counts_by_round.png").exists()
    assert (out / "plots" / "optimize_primary_by_knob_retrieval_top_k.png").exists()
