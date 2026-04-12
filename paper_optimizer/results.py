from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .contracts import CandidateResult, RoundSummary
from .utils import write_json


class ResultsWriter:
    def __init__(self, experiment_dir: Path) -> None:
        self.experiment_dir = experiment_dir
        self.results_dir = experiment_dir / "results"
        self.plots_dir = experiment_dir / "plots"
        self.rounds_dir = experiment_dir / "rounds"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        self.rounds_dir.mkdir(parents=True, exist_ok=True)

        self.csv_path = self.results_dir / "results.csv"
        self.jsonl_path = self.results_dir / "results.jsonl"
        self._csv_fieldnames: list[str] | None = None

    def write_experiment_manifest(self, manifest: dict[str, Any]) -> None:
        write_json(self.experiment_dir / "experiment.json", manifest)

    def write_best_candidate(self, payload: dict[str, Any]) -> None:
        write_json(self.experiment_dir / "best_candidate.json", payload)

    def write_no_winner(self, payload: dict[str, Any]) -> None:
        write_json(self.experiment_dir / "no_winner.json", payload)

    def write_round_summary(self, summary: RoundSummary) -> None:
        write_json(self.rounds_dir / f"round_{summary.round_index:04d}.json", summary.to_dict())

    def write_experiment_summary(self, payload: dict[str, Any]) -> None:
        write_json(self.experiment_dir / "summary.json", payload)

    def append_result(self, result: CandidateResult) -> None:
        row = self._flatten_row(result)
        self._append_csv(row)
        self._append_jsonl(result.to_dict())

    def _flatten_row(self, result: CandidateResult) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema_version": result.schema_version,
            "experiment_id": result.experiment_id,
            "study_type": result.study_type,
            "candidate_status": result.candidate_status,
            "candidate_id": result.candidate_id,
            "parent_candidate_id": result.parent_candidate_id,
            "round_index": result.round_index,
            "benchmark_id": result.benchmark_id,
            "candidate_hash": result.candidate_hash,
            "candidate_manifest_path": result.candidate_manifest_path,
            "candidate_bundle_dir": result.candidate_bundle_dir,
            "prompt_bundle_id": result.prompt_bundle_id,
            "text_model_id": result.text_model_id,
            "vision_model_id": result.vision_model_id,
            "scored": result.scored,
            "score_status": result.score_status,
            "unscored_reason": result.unscored_reason,
            "unscored_reason_detail": result.unscored_reason_detail,
            "runtime_seconds": result.runtime_seconds,
            "runtime.main_app_duration_seconds": result.runtime_metadata.get("main_app_duration_seconds"),
            "runtime.eval_duration_seconds": result.runtime_metadata.get("eval_duration_seconds"),
            "runtime.total_duration_seconds": result.runtime_metadata.get("total_duration_seconds"),
            "started_at": result.started_at,
            "ended_at": result.ended_at,
            "promotion_decision": result.promotion_decision,
            "decision_reason": result.decision_reason,
            "structured_output_mode": result.structured_output_mode,
            "structured_output_reason": result.structured_output_reason,
            "prompt_only_degraded_mode_used": result.prompt_only_degraded_mode_used,
            "parse_repair_used": result.parse_repair_used,
            "extraction_contract_valid": result.extraction_contract_valid,
            "extraction_contract_warnings": "|".join(result.extraction_contract_warnings),
            "retrieval_mode": result.retrieval_mode,
            "retrieval_top_k": result.retrieval_top_k,
            "recall_rescue_enabled": result.recall_rescue_enabled,
            "whole_document_mode": result.whole_document_mode,
            "whole_document_max_chars": result.whole_document_max_chars,
            "recall_rescue_used": result.recall_rescue_used,
            "recall_rescue_invocation_count": result.recall_rescue_invocation_count,
            "whole_document_used_count": result.whole_document_used_count,
            "main_app_run_id": result.main_app_run_ref.get("run_id"),
            "main_app_run_path": result.main_app_run_ref.get("run_path"),
            "main_app_output_path": result.main_app_run_ref.get("output_path"),
            "main_app_return_code": result.main_app_run_ref.get("return_code"),
            "main_app_resolved_config_path": (result.main_app_run_ref.get("artifact_paths") or {}).get("resolved_main_config_path"),
            "main_app_overlay_path": (result.main_app_run_ref.get("artifact_paths") or {}).get("main_config_overlay_path"),
            "eval_output_path": result.eval_output_ref.get("output_path"),
            "eval_return_code": result.eval_output_ref.get("return_code"),
            "eval_summary_path": result.eval_output_ref.get("summary_path"),
        }

        for key, value in result.optimizer_knobs_flat.items():
            row[f"knob.{key}"] = value
        for key, value in result.primary_metrics.items():
            row[f"primary.{key}"] = value
        for key, value in result.guardrail_metrics.items():
            row[f"guardrail.{key}"] = value
        for key, value in result.diagnostic_metrics.items():
            row[f"diagnostic.{key}"] = value

        return row

    def _append_csv(self, row: dict[str, Any]) -> None:
        if self._csv_fieldnames is None:
            if self.csv_path.exists():
                with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    self._csv_fieldnames = list(reader.fieldnames or [])
            else:
                self._csv_fieldnames = list(row.keys())

        for key in row:
            if key not in self._csv_fieldnames:
                self._csv_fieldnames.append(key)

        existing_rows: list[dict[str, Any]] = []
        if self.csv_path.exists():
            with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                existing_rows = list(reader)

        existing_rows.append({k: row.get(k) for k in self._csv_fieldnames})
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self._csv_fieldnames)
            writer.writeheader()
            for existing in existing_rows:
                writer.writerow(existing)

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def load_results_jsonl(experiment_dir: Path) -> list[dict[str, Any]]:
    path = experiment_dir / "results" / "results.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
