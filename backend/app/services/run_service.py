from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from ..artifacts import ArtifactStore
from ..ids import new_run_id
from ..models import CreateRunResponse, RunRecord, RunStatus
from .config_service import ConfigValidationError, load_and_resolve_config, validate_inputs
from .matching_service import MatchingService
from .parser_service import ParseService


class RunService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.store = ArtifactStore(base_dir)
        self.parse_service = ParseService(self.store)
        self.matching_service = MatchingService(self.store)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._lock = Lock()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _operator_state(self, status: RunStatus) -> str:
        if status == RunStatus.CREATED:
            return "ready"
        if status == RunStatus.VALIDATING:
            return "validating"
        if status == RunStatus.RUNNING:
            return "running"
        if status == RunStatus.COMPLETED_WITH_WARNINGS:
            return "completed with warnings"
        if status == RunStatus.COMPLETED:
            return "completed"
        return "failed"

    def create_run(self, config_path: str) -> CreateRunResponse:
        run_id = new_run_id()
        run_dir = self.store.create_bundle(run_id)
        run_record = RunRecord(
            run_id=run_id,
            status=RunStatus.CREATED,
            created_at=self._now(),
            updated_at=self._now(),
            operator_state="ready",
            artifact_dir=str(run_dir),
        )
        self.store.write_json(run_dir / "run.json", run_record.model_dump())
        self.executor.submit(self._execute_pipeline, run_id, config_path)
        return CreateRunResponse(run_id=run_id, status=RunStatus.CREATED)

    def _update_run(self, run_dir: Path, status: RunStatus, **extra: Any) -> None:
        with self._lock:
            data = self.store.read_json(run_dir / "run.json")
            data["status"] = status.value
            data["operator_state"] = self._operator_state(status)
            data["updated_at"] = self._now()
            for key, value in extra.items():
                data[key] = value
            self.store.write_json(run_dir / "run.json", data)

    def _execute_pipeline(self, run_id: str, config_path: str) -> None:
        run_dir = self.base_dir / run_id
        try:
            self._update_run(run_dir, RunStatus.VALIDATING)
            config = load_and_resolve_config(Path(config_path))
            input_summary = validate_inputs(config)
            self.store.write_json(run_dir / "config.snapshot.json", config.model_dump())
            self.store.write_json(run_dir / "inputs" / "summary.json", input_summary)
            self._update_run(
                run_dir,
                RunStatus.RUNNING,
                verify_mode=config.review.verify_mode,
                provider_name=config.provider.provider_name,
                model_name=config.provider.model_name,
                provider_locality=config.provider.locality.value,
                pdf_count=input_summary["pdf_count"],
            )
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase1", "message": "Input preparation complete"})
            parsed = self.parse_service.parse_run(run_id, run_dir, config)
            self.store.append_jsonl(
                run_dir / "logs" / "events.jsonl",
                {"stage": "phase2", "message": f"Parsed {len(parsed['documents'])} PDFs"},
            )
            self.matching_service.match(
                run_dir=run_dir,
                parsed_docs=parsed["documents"],
                table_path=Path(config.paths.table_path),
            )
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase3", "message": "Matching complete"})
            self._update_run(run_dir, RunStatus.COMPLETED)
            self.store.recompute_summaries(run_dir)
        except ConfigValidationError as exc:
            self._update_run(run_dir, RunStatus.FAILED, error=str(exc))
        except Exception as exc:  # pragma: no cover
            self._update_run(run_dir, RunStatus.FAILED, error=f"unexpected_error: {exc}")

    def list_runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        if not self.base_dir.exists():
            return runs
        for run_dir in sorted(self.base_dir.glob("run_*"), reverse=True):
            run_json = run_dir / "run.json"
            if run_json.exists():
                runs.append(self.store.read_json(run_json))
        return runs

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.read_json(self.base_dir / run_id / "run.json")

    def get_config_snapshot(self, run_id: str) -> dict[str, Any]:
        return self.store.read_json(self.base_dir / run_id / "config.snapshot.json")

    def get_input_summary(self, run_id: str) -> dict[str, Any]:
        return self.store.read_json(self.base_dir / run_id / "inputs" / "summary.json")

    def get_matching_issues(self, run_id: str) -> dict[str, list[dict[str, Any]]]:
        data = self.store.read_json(self.base_dir / run_id / "matching" / "summary.json")
        results = data.get("results", [])
        return {
            "unmatched": [item for item in results if item.get("match_outcome") == "unmatched"],
            "ambiguous": [item for item in results if item.get("match_outcome") == "ambiguous"],
            "duplicate_row_conflicts": [item for item in results if item.get("match_outcome") == "duplicate_row_conflict"],
        }
