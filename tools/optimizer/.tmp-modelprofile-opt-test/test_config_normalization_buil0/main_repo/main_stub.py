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

(run_dir / "inputs" / "gold_table.csv").write_text("row_id,value\nrow-1,yes\n", encoding="utf-8")
(run_dir / "inputs" / "masked_working_table.csv").write_text("row_id,value\nrow-1,\n", encoding="utf-8")
(run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
(run_dir / "config.snapshot.json").write_text(json.dumps(config), encoding="utf-8")
(run_dir / "proposals" / "proposals.jsonl").write_text("{}\n", encoding="utf-8")
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
