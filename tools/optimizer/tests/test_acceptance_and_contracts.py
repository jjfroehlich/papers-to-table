from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from contextlib import redirect_stdout

import pytest

from paper_optimizer.acceptance import evaluate_promotion
from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.bundle import build_candidate_from_dict
from paper_optimizer.cli import main as cli_main
from paper_optimizer.contracts import CandidateResult
from paper_optimizer.pipeline import evaluate_candidate_once
from paper_optimizer.search_space import load_search_space
from paper_optimizer.study import _rank_compare_results, run_optimize_mode, validate_best
from paper_optimizer.validation import PreflightError, validate_preflight


def _candidate_result(candidate_id: str, score: float, runtime_seconds: float, *, passed: bool = True) -> CandidateResult:
    return CandidateResult(
        schema_version="1.0",
        experiment_id="exp_test",
        study_type="compare",
        benchmark_id="bench_dev",
        candidate_id=candidate_id,
        parent_candidate_id=None,
        round_index=None,
        candidate_hash=f"hash-{candidate_id}",
        candidate_manifest_path=f"/tmp/{candidate_id}.json",
        candidate_bundle_dir=f"/tmp/{candidate_id}",
        prompt_bundle_id="default",
        text_model_id="text-model-a",
        vision_model_id=None,
        optimizer_knobs_flat={"retrieval_top_k": 6},
        primary_metrics={"correctness": score},
        guardrail_metrics={"evidence_quality": 0.9, "null_count": 0.0, "failure_count": 0.0},
        diagnostic_metrics={},
        runtime_seconds=runtime_seconds,
        runtime_metadata={},
        started_at="",
        ended_at="",
        candidate_status="completed",
        promotion_decision="rejected",
        decision_reason="test",
        main_app_run_ref={},
        eval_output_ref={},
        metadata={"deterministic_gate": {"passed": passed, "failures": [] if passed else ["missing provenance"]}},
    )


def test_evaluate_promotion_rejects_deterministic_gate_failure() -> None:
    incumbent = _candidate_result("cand_0000", 0.8, 10.0)
    challenger = _candidate_result("cand_0001", 0.9, 9.0, passed=False)

    ok, reason = evaluate_promotion(
        incumbent,
        challenger,
        {
            "primary_metric": "correctness",
            "min_improvement": 0.01,
            "guardrails": {},
        },
    )

    assert ok is False
    assert "deterministic checks failed" in reason


def test_evaluate_promotion_rejects_guardrail_regression() -> None:
    incumbent = _candidate_result("cand_0000", 0.8, 10.0)
    challenger = _candidate_result("cand_0001", 0.82, 9.0)
    challenger.guardrail_metrics["null_count"] = 3.0

    ok, reason = evaluate_promotion(
        incumbent,
        challenger,
        {
            "primary_metric": "correctness",
            "min_improvement": 0.01,
            "guardrails": {"null_count": {"max": 2}},
        },
    )

    assert ok is False
    assert reason == "null_count above max"


def test_rank_compare_results_uses_runtime_tiebreaker() -> None:
    faster = _candidate_result("cand_fast", 0.8, 9.0)
    slower = _candidate_result("cand_slow", 0.8, 12.0)

    ranked = _rank_compare_results([slower, faster], "correctness")

    assert [row.candidate_id for row in ranked] == ["cand_fast", "cand_slow"]


def test_validate_preflight_fails_on_missing_prompt_bundle(base_config: dict) -> None:
    base_config["search_space"]["prompt_bundle_ids"] = ["default", "evidence_strict"]
    benches = load_benchmarks(base_config)

    with pytest.raises(PreflightError):
        validate_preflight(base_config, benches, require_holdout=True)


def test_validate_preflight_accepts_src_layout_prompt_bundles(base_config: dict) -> None:
    main_repo = Path(base_config["main_app"]["repo_root"])
    old_root = main_repo / "backend" / "app" / "prompt_bundles"
    shutil.rmtree(old_root)
    src_root = main_repo / "backend" / "src" / "backend" / "app" / "prompt_bundles"
    for prompt_id in ["prompt_base", "default"]:
        (src_root / prompt_id).mkdir(parents=True, exist_ok=True)

    benches = load_benchmarks(base_config)

    validate_preflight(base_config, benches, require_holdout=True)


def test_validate_preflight_rejects_real_benchmark_pointing_at_fixture_assets(base_config: dict) -> None:
    base_config["benchmarks"]["manifests"]["bench_dev"]["benchmark_kind"] = "real_external_dev"
    base_config["benchmarks"]["manifests"]["bench_dev"]["require_non_fixture_inputs"] = True
    base_config["benchmarks"]["manifests"]["bench_dev"]["table_path"] = (
        "/tmp/project/app/tests/fixtures/tables/literature_fixture.xlsx"
    )
    benches = load_benchmarks(base_config)

    with pytest.raises(PreflightError, match="requires real benchmark inputs"):
        validate_preflight(base_config, benches, require_holdout=True)


def test_validate_preflight_rejects_missing_second_judge_when_required(base_config: dict) -> None:
    base_config["benchmarks"]["manifests"]["bench_dev"]["required_judges"] = ["judge_a", "judge_b"]
    base_config["benchmarks"]["manifests"]["bench_dev"]["eval_args"] = ["--judge-model", "judge-model-a"]
    benches = load_benchmarks(base_config)

    with pytest.raises(PreflightError, match="requires judge_b"):
        validate_preflight(base_config, benches, require_holdout=True)


def test_validate_preflight_rejects_planned_gold_without_stable_ids(base_config: dict, tmp_path: Path) -> None:
    gold_path = tmp_path / "legacy_gold.csv"
    gold_path.write_text("Title,status\nPaper A,yes\n", encoding="utf-8")
    base_config["benchmarks"]["manifests"]["bench_dev"]["gold_path"] = str(gold_path)
    benches = load_benchmarks(base_config)

    with pytest.raises(PreflightError, match="missing required stable join column: row_id"):
        validate_preflight(base_config, benches, require_holdout=True)


def test_cli_preflight_command_accepts_valid_config(
    base_config: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_bundle_id = str(base_config["baseline_candidate"]["prompt_bundle_id"])
    prompt_bundle_dir = Path(base_config["main_app"]["repo_root"]) / "backend" / "app" / "prompt_bundles" / prompt_bundle_id
    prompt_bundle_dir.mkdir(parents=True, exist_ok=True)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(base_config), encoding="utf-8")

    stdout = io.StringIO()
    monkeypatch.setattr("sys.argv", ["paper-optimizer", "preflight", "--config", str(config_path)])

    with redirect_stdout(stdout):
        cli_main()

    payload = json.loads(stdout.getvalue().strip())
    assert payload["ok"] is True
    assert payload["experiment_id"] == base_config["experiment_id"]


def test_evaluate_candidate_records_main_contract_failure(base_config: dict, tmp_path: Path) -> None:
    broken_script = tmp_path / "broken_contract_main.py"
    broken_script.write_text(
        """
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[sys.argv.index('--config-path') + 1])
config = json.loads(config_path.read_text(encoding='utf-8'))
output_dir = Path(config['output_dir'])
candidate_id = output_dir.parents[1].name
run_id = f'run_{candidate_id}'
run_dir = output_dir / run_id
(run_dir / 'summaries').mkdir(parents=True, exist_ok=True)
(run_dir / 'run.json').write_text(json.dumps({'run_id': run_id, 'prompt_bundle_id': config['prompt']['bundle']}), encoding='utf-8')
(run_dir / 'config.snapshot.json').write_text(json.dumps(config), encoding='utf-8')
(run_dir / 'summaries' / 'run_summary.json').write_text(json.dumps({'status': 'completed'}), encoding='utf-8')
print(json.dumps({
    'schema_version': 'main_app_automation.v1',
    'run_id': run_id,
    'status': 'completed',
    'is_terminal': True,
    'mode': 'eval',
    'artifacts': {
        'run_dir': str(run_dir.resolve()),
        'run_json_path': str((run_dir / 'run.json').resolve()),
        'config_snapshot_path': str((run_dir / 'config.snapshot.json').resolve()),
        'run_summary_path': str((run_dir / 'summaries' / 'run_summary.json').resolve())
    },
    'run_summary': {
        'prompt_bundle_id': config['prompt']['bundle'],
        'prompt_hash': 'hash-only',
        'retrieval_mode': config['retrieval']['mode'],
        'provider_mode': 'live_local'
    }
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    base_config["main_app"]["command_prefix"] = [base_config["main_app"]["command_prefix"][0], str(broken_script)]

    candidate = build_candidate_from_dict(
        "cand_0101",
        base_config["compare_candidates"][0],
        parent_candidate_id=None,
        round_index=None,
    )
    result = evaluate_candidate_once(
        base_config,
        experiment_dir=tmp_path / "exp",
        candidate=candidate,
        benchmark_id="bench_dev",
        study_type="compare",
        decision="not_promoted",
        reason="contract_test",
    )

    assert result.candidate_status == "failed"
    assert result.decision_reason == "main_app_contract_invalid"
    assert result.metadata["failure_stage"] == "main_app_contract"


def test_validate_best_uses_promoted_incumbent_not_top_score(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)

    exp = tmp_path / "optimize_exp"
    run_optimize_mode(base_config, benches, search_space, exp)

    best_candidate = json.loads((exp / "best_candidate.json").read_text(encoding="utf-8"))["candidate_id"]
    results_path = exp / "results" / "results.jsonl"
    records = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        if record["candidate_id"] != best_candidate and record["candidate_status"] == "completed":
            record["primary_metrics"]["correctness"] = 999.0
            break
    results_path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

    holdout = tmp_path / "holdout_exp"
    validate_best(base_config, benches, exp, holdout)

    holdout_records = [json.loads(line) for line in (holdout / "results" / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert holdout_records[0]["candidate_id"] == best_candidate
