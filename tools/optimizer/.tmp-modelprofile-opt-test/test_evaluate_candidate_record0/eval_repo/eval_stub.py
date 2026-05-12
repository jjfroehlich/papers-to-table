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
(run_output_dir / "scored_cells.jsonl").write_text("{}\n", encoding="utf-8")
(out_dir / "compare" / "runs_comparison.csv").write_text("run_id,structured_accuracy\n", encoding="utf-8")
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
