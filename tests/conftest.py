from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def stub_scripts(tmp_path: Path) -> dict[str, str]:
    main_script = tmp_path / "main_stub.py"
    eval_script = tmp_path / "eval_stub.py"

    main_script.write_text(
        """
import json
import os
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)

candidate_id = out_dir.parent.name
payload = {
    "run_id": f"run_{candidate_id}",
    "run_path": str(out_dir / "main_run_artifact"),
}
(out_dir / "main_run.json").write_text(json.dumps(payload), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    eval_script.write_text(
        """
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
main_run_ref = Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)

run_ref = json.loads(main_run_ref.read_text(encoding=\"utf-8\"))
run_id = run_ref.get(\"run_id\", \"run_cand_0000\")
candidate_id = run_id.replace(\"run_\", \"\")
try:
    idx = int(candidate_id.split(\"_\")[-1])
except Exception:
    idx = 0

primary = 0.5 + (idx * 0.01)
summary = {
    "primary_metrics": {"correctness": primary},
    "guardrail_metrics": {
        "evidence_quality": 0.9,
        "null_rate": 0.05,
        "failure_rate": 0.0,
    },
    "diagnostic_metrics": {"warning_count": 0.0},
    "runtime_seconds": 30.0 + idx,
}
(out_dir / "eval_summary.json").write_text(json.dumps(summary), encoding=\"utf-8\")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return {
        "python": sys.executable,
        "main": str(main_script),
        "eval": str(eval_script),
    }


@pytest.fixture()
def base_config(tmp_path: Path, stub_scripts: dict[str, str]) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "exp_test",
        "baseline_candidate": {
            "prompt_bundle_id": "prompt_base",
            "text_model_id": "text-model-a",
            "vision_model_id": None,
            "optimizer_knobs": {"retrieval_top_k": 5},
        },
        "compare_candidates": [
            {
                "prompt_bundle_id": "prompt_a",
                "text_model_id": "text-model-a",
                "vision_model_id": None,
                "optimizer_knobs": {"retrieval_top_k": 5},
            },
            {
                "prompt_bundle_id": "prompt_b",
                "text_model_id": "text-model-b",
                "vision_model_id": None,
                "optimizer_knobs": {"retrieval_top_k": 10},
            },
        ],
        "search_space": {
            "prompt_bundle_ids": ["prompt_base", "prompt_b"],
            "text_model_ids": ["text-model-a", "text-model-b"],
            "vision_model_ids": [],
            "numeric_knobs": {
                "retrieval_top_k": {"values": [5, 10]}
            },
        },
        "benchmarks": {
            "dev": "bench_dev",
            "holdout": "bench_holdout",
            "manifests": {
                "bench_dev": {
                    "main_args": [],
                    "eval_args": [],
                    "expected_items": 2,
                },
                "bench_holdout": {
                    "main_args": [],
                    "eval_args": [],
                    "expected_items": 1,
                },
            },
        },
        "main_app": {
            "command": [stub_scripts["python"], stub_scripts["main"], "{out_dir}"],
            "run_reference_file": "main_run.json",
        },
        "eval_app": {
            "command": [stub_scripts["python"], stub_scripts["eval"], "{out_dir}", "{main_run_ref}"],
            "summary_file": "eval_summary.json",
        },
        "acceptance": {
            "primary_metric": "correctness",
            "min_improvement": 0.001,
            "guardrails": {
                "evidence_quality": {"min": 0.5},
                "null_rate": {"max": 0.3},
                "failure_rate": {"max": 0.1},
                "runtime_seconds": {"max_delta": 1000},
            },
        },
        "optimize": {
            "rounds": 2,
            "batch_size": 2,
        },
        "compare": {
            "holdout_top_k": 1,
        },
    }


@pytest.fixture()
def config_path(tmp_path: Path, base_config: dict) -> Path:
    path = tmp_path / "optimizer.json"
    path.write_text(json.dumps(base_config), encoding="utf-8")
    return path
