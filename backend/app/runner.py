from __future__ import annotations

import json
from pathlib import Path

from .artifacts import ArtifactStore
from .config import resolve_config_defaults, validate_config
from .extraction import ExtractionOrchestrator
from .matching import match_documents
from .models import (
    AppConfig,
    MatchRecord,
    MatchOutcome,
    ProposalRecord,
    ReviewDecisionType,
    ReviewerSummary,
    RunRecord,
    RunStatus,
    WarningCategory,
)
from .parser import DoclingParserAdapter
from .retrieval import build_retrieval_chunks
from .style_profiles import build_style_profiles
from .summaries import build_reviewer_summary, build_run_summary
from .table_io import build_input_summary, classify_cells, load_schema, load_table, validate_metadata_columns
from .exporter import export_reviewed_changes
from .ids import make_run_id


class Runner:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def create_run(self, config: AppConfig) -> tuple[RunRecord, ArtifactStore]:
        resolved = resolve_config_defaults(config)
        validate_config(resolved)
        run_id = make_run_id(json.dumps(resolved.model_dump(mode="json"), sort_keys=True))
        store = ArtifactStore(self.output_root / run_id)
        run = RunRecord(run_id=run_id, artifact_root=str(store.root), verify_mode=resolved.review.verify_mode)
        store.write_model(store.path("run.json"), run)
        store.write_model(store.path("config.snapshot.json"), resolved)
        return run, store

    def execute(self, config: AppConfig) -> RunRecord:
        run, store = self.create_run(config)
        resolved = resolve_config_defaults(config)
        try:
            run.status = RunStatus.RUNNING
            store.write_model(store.path("run.json"), run)
            rows, headers, _ = load_table(resolved.paths.table_path)
            validate_metadata_columns(headers)
            schema = load_schema(resolved.paths.table_path, resolved.paths.schema_path)
            normalized_rows, eligibility = classify_cells(rows, schema, resolved.review.placeholder_values, resolved.review.verify_mode)
            input_summary = build_input_summary(resolved.paths.table_path, resolved.paths.schema_path, resolved.paths.pdf_dir, normalized_rows, schema, resolved.review.verify_mode)
            store.write_model(store.path("inputs", "input_summary.json"), input_summary)
            store.write_json(store.path("inputs", "rows.json"), normalized_rows)
            store.write_json(store.path("inputs", "eligibility.json"), [item.model_dump(mode="json") for item in eligibility])
            parser = DoclingParserAdapter(resolved.parser, resolved.ocr)
            parsed_docs = []
            for pdf_path in sorted(Path(resolved.paths.pdf_dir).glob("*.pdf")):
                parsed = parser.parse(run.run_id, pdf_path, store)
                parsed_docs.append(parsed)
                store.write_model(store.path("parsed", parsed.pdf_id, "parsed_document.json"), parsed)
                store.write_json(store.path("parsed", parsed.pdf_id, "parser_diagnostics.json"), parsed.diagnostics)
            matches = match_documents(parsed_docs, normalized_rows, resolved.matching)
            store.write_models_jsonl(store.path("matching", "matches.jsonl"), matches)
            style_profiles = build_style_profiles(normalized_rows, schema)
            for profile in style_profiles:
                store.write_model(store.path("style_profiles", f"{profile.column_name}.json"), profile)
            style_by_column = {profile.column_name: profile for profile in style_profiles}
            parsed_by_id = {doc.pdf_id: doc for doc in parsed_docs}
            row_by_id = {row["row_id"]: row for row in normalized_rows}
            eligibility_map: dict[tuple[str, str], object] = {(item.row_id, item.column_name): item for item in eligibility}
            all_proposals: list[ProposalRecord] = []
            all_evidence = []
            extractor = ExtractionOrchestrator(resolved)
            for match in matches:
                if match.row_id:
                    row = row_by_id[match.row_id]
                    eligibility_by_column = {column.column_name: eligibility_map[(match.row_id, column.column_name)] for column in schema}
                else:
                    # attach blocked proposals only for ambiguous/conflict cases if a likely row candidate exists
                    row = row_by_id[matches[0].row_id] if matches and matches[0].row_id else normalized_rows[0]
                    eligibility_by_column = {column.column_name: eligibility_map[(row["row_id"], column.column_name)] for column in schema}
                retrieval_chunks = build_retrieval_chunks(parsed_by_id[match.pdf_id])
                store.write_json(store.path("retrieval", f"{match.pdf_id}.json"), [chunk.model_dump(mode="json") for chunk in retrieval_chunks])
                proposals, evidence = extractor.extract_for_match(run.run_id, match, row, parsed_by_id[match.pdf_id], eligibility_by_column, schema, style_by_column, retrieval_chunks)
                all_proposals.extend(proposals)
                all_evidence.extend(evidence)
            store.write_models_jsonl(store.path("proposals", "proposals.jsonl"), all_proposals)
            store.write_models_jsonl(store.path("evidence", "evidence.jsonl"), all_evidence)
            workbook_name, audit_name, changed, warnings = export_reviewed_changes(resolved.paths.table_path, normalized_rows, all_proposals, store.path("exports"), resolved.export.highlight_hex)
            run.provider_name = extractor.provider.settings.provider if extractor.provider.settings.provider != "stub" else "stub-lmstudio"
            run.provider_model = extractor.provider.settings.model
            if warnings:
                run.warnings.append(WarningCategory.UNSUPPORTED_WORKBOOK_FEATURES)
            if any(match.outcome != MatchOutcome.MATCHED for match in matches):
                run.warnings.append(WarningCategory.COMPLETED_WITH_WARNINGS)
            run.status = RunStatus.COMPLETED_WITH_WARNINGS if run.warnings else RunStatus.COMPLETED
            run_summary = build_run_summary(run, matches, all_proposals, changed)
            reviewer_summary = build_reviewer_summary(run, matches, all_proposals, changed)
            store.write_model(store.path("summaries", "run_summary.json"), run_summary)
            store.write_model(store.path("summaries", "reviewer_summary.json"), reviewer_summary)
            store.write_json(store.path("logs", "diagnostics.json"), {
                "match_outcomes": [item.model_dump(mode="json") for item in matches],
                "warnings": warnings,
                "exports": {"workbook": workbook_name, "audit_log": audit_name},
            })
            run.updated_at = run.updated_at
            store.write_model(store.path("run.json"), run)
            return run
        except KeyboardInterrupt:
            run.status = RunStatus.INTERRUPTED
            store.write_model(store.path("run.json"), run)
            raise
        except Exception as exc:  # noqa: BLE001
            run.status = RunStatus.FAILED
            run.message = str(exc)
            store.write_model(store.path("run.json"), run)
            raise


def sort_proposals(proposals: list[ProposalRecord]) -> list[ProposalRecord]:
    decision_rank = {
        ReviewDecisionType.NONE: 0,
        ReviewDecisionType.ACCEPT: 1,
        ReviewDecisionType.ACCEPT_EDIT: 1,
        ReviewDecisionType.REJECT: 1,
    }
    return sorted(
        proposals,
        key=lambda proposal: (
            decision_rank[proposal.review_decision],
            proposal.row_index,
            proposal.column_order,
            proposal.proposal_id,
        ),
    )
