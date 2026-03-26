from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from ..artifacts import ArtifactStore
from ..ids import new_run_id
from ..models import CreateRunResponse, RunRecord, RunStatus
from .config_service import ConfigValidationError, load_and_resolve_config, validate_inputs
from .matching_service import MatchingService
from .parser_service import ParseService
from .retrieval_service import RetrievalService
from .style_profile_service import StyleProfileService
from .extraction_service import ExtractionService
from .review_service import ReviewService


class RunService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.store = ArtifactStore(base_dir)
        self.parse_service = ParseService(self.store)
        self.matching_service = MatchingService(self.store)
        self.style_profile_service = StyleProfileService(self.store)
        self.retrieval_service = RetrievalService(self.store)
        self.extraction_service = ExtractionService(self.store)
        self.review_service = ReviewService(self.store)
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
            self._update_run(run_dir, RunStatus.VALIDATING, current_stage='validating_config')
            config = load_and_resolve_config(Path(config_path))
            input_summary = validate_inputs(config)
            self.store.write_json(run_dir / "config.snapshot.json", config.model_dump())
            self.store.write_json(run_dir / "inputs" / "summary.json", input_summary)
            self._update_run(
                run_dir,
                RunStatus.RUNNING,
                current_stage='loading_inputs',
                current_item='config and table validation complete',
                verify_mode=config.review.verify_mode,
                provider_name=config.provider.provider_name,
                model_name=config.provider.model_name,
                provider_locality=config.provider.locality.value,
                pdf_count=input_summary["pdf_count"],
            )
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase1", "message": "Input preparation complete"})
            self._update_run(run_dir, RunStatus.RUNNING, current_stage='parsing_pdfs')
            parsed = self.parse_service.parse_run(run_id, run_dir, config)
            self.store.append_jsonl(
                run_dir / "logs" / "events.jsonl",
                {"stage": "phase2", "message": f"Parsed {len(parsed['documents'])} PDFs"},
            )
            self._update_run(run_dir, RunStatus.RUNNING, current_stage='matching_rows')
            matching = self.matching_service.match(
                run_dir=run_dir,
                parsed_docs=parsed["documents"],
                table_path=Path(config.paths.table_path),
            )
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase3", "message": "Matching complete"})

            table_path = Path(config.paths.table_path)
            table_df = pd.read_excel(table_path) if table_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(table_path)
            schema_path = Path(config.paths.schema_path) if config.paths.schema_path else table_path
            schema_df = pd.read_excel(schema_path, sheet_name="schema") if config.paths.schema_path is None else (pd.read_excel(schema_path) if schema_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(schema_path))

            self._update_run(run_dir, RunStatus.RUNNING, current_stage='building_style_profiles')
            profiles = self.style_profile_service.build_profiles(run_dir, table_df, schema_df)
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase4", "message": "Style profiles generated"})

            self._update_run(run_dir, RunStatus.RUNNING, current_stage='retrieval')
            retrieval = self.retrieval_service.build_retrieval_artifacts(
                run_dir=run_dir,
                parsed_docs=parsed["documents"],
                top_k=config.retrieval.top_k,
            )
            self.store.append_jsonl(run_dir / "logs" / "events.jsonl", {"stage": "phase5", "message": "Retrieval artifacts generated"})

            self._update_run(run_dir, RunStatus.RUNNING, current_stage='extraction')
            extraction = self.extraction_service.run(
                run_id=run_id,
                run_dir=run_dir,
                config=config,
                table_df=table_df,
                schema_df=schema_df,
                style_profiles=profiles,
                matching_results=matching["results"],
                parsed_docs=parsed["documents"],
                retrieval_chunks=retrieval,
            )
            self.store.append_jsonl(
                run_dir / "logs" / "events.jsonl",
                {"stage": "phase6", "message": f"Extraction complete ({extraction['proposal_count']} proposals)"},
            )
            self._update_run(run_dir, RunStatus.RUNNING, current_stage='refreshing_review_index')
            self.review_service.refresh_review_index(run_dir)
            self._update_run(run_dir, RunStatus.COMPLETED, current_stage='completed')
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


    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        return self.store.read_json(self.base_dir / run_id / "summaries" / "run_summary.json")

    def get_reviewer_summary(self, run_id: str) -> dict[str, Any]:
        return self.store.read_json(self.base_dir / run_id / "summaries" / "reviewer_summary.json")

    def get_matching_issues(self, run_id: str) -> dict[str, list[dict[str, Any]]]:
        data = self.store.read_json(self.base_dir / run_id / "matching" / "summary.json")
        results = data.get("results", [])
        return {
            "unmatched": [item for item in results if item.get("match_outcome") == "unmatched"],
            "ambiguous": [item for item in results if item.get("match_outcome") == "ambiguous"],
            "duplicate_row_conflicts": [item for item in results if item.get("match_outcome") == "duplicate_row_conflict"],
        }
