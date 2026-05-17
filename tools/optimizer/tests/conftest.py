from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def stub_scripts(tmp_path: Path) -> dict[str, str]:
    main_repo = tmp_path / "main_repo"
    eval_repo = tmp_path / "eval_repo"
    main_repo.mkdir(parents=True, exist_ok=True)
    eval_repo.mkdir(parents=True, exist_ok=True)
    (main_repo / "backend" / "app" / "prompt_bundles" / "default").mkdir(parents=True, exist_ok=True)

    main_script = main_repo / "main_stub.py"
    eval_script = eval_repo / "eval_stub.py"
    base_config_path = main_repo / "base_config.json"
    tables_dir = tmp_path / "bench_tables"
    pdfs_dir = tmp_path / "bench_pdfs"
    gold_dir = tmp_path / "gold"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    smoke_table = tables_dir / "smoke.xlsx"
    dev_table = tables_dir / "dev.xlsx"
    holdout_table = tables_dir / "holdout.xlsx"
    schema_path = tables_dir / "schema.json"
    smoke_gold = gold_dir / "smoke.csv"
    dev_gold = gold_dir / "dev.csv"
    holdout_gold = gold_dir / "holdout.csv"

    for path in [smoke_table, dev_table, holdout_table]:
        path.write_text("stub-table", encoding="utf-8")
    schema_path.write_text(json.dumps({"columns": []}), encoding="utf-8")
    for path in [smoke_gold, dev_gold, holdout_gold]:
        path.write_text("row_id,value\nrow-1,yes\n", encoding="utf-8")

    main_script.write_text(
        """
import json
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] != "start":
    raise SystemExit(2)

config_path = Path(args[args.index("--config-path") + 1])
config = json.loads(config_path.read_text(encoding="utf-8"))
output_dir = Path(config["output_dir"])
candidate_id = output_dir.parents[1].name
run_id = f"run_{candidate_id}"
run_dir = output_dir / run_id
(run_dir / "proposals").mkdir(parents=True, exist_ok=True)
(run_dir / "summaries").mkdir(parents=True, exist_ok=True)
(run_dir / "inputs").mkdir(parents=True, exist_ok=True)

text_model_id = config["provider"]["text_model"]["model_id"]
run_payload = {
    "run_id": run_id,
    "status": "completed",
    "run_mode": "eval",
    "prompt_hash": f"hash-{config['prompt']['bundle']}",
    "prompt_bundle_id": config["prompt"]["bundle"],
    "retrieval_mode": config["retrieval"]["mode"],
    "provider_mode": "live_local",
    "provider_text_model_id": text_model_id,
    "warnings": [],
    "current_stage": None,
    "error_message": None,
    "provider_readiness_error": None,
    "provider_readiness_reason": None,
    "text_model_id": text_model_id,
    "eval_artifacts": {
        "gold_table": {
            "source_reference": config.get("table_path"),
            "content_hash": "gold-hash",
            "snapshot_path": "inputs/gold_table.csv",
        },
        "masked_working_table": {
            "path": "inputs/masked_working_table.csv",
            "content_hash": "masked-hash",
        },
    },
}

(run_dir / "inputs" / "gold_table.csv").write_text("row_id,value\\nrow-1,yes\\n", encoding="utf-8")
(run_dir / "inputs" / "masked_working_table.csv").write_text("row_id,value\\nrow-1,\\n", encoding="utf-8")
(run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
(run_dir / "config.snapshot.json").write_text(json.dumps(config), encoding="utf-8")
(run_dir / "proposals" / "proposals.jsonl").write_text("{}\\n", encoding="utf-8")
(run_dir / "summaries" / "run_summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
(run_dir / "summaries" / "reviewer_summary.json").write_text(json.dumps({"pending": 0}), encoding="utf-8")

payload = {
    "schema_version": "main_app_automation.v1",
    "run_id": run_id,
    "status": "completed",
    "is_terminal": True,
    "mode": "eval",
    "config_path": str(config_path.resolve()),
    "output_dir": str(output_dir.resolve()),
    "resolved_inputs": {
        "table_path": {"logical_source": config.get("table_path"), "runtime_locator": config.get("table_path")},
        "schema_path": {"logical_source": config.get("schema_path"), "runtime_locator": config.get("schema_path")},
        "pdf_dir": {"logical_source": config.get("pdf_dir"), "runtime_locator": config.get("pdf_dir")},
    },
    "artifacts": {
        "run_dir": str(run_dir.resolve()),
        "run_json_path": str((run_dir / "run.json").resolve()),
        "config_snapshot_path": str((run_dir / "config.snapshot.json").resolve()),
        "run_summary_path": str((run_dir / "summaries" / "run_summary.json").resolve()),
        "reviewer_summary_path": str((run_dir / "summaries" / "reviewer_summary.json").resolve()),
        "latest_export_path": None,
    },
    "run_summary": {
        "prompt_bundle_id": config["prompt"]["bundle"],
        "prompt_hash": f"hash-{config['prompt']['bundle']}",
        "retrieval_mode": config["retrieval"]["mode"],
        "provider_mode": "live_local",
    },
}
print(json.dumps(payload, sort_keys=True))
""".strip()
        + "\n",
        encoding="utf-8",
    )

    eval_script.write_text(
        """
import json
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] != "evaluate":
    raise SystemExit(2)

run_dir = Path(args[args.index("--run") + 1])
gold_path = Path(args[args.index("--gold") + 1])
out_dir = Path(args[args.index("--out") + 1])
run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
config_snapshot = json.loads((run_dir / "config.snapshot.json").read_text(encoding="utf-8"))
run_id = run_payload["run_id"]
text_model_id = config_snapshot["provider"]["text_model"]["model_id"]

model_scores = {
    "text-model-a": 0.72,
    "text-model-b": 0.81,
    "text-model-c": 0.77,
}
structured_accuracy = model_scores.get(text_model_id, 0.69)
anchor_valid_rate = 0.9 if text_model_id != "text-model-a" else 0.82
missing_proposal_count = 0 if text_model_id != "text-model-a" else 1
join_failure_count = 0 if text_model_id != "text-model-a" else 1

run_output_dir = out_dir / "per-run" / run_id
(out_dir / "compare").mkdir(parents=True, exist_ok=True)
run_output_dir.mkdir(parents=True, exist_ok=True)
summary = {
    "run_id": run_id,
    "run_dir": str(run_dir.resolve()),
    "gold_source": str(gold_path.resolve()),
    "gold_sheet": None,
    "metrics": {
        "structured_accuracy": structured_accuracy,
        "correct_and_anchored_rate": structured_accuracy - 0.05,
        "anchor_valid_rate": anchor_valid_rate,
        "missing_proposal_count": missing_proposal_count,
        "join_failure_count": join_failure_count,
        "contract_warning_count": 0,
    },
    "metadata": {
        "text_model_id": text_model_id,
        "prompt_identity": config_snapshot["prompt"]["bundle"],
        "page_count": 1,
    },
    "contract_warnings": [],
    "join_diagnostics": [],
}
(run_output_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
(run_output_dir / "scored_cells.jsonl").write_text("{}\\n", encoding="utf-8")
(out_dir / "compare" / "runs_comparison.csv").write_text("run_id,structured_accuracy\\n", encoding="utf-8")
(out_dir / "compare" / "runs_comparison.xlsx").write_bytes(b"xlsx")
(out_dir / "compare" / "runs_comparison.parquet").write_bytes(b"parquet")

payload = {
    "schema_version": "paper_eval_cli.v1",
    "command": "evaluate",
    "status": "ok",
    "success": True,
    "output_dir": str(out_dir.resolve()),
    "per_run_dir": str((out_dir / "per-run").resolve()),
    "compare_dir": str((out_dir / "compare").resolve()),
    "run_count": 1,
    "run_ids": [run_id],
    "run_summary_paths": [str((run_output_dir / "run_summary.json").resolve())],
    "scored_cells_paths": [str((run_output_dir / "scored_cells.jsonl").resolve())],
    "judge_records_paths": [],
    "comparison_artifacts": {
        "runs_comparison_csv": str((out_dir / "compare" / "runs_comparison.csv").resolve()),
        "runs_comparison_xlsx": str((out_dir / "compare" / "runs_comparison.xlsx").resolve()),
        "runs_comparison_parquet": str((out_dir / "compare" / "runs_comparison.parquet").resolve()),
    },
}
print(json.dumps(payload, sort_keys=True))
""".strip()
        + "\n",
        encoding="utf-8",
    )

    base_config_path.write_text(
        json.dumps(
            {
                "table_path": str(dev_table),
                "schema_path": str(schema_path),
                "pdf_dir": str(pdfs_dir),
                "output_dir": str(tmp_path / "placeholder_runs"),
                "verify_mode": False,
                "eval_mode": True,
                "provider": {
                    "token": "lm_studio",
                    "text_model": {"model_id": "text-model-a", "temperature": 0.0, "max_tokens": 2048},
                    "vision_model": None,
                },
                "prompt": {"bundle": "default"},
                "retrieval": {
                    "mode": "lexical",
                    "top_k": 6,
                    "recall_rescue_enabled": True,
                    "whole_document_mode": False,
                    "whole_document_max_chars": 12000,
                },
                "style_profiles": {"enabled": True, "max_examples": 3},
                "figure_review": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    return {
        "python": sys.executable,
        "main_repo": str(main_repo),
        "eval_repo": str(eval_repo),
        "main": str(main_script),
        "eval": str(eval_script),
        "base_config_path": str(base_config_path),
        "schema_path": str(schema_path),
        "pdf_dir": str(pdfs_dir),
        "smoke_table": str(smoke_table),
        "dev_table": str(dev_table),
        "holdout_table": str(holdout_table),
        "smoke_gold": str(smoke_gold),
        "dev_gold": str(dev_gold),
        "holdout_gold": str(holdout_gold),
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
            "optimizer_knobs": {
                "retrieval_top_k": 6,
                "recall_rescue_enabled": True,
                "whole_document_mode": False,
            },
        },
        "compare_candidates": [
            {
                "prompt_bundle_id": "default",
                "text_model_id": "text-model-a",
                "vision_model_id": None,
                "optimizer_knobs": {
                    "retrieval_top_k": 6,
                    "recall_rescue_enabled": True,
                    "whole_document_mode": False,
                },
            },
            {
                "prompt_bundle_id": "default",
                "text_model_id": "text-model-b",
                "vision_model_id": None,
                "optimizer_knobs": {
                    "retrieval_top_k": 6,
                    "recall_rescue_enabled": True,
                    "whole_document_mode": False,
                },
            },
            {
                "prompt_bundle_id": "default",
                "text_model_id": "text-model-c",
                "vision_model_id": None,
                "optimizer_knobs": {
                    "retrieval_top_k": 6,
                    "recall_rescue_enabled": True,
                    "whole_document_mode": False,
                },
            },
        ],
        "search_space": {
            "prompt_bundle_ids": ["default"],
            "text_model_ids": ["text-model-a", "text-model-b", "text-model-c"],
            "vision_model_ids": [],
            "numeric_knobs": {
                "retrieval_top_k": {"values": [6]}
            },
        },
        "benchmarks": {
            "smoke": "bench_smoke",
            "dev": "bench_dev",
            "holdout": "bench_holdout",
            "manifests": {
                "bench_smoke": {
                    "table_path": stub_scripts["smoke_table"],
                    "schema_path": stub_scripts["schema_path"],
                    "pdf_dir": stub_scripts["pdf_dir"],
                    "gold_path": stub_scripts["smoke_gold"],
                    "eval_schema_path": stub_scripts["schema_path"],
                    "main_args": [],
                    "eval_args": [],
                    "expected_items": 1,
                },
                "bench_dev": {
                    "table_path": stub_scripts["dev_table"],
                    "schema_path": stub_scripts["schema_path"],
                    "pdf_dir": stub_scripts["pdf_dir"],
                    "gold_path": stub_scripts["dev_gold"],
                    "eval_schema_path": stub_scripts["schema_path"],
                    "main_args": [],
                    "eval_args": [],
                    "expected_items": 3,
                },
                "bench_holdout": {
                    "table_path": stub_scripts["holdout_table"],
                    "schema_path": stub_scripts["schema_path"],
                    "pdf_dir": stub_scripts["pdf_dir"],
                    "gold_path": stub_scripts["holdout_gold"],
                    "eval_schema_path": stub_scripts["schema_path"],
                    "main_args": [],
                    "eval_args": [],
                    "expected_items": 1,
                },
            },
        },
        "benchmark_suites": {
            "smoke_suite": {
                "benchmark_ids": ["bench_smoke"],
                "aggregation": {
                    "method": "weighted_mean",
                    "primary_metric": "correctness",
                    "weights": {"bench_smoke": 1.0},
                },
            },
            "dev_suite": {
                "benchmark_ids": ["bench_dev"],
                "aggregation": {
                    "method": "weighted_mean",
                    "primary_metric": "correctness",
                    "weights": {"bench_dev": 1.0},
                },
            },
            "holdout_suite": {
                "benchmark_ids": ["bench_holdout"],
                "aggregation": {
                    "method": "weighted_mean",
                    "primary_metric": "correctness",
                    "weights": {"bench_holdout": 1.0},
                },
            },
        },
        "replicates": {
            "count": 1,
            "continue_on_failure": True,
        },
        "main_app": {
            "repo_root": stub_scripts["main_repo"],
            "base_config_path": stub_scripts["base_config_path"],
            "command_prefix": [stub_scripts["python"], stub_scripts["main"]],
            "optimizer_knob_map": {
                "retrieval_top_k": "retrieval.top_k",
                "recall_rescue_enabled": "retrieval.recall_rescue_enabled",
                "whole_document_mode": "retrieval.whole_document_mode",
            },
        },
        "eval_app": {
            "repo_root": stub_scripts["eval_repo"],
            "command_prefix": [stub_scripts["python"], stub_scripts["eval"]],
            "metric_groups": {
                "primary": {
                    "correctness": "structured_accuracy",
                },
                "guardrail": {
                    "evidence_quality": "anchor_valid_rate",
                    "null_count": "missing_proposal_count",
                    "failure_count": "join_failure_count",
                },
                "diagnostic": {
                    "contract_warning_count": "contract_warning_count",
                },
            },
        },
        "acceptance": {
            "primary_metric": "correctness",
            "degraded_score_policy": "disallow",
            "min_improvement": 0.001,
            "guardrails": {
                "evidence_quality": {"min": 0.5},
                "null_count": {"max": 2},
                "failure_count": {"max": 2},
                "runtime_seconds": {"max_delta": 1000},
            },
        },
        "compare": {
            "holdout_top_k": 1,
            "suite_id": "dev_suite",
            "holdout_suite_id": "holdout_suite",
        },
    }


@pytest.fixture()
def config_path(tmp_path: Path, base_config: dict) -> Path:
    path = tmp_path / "optimizer.json"
    path.write_text(json.dumps(base_config), encoding="utf-8")
    return path
