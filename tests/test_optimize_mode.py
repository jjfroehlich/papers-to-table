from __future__ import annotations

import json
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

    best_candidate = json.loads((out / "best_candidate.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert best_candidate["progress_state"] == "completed"
    assert summary["progress_state"] == "completed"
    assert summary["current_best_candidate_id"] == best_candidate["candidate_id"]
    assert summary["eligible_winner_candidate_id"] == best_candidate["candidate_id"]
    assert summary["provisional_winner_candidate_id"] is None

    report_html = (out / "report.html").read_text(encoding="utf-8")
    assert "Incumbent" in report_html
    assert "Optimize Summary" in report_html
    assert "Promotion History" in report_html
    assert "Search Ceiling" in report_html
    assert "What This Shows" in report_html
    assert "How To Read It" in report_html


def test_optimize_mode_writes_progressive_summary_states(base_config: dict, tmp_path: Path, monkeypatch) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)
    out = tmp_path / "optimize_progress_exp"
    progress_states: list[str] = []

    from paper_optimizer.study import ResultsWriter

    original_write = ResultsWriter.write_experiment_summary

    def _record_progress(self, payload):
        progress_states.append(str(payload.get("progress_state")))
        return original_write(self, payload)

    monkeypatch.setattr(ResultsWriter, "write_experiment_summary", _record_progress)

    run_optimize_mode(base_config, benches, search_space, out)

    assert progress_states
    assert progress_states[0] == "running"
    assert progress_states[-1] == "completed"
