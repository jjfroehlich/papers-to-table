from __future__ import annotations

from pathlib import Path

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.search_space import load_search_space
from paper_optimizer.study import run_optimize_mode, summarize, validate_best


def test_holdout_validation_and_summarize(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)

    exp = tmp_path / "optimize_exp"
    run_optimize_mode(base_config, benches, search_space, exp)

    holdout = tmp_path / "holdout_exp"
    validate_best(base_config, benches, exp, holdout)
    assert (holdout / "results" / "results.csv").exists()

    summarize(base_config, exp)
    assert (exp / "plots" / "optimize_best_by_round.png").exists()
