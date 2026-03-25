from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import RunArtifacts
from .config import ConfigError, load_and_validate_config, snapshot_config
from .ids import generate_run_id
from .ingest import IngestError, build_input_summary
from .lifecycle import can_transition, map_operator_status
from .schemas import RunCreateResponse, RunProgress, RunRecord, RunStatus, RunSummary


class RunnerError(RuntimeError):
    pass


class RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._artifacts: dict[str, RunArtifacts] = {}

    def create_run(self, config_path: str) -> RunCreateResponse:
        run_id = generate_run_id()
        now = datetime.now(timezone.utc)

        config, _ = load_and_validate_config(config_path)
        artifacts = RunArtifacts.create(Path(config.paths.output_dir), run_id)

        record = RunRecord(
            run_id=run_id,
            status=RunStatus.CREATED,
            operator_status=map_operator_status(RunStatus.CREATED),
            config_path=config_path,
            artifact_dir=str(artifacts.root),
            created_at=now,
            updated_at=now,
            message="Run created and queued for validation.",
        )

        artifacts.write_json("run.json", record.model_dump(mode="json"))

        with self._lock:
            self._runs[run_id] = record
            self._artifacts[run_id] = artifacts

        thread = threading.Thread(target=self._execute_run, args=(run_id, config_path), daemon=True)
        thread.start()

        return RunCreateResponse(
            run_id=run_id,
            status=record.status,
            operator_status=record.operator_status,
        )

    def _transition(
        self,
        run_id: str,
        target: RunStatus,
        message: str | None = None,
        progress: RunProgress | None = None,
    ) -> RunRecord:
        with self._lock:
            current = self._runs[run_id]
            if not can_transition(current.status, target) and current.status != target:
                raise RunnerError(f"Invalid transition {current.status} -> {target}")
            updated = current.model_copy(deep=True)
            updated.status = target
            updated.operator_status = map_operator_status(target)
            if message is not None:
                updated.message = message
            if progress is not None:
                updated.progress = progress
            updated.updated_at = datetime.now(timezone.utc)
            self._runs[run_id] = updated
            artifacts = self._artifacts[run_id]

        artifacts.write_json("run.json", updated.model_dump(mode="json"))
        return updated

    def _execute_run(self, run_id: str, config_path: str) -> None:
        artifacts = self._artifacts[run_id]
        try:
            self._transition(
                run_id,
                RunStatus.VALIDATING,
                message="Validating config paths and input readiness.",
                progress=RunProgress(stage="load_config", item="config"),
            )
            config, _ = load_and_validate_config(config_path)
            snapshot_config(artifacts, config)

            self._transition(
                run_id,
                RunStatus.RUNNING,
                message="Loading table and schema, classifying eligible cells.",
                progress=RunProgress(stage="load_inputs", item="table+schema"),
            )
            input_summary, details = build_input_summary(config)
            artifacts.write_json("inputs/input_summary.json", input_summary.model_dump(mode="json"))
            artifacts.write_json("inputs/input_details.json", details)

            # Batch 1 intentionally stops after validated run-start foundation.
            self._transition(
                run_id,
                RunStatus.COMPLETED_WITH_WARNINGS,
                message="Batch 1 foundation complete: run-start baseline is ready; later extraction stages are not yet implemented.",
                progress=RunProgress(stage="batch1_complete", item="foundation"),
            )
        except (ConfigError, IngestError, Exception) as error:
            self._transition(
                run_id,
                RunStatus.FAILED,
                message=f"Run failed during startup validation: {error}",
                progress=RunProgress(stage="failed", item="startup"),
            )

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            runs = list(self._runs.values())
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            if run_id not in self._runs:
                raise RunnerError(f"Run not found: {run_id}")
            return self._runs[run_id]

    def get_summary(self, run_id: str) -> RunSummary:
        record = self.get_run(run_id)
        artifacts = self._artifacts[run_id]

        snapshot = {}
        input_summary = {}
        try:
            snapshot = artifacts.read_json("config.snapshot.json")
        except FileNotFoundError:
            pass
        try:
            input_summary = artifacts.read_json("inputs/input_summary.json")
        except FileNotFoundError:
            pass

        provider = snapshot.get("provider", {})
        return RunSummary(
            run_id=record.run_id,
            status=record.status,
            operator_status=record.operator_status,
            message=record.message,
            progress=record.progress,
            config_path=record.config_path,
            artifact_dir=record.artifact_dir,
            verify_mode=input_summary.get("verify_mode", snapshot.get("verify_mode", True)),
            table_path=input_summary.get("table_path"),
            schema_path=input_summary.get("schema_path"),
            pdf_dir=input_summary.get("pdf_dir"),
            output_dir=input_summary.get("output_dir"),
            target_columns=input_summary.get("target_columns", []),
            provider_name=provider.get("provider_name") or provider.get("name"),
            model_name=provider.get("model_name") or provider.get("model"),
            provider_locality=provider.get("locality", "local"),
        )

    def read_artifact_json(self, run_id: str, relative_path: str) -> dict[str, Any]:
        if run_id not in self._artifacts:
            raise RunnerError(f"Run not found: {run_id}")
        return self._artifacts[run_id].read_json(relative_path)
