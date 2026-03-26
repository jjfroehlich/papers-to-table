from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class RunnerError(RuntimeError):
    pass


class RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._artifacts: dict[str, RunArtifacts] = {}

    def create_run(self, config_path: str) -> RunCreateResponse:
        self._mark_incomplete_runs_interrupted()
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
        artifacts.write_json(
            "summaries/run_summary.json",
            {
                "run_id": run_id,
                "status": "created",
                "operator_status": "ready",
                "message": "Run created.",
                "progress": {"stage": "created", "item": "run"},
            },
        )
        artifacts.write_json(
            "summaries/reviewer_summary.json",
            {
                "run_id": run_id,
                "counts": {
                    "proposals_generated": 0,
                    "reviewed_proposals": 0,
                    "accepted_as_is": 0,
                    "accepted_with_edit": 0,
                    "rejected": 0,
                    "pending": 0,
                    "changed_cells_exported": 0,
                },
            },
        )

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

            # Phase 2 — Parse PDFs
            table_rows: list[dict[str, Any]] = details.get("table_rows", [])
            self._run_parse_stage(run_id, artifacts, config, table_rows)
            artifacts.recompute_summaries(run_id=run_id, verify_mode=config.verify_mode)
        except (ConfigError, IngestError, Exception) as error:
            self._transition(
                run_id,
                RunStatus.FAILED,
                message=f"Run failed: {error}",
                progress=RunProgress(stage="failed", item="run"),
            )
            artifacts.recompute_summaries(run_id=run_id, verify_mode=True)

    def _run_parse_stage(
        self,
        run_id: str,
        artifacts: RunArtifacts,
        config: Any,
        table_rows: list[dict[str, Any]],
    ) -> None:
        """Phase 2: parse PDFs and Phase 3: match to rows."""
        from .config import RunConfig
        from .ingest import load_table
        from .matching import (
            ExtractedMetadata,
            MatchOutcome,
            extract_paper_metadata,
            run_matching_for_run,
        )
        from .parsing import ParsedDocument, parse_pdf_for_run

        pdf_dir = Path(config.paths.pdf_dir)
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            self._transition(
                run_id,
                RunStatus.COMPLETED_WITH_WARNINGS,
                message="No PDF files found in pdf_dir; run is complete with warnings. Extraction and review will be unavailable.",
                progress=RunProgress(stage="parse", item="no_pdfs"),
            )
            return

        parsed_dir = artifacts.root / "parsed"
        matching_dir = artifacts.root / "matching"

        parsed_docs: dict[str, ParsedDocument] = {}
        parse_errors: list[str] = []

        for pdf_path in pdf_files:
            pdf_id = pdf_path.stem
            self._transition(
                run_id,
                RunStatus.RUNNING,
                message=f"Parsing {pdf_path.name}…",
                progress=RunProgress(stage="parse", item=pdf_id),
            )
            try:
                doc, _ocr_used = parse_pdf_for_run(
                    pdf_path=pdf_path,
                    pdf_id=pdf_id,
                    parsed_dir=parsed_dir,
                    render_pages=True,
                )
                parsed_docs[pdf_id] = doc
            except Exception as exc:
                msg = f"Parsing failed for {pdf_path.name}: {exc}"
                logger.warning(msg)
                parse_errors.append(msg)

        # Phase 3: matching
        if not table_rows:
            try:
                table_rows = load_table(config.paths.table_path)
            except Exception as exc:
                logger.warning("Could not reload table rows for matching: %s; proceeding with empty row list", exc)
                table_rows = []

        self._transition(
            run_id,
            RunStatus.RUNNING,
            message=f"Matching {len(parsed_docs)} parsed PDF(s) to table rows…",
            progress=RunProgress(stage="match", item="all_pdfs"),
        )

        pdf_metas: dict[str, ExtractedMetadata] = {}
        for pdf_id, doc in parsed_docs.items():
            pdf_metas[pdf_id] = extract_paper_metadata(doc)

        matching_summary = run_matching_for_run(
            pdf_metas=pdf_metas,
            table_rows=table_rows,
            matching_dir=matching_dir,
            run_id=run_id,
        )

        unresolved_count = (
            matching_summary.ambiguous
            + matching_summary.unmatched
            + matching_summary.duplicate_row_conflict
        )

        # Build matched_pdfs dict: pdf_id -> row_id for cleanly matched PDFs only
        matched_pdfs: dict[str, str] = {}
        try:
            match_records_path = matching_dir / "matching_results.jsonl"
            if match_records_path.exists():
                import json as _json
                with match_records_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        rec = _json.loads(line)
                        if rec.get("outcome") == "matched" and rec.get("matched_row_id"):
                            matched_pdfs[rec["pdf_id"]] = rec["matched_row_id"]
        except Exception as exc:
            logger.warning("Could not load match results for extraction: %s", exc)

        # Phase 4: Style profiles
        schema_rows_for_profiles: list[dict[str, Any]] = []
        try:
            input_details = artifacts.read_json("inputs/input_details.json")
            schema_rows_for_profiles = input_details.get("schema_rows", [])
        except FileNotFoundError:
            pass

        from .provider import build_provider_from_config
        from .style_profiles import generate_and_persist_style_profiles, load_style_profiles

        provider_config = config.provider if hasattr(config, "provider") else {}
        provider = build_provider_from_config(provider_config)

        style_profiles: dict[str, Any] = {}
        if schema_rows_for_profiles:
            self._transition(
                run_id,
                RunStatus.RUNNING,
                message="Generating style profiles…",
                progress=RunProgress(stage="style_profiles", item="all_columns"),
            )
            try:
                style_profiles = generate_and_persist_style_profiles(
                    artifacts=artifacts,
                    schema_rows=schema_rows_for_profiles,
                    table_rows=table_rows,
                    provider=provider,
                )
            except Exception as exc:
                logger.warning("Style profile generation failed (non-fatal): %s", exc)
                style_profiles = load_style_profiles(artifacts)

        # Phase 4: Retrieval chunks + retrieval per matched PDF × column
        from .retrieval import (
            build_chunks,
            build_retrieval_result,
            persist_chunks,
            persist_retrieval_result,
        )

        all_chunks_by_pdf: dict[str, list[Any]] = {}
        retrieval_results: dict[str, dict[str, Any]] = {}

        retrieval_cfg = config.retrieval if hasattr(config, "retrieval") else {}
        top_k = int(retrieval_cfg.get("top_k", 6))

        for pdf_id, doc in parsed_docs.items():
            if pdf_id not in matched_pdfs:
                continue
            self._transition(
                run_id,
                RunStatus.RUNNING,
                message=f"Building retrieval chunks for {pdf_id}…",
                progress=RunProgress(stage="retrieval", item=pdf_id),
            )
            chunks = build_chunks(doc)
            persist_chunks(artifacts, pdf_id, chunks)
            all_chunks_by_pdf[pdf_id] = chunks

            retrieval_results[pdf_id] = {}
            for schema_row in schema_rows_for_profiles:
                col_name = str(schema_row.get("column_name", ""))
                col_desc = str(schema_row.get("description", ""))
                if not col_name:
                    continue
                result = build_retrieval_result(
                    doc=doc,
                    chunks=chunks,
                    column_name=col_name,
                    column_description=col_desc,
                    top_k=top_k,
                )
                persist_retrieval_result(artifacts, result)
                retrieval_results[pdf_id][col_name] = result

        # Phase 5: Extraction
        from .extraction import run_extraction_for_run

        if matched_pdfs and schema_rows_for_profiles:
            self._transition(
                run_id,
                RunStatus.RUNNING,
                message=f"Extracting proposals for {len(matched_pdfs)} matched PDF(s)…",
                progress=RunProgress(stage="extraction", item="all_cells"),
            )
            try:
                extraction_summary = run_extraction_for_run(
                    run_id=run_id,
                    artifacts=artifacts,
                    config=config,
                    matched_pdfs=matched_pdfs,
                    parsed_docs=parsed_docs,
                    schema_rows=schema_rows_for_profiles,
                    table_rows=table_rows,
                    provider=provider,
                    style_profiles=style_profiles,
                    all_chunks_by_pdf=all_chunks_by_pdf,
                    retrieval_results=retrieval_results,
                )
            except Exception as exc:
                logger.error("Extraction stage failed: %s", exc)
                extraction_summary = {"proposals_generated": 0, "skipped_no_provider": 0}
        else:
            extraction_summary = {"proposals_generated": 0, "skipped_no_provider": 0}

        # Compose final run message
        msg_parts = [
            f"Parsed {len(parsed_docs)} PDF(s)",
            f"{matching_summary.matched} matched",
            f"{unresolved_count} unresolved",
            f"{extraction_summary['proposals_generated']} proposals generated",
        ]
        if parse_errors:
            msg_parts.append(f"{len(parse_errors)} parse error(s)")
        if extraction_summary.get("skipped_no_provider"):
            msg_parts.append("no LLM provider configured — cells skipped")
        msg = "; ".join(msg_parts) + "."

        final_status = (
            RunStatus.COMPLETED
            if unresolved_count == 0 and not parse_errors
            else RunStatus.COMPLETED_WITH_WARNINGS
        )
        self._transition(
            run_id,
            final_status,
            message=msg,
            progress=RunProgress(stage="extraction_complete", item="all_cells"),
        )

    def get_matching_unresolved(self, run_id: str) -> list[dict[str, Any]]:
        """Return unresolved match records for the given run (T039)."""
        from .matching import load_unresolved_matches

        if run_id not in self._artifacts:
            raise RunnerError(f"Run not found: {run_id}")
        matching_dir = self._artifacts[run_id].root / "matching"
        return load_unresolved_matches(matching_dir)

    def get_matching_summary(self, run_id: str) -> dict[str, Any]:
        """Return the matching summary for the given run (T039)."""
        from .matching import load_matching_summary

        if run_id not in self._artifacts:
            raise RunnerError(f"Run not found: {run_id}")
        matching_dir = self._artifacts[run_id].root / "matching"
        summary = load_matching_summary(matching_dir)
        if summary is None:
            raise RunnerError("Matching summary not yet available for this run")
        return summary.model_dump(mode="json")

    def get_artifacts(self, run_id: str) -> RunArtifacts:
        """Return the RunArtifacts bundle for the given run."""
        with self._lock:
            if run_id not in self._artifacts:
                raise RunnerError(f"Run not found: {run_id}")
            return self._artifacts[run_id]

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

    def _mark_incomplete_runs_interrupted(self) -> None:
        with self._lock:
            stale_ids = [
                run_id
                for run_id, run in self._runs.items()
                if run.status in {RunStatus.CREATED, RunStatus.VALIDATING, RunStatus.RUNNING}
            ]

        for run_id in stale_ids:
            try:
                self._transition(
                    run_id,
                    RunStatus.INTERRUPTED,
                    message="Run marked interrupted because a newer run was started.",
                    progress=RunProgress(stage="interrupted", item="stale_run"),
                )
            except RunnerError:
                continue
