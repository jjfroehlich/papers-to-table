from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..artifacts import ArtifactStore
from ..ids import new_review_decision_id
from ..models import ReviewDecisionType, WarningCategory


class ReviewService:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _latest_decisions(self, decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in decisions:
            proposal_id = row.get("proposal_id")
            decided_at = row.get("decided_at", "")
            prev = latest.get(proposal_id)
            if prev is None or decided_at >= prev.get("decided_at", ""):
                latest[proposal_id] = row
        return latest

    def _proposal_warnings(
        self,
        proposal: dict[str, Any],
        evidence: list[dict[str, Any]],
        match_outcome: str,
    ) -> list[str]:
        warnings: list[str] = []
        if match_outcome == "ambiguous":
            warnings.append(WarningCategory.AMBIGUOUS_MATCH.value)
        if match_outcome == "duplicate_row_conflict":
            warnings.append(WarningCategory.DUPLICATE_ROW_CONFLICT.value)
        if proposal.get("support_label") == "weak_evidence" or proposal.get("needs_more_evidence"):
            warnings.append(WarningCategory.WEAK_EVIDENCE.value)
        if proposal.get("support_label") == "figure_based_evidence":
            warnings.append(WarningCategory.FIGURE_DERIVED.value)
        if any(item.get("quote_text") and item.get("page") and not item.get("highlight") for item in evidence):
            warnings.append(WarningCategory.QUOTE_PAGE_NO_HIGHLIGHT.value)
        return sorted(set(warnings))

    def refresh_review_index(self, run_dir: Path) -> dict[str, Any]:
        proposals = self.store.read_jsonl(run_dir / "proposals" / "proposals.jsonl")
        evidence_rows = self.store.read_jsonl(run_dir / "evidence" / "evidence.jsonl")
        matching_results = self.store.read_json(run_dir / "matching" / "summary.json").get("results", [])
        decisions = self.store.read_jsonl(run_dir / "review" / "decisions.jsonl")
        run_json = self.store.read_json(run_dir / "run.json")

        evidence_by_proposal: dict[str, list[dict[str, Any]]] = {}
        for item in evidence_rows:
            evidence_by_proposal.setdefault(item.get("proposal_id", ""), []).append(item)

        match_by_pdf = {item.get("pdf_id"): item.get("match_outcome", "unmatched") for item in matching_results}
        latest = self._latest_decisions(decisions)

        proposal_status_rows: list[dict[str, Any]] = []
        run_warnings: set[str] = set()
        for proposal in proposals:
            proposal_id = proposal["proposal_id"]
            decision = latest.get(proposal_id, {"decision": ReviewDecisionType.UNDECIDED.value})
            match_outcome = match_by_pdf.get(proposal.get("pdf_id"), "unmatched")
            warnings = self._proposal_warnings(
                proposal,
                evidence_by_proposal.get(proposal_id, []),
                match_outcome,
            )
            run_warnings.update(warnings)
            proposal_status_rows.append(
                {
                    "proposal_id": proposal_id,
                    "pdf_id": proposal.get("pdf_id"),
                    "row_id": proposal.get("row_id"),
                    "column_name": proposal.get("column_name"),
                    "cell_id": proposal.get("cell_id"),
                    "match_outcome": match_outcome,
                    "proposal_state": proposal.get("proposal_state"),
                    "support_label": proposal.get("support_label"),
                    "warning_categories": warnings,
                    "review_decision": decision.get("decision", ReviewDecisionType.UNDECIDED.value),
                    "review_decision_id": decision.get("decision_id"),
                }
            )

        if run_json.get("verify_mode") and not any(
            item.get("decision") in {ReviewDecisionType.ACCEPT.value, ReviewDecisionType.ACCEPT_EDITED.value}
            for item in latest.values()
        ):
            run_warnings.add(WarningCategory.NO_REVIEWED_VERIFIED_CELLS.value)
        if run_warnings:
            run_warnings.add(WarningCategory.COMPLETED_WITH_WARNINGS.value)

        payload = {
            "run_id": run_json["run_id"],
            "proposal_status": proposal_status_rows,
            "run_warning_categories": sorted(run_warnings),
        }
        self.store.write_json(run_dir / "review" / "status_index.json", payload)
        self.store.write_json(
            run_dir / "exports" / "export_candidates.json",
            {
                "run_id": run_json["run_id"],
                "candidate_proposal_ids": [
                    item["proposal_id"]
                    for item in proposal_status_rows
                    if item["review_decision"] in {ReviewDecisionType.ACCEPT.value, ReviewDecisionType.ACCEPT_EDITED.value}
                ],
            },
        )
        return payload

    def add_run_warnings(self, run_dir: Path, warnings: list[str]) -> dict[str, Any]:
        status_index = self.store.read_json(run_dir / "review" / "status_index.json")
        merged = set(status_index.get("run_warning_categories", []))
        merged.update(warnings)
        if merged:
            merged.add(WarningCategory.COMPLETED_WITH_WARNINGS.value)
        status_index["run_warning_categories"] = sorted(merged)
        self.store.write_json(run_dir / "review" / "status_index.json", status_index)
        return status_index

    def list_proposals(self, run_dir: Path, filters: dict[str, Any]) -> dict[str, Any]:
        proposals = self.store.read_jsonl(run_dir / "proposals" / "proposals.jsonl")
        status_index = self.store.read_json(run_dir / "review" / "status_index.json")
        status_by_id = {item["proposal_id"]: item for item in status_index.get("proposal_status", [])}

        rows: list[dict[str, Any]] = []
        for proposal in proposals:
            status = status_by_id.get(proposal["proposal_id"], {})
            record = {**proposal, **status}
            warnings = set(record.get("warning_categories", []))

            if filters.get("row_id") and record.get("row_id") != filters["row_id"]:
                continue
            if filters.get("column_name") and record.get("column_name") != filters["column_name"]:
                continue
            if filters.get("pdf_id") and record.get("pdf_id") != filters["pdf_id"]:
                continue
            if filters.get("match_status") and record.get("match_outcome") != filters["match_status"]:
                continue
            if filters.get("review_decision") and record.get("review_decision") != filters["review_decision"]:
                continue
            evidence_status = filters.get("evidence_status")
            if evidence_status == "weak" and WarningCategory.WEAK_EVIDENCE.value not in warnings:
                continue
            if evidence_status == "strong" and WarningCategory.WEAK_EVIDENCE.value in warnings:
                continue
            figure_derived = filters.get("figure_derived")
            if figure_derived is True and WarningCategory.FIGURE_DERIVED.value not in warnings:
                continue
            if figure_derived is False and WarningCategory.FIGURE_DERIVED.value in warnings:
                continue
            rows.append(record)

        counters = {
            "total": len(proposals),
            "visible": len(rows),
            "undecided_visible": sum(1 for item in rows if item.get("review_decision") == ReviewDecisionType.UNDECIDED.value),
            "accepted_as_is": sum(1 for item in status_by_id.values() if item.get("review_decision") == ReviewDecisionType.ACCEPT.value),
            "accepted_with_edit": sum(1 for item in status_by_id.values() if item.get("review_decision") == ReviewDecisionType.ACCEPT_EDITED.value),
            "rejected": sum(1 for item in status_by_id.values() if item.get("review_decision") == ReviewDecisionType.REJECT.value),
        }
        counters["reviewed"] = counters["accepted_as_is"] + counters["accepted_with_edit"] + counters["rejected"]
        counters["pending"] = max(counters["total"] - counters["reviewed"], 0)

        return {
            "items": rows,
            "counters": counters,
            "run_warning_categories": status_index.get("run_warning_categories", []),
        }

    def proposal_detail(self, run_dir: Path, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.find_by_id(run_dir, "proposals/proposals.jsonl", "proposal_id", proposal_id)
        if proposal is None:
            raise FileNotFoundError("proposal_not_found")

        status_index = self.store.read_json(run_dir / "review" / "status_index.json")
        status = next((item for item in status_index.get("proposal_status", []) if item.get("proposal_id") == proposal_id), None)

        evidence = [item for item in self.store.read_jsonl(run_dir / "evidence" / "evidence.jsonl") if item.get("proposal_id") == proposal_id]
        config = self.store.read_json(run_dir / "config.snapshot.json")
        table_path = Path(config["paths"]["table_path"])
        schema_path = Path(config["paths"].get("schema_path") or table_path)

        table_df = pd.read_excel(table_path) if table_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(table_path)
        schema_df = pd.read_excel(schema_path, sheet_name="schema") if config["paths"].get("schema_path") is None else (pd.read_excel(schema_path) if schema_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(schema_path))

        row_context: dict[str, Any] = {}
        row_id = proposal.get("row_id", "")
        if row_id.startswith("row_"):
            row_idx = int(row_id.split("_", 1)[1])
            if 0 <= row_idx < len(table_df):
                row_context = {
                    "row_index": row_idx,
                    "row_values": table_df.iloc[row_idx].to_dict(),
                    "current_cell_value": table_df.iloc[row_idx].get(proposal.get("column_name")),
                }

        schema_rows = schema_df[schema_df["column_name"].astype(str) == str(proposal.get("column_name"))]
        column_definition = schema_rows.iloc[0].to_dict() if not schema_rows.empty else {"column_name": proposal.get("column_name")}

        return {
            "proposal": proposal,
            "row_context": row_context,
            "column_definition": column_definition,
            "proposal_state": proposal.get("proposal_state"),
            "support_label": proposal.get("support_label"),
            "rationale": proposal.get("rationale"),
            "calculation": proposal.get("calculation"),
            "primary_evidence": next((item for item in evidence if item.get("evidence_id") == proposal.get("primary_evidence_id")), None),
            "secondary_evidence": [item for item in evidence if item.get("evidence_id") != proposal.get("primary_evidence_id")],
            "warning_status_flags": (status or {}).get("warning_categories", []),
        }

    def record_decision(
        self,
        run_dir: Path,
        proposal_id: str,
        decision: ReviewDecisionType,
        *,
        edited_value: str | None,
        reviewer_note: str | None,
    ) -> dict[str, Any]:
        proposal = self.store.find_by_id(run_dir, "proposals/proposals.jsonl", "proposal_id", proposal_id)
        if proposal is None:
            raise FileNotFoundError("proposal_not_found")

        run_data = self.store.read_json(run_dir / "run.json")
        previous = self._latest_decisions(self.store.read_jsonl(run_dir / "review" / "decisions.jsonl")).get(proposal_id)
        decided_at = self._now()
        payload = {
            "decision_id": new_review_decision_id(run_data["run_id"], proposal_id, decided_at),
            "run_id": run_data["run_id"],
            "proposal_id": proposal_id,
            "cell_id": proposal.get("cell_id"),
            "decision": decision.value,
            "edited_value": edited_value,
            "reviewer_note": reviewer_note,
            "decided_at": decided_at,
        }
        self.store.append_jsonl(run_dir / "review" / "decisions.jsonl", payload)
        self.store.append_jsonl(
            run_dir / "review" / "decision_history.jsonl",
            {
                "proposal_id": proposal_id,
                "recorded_at": decided_at,
                "previous_decision": previous,
                "proposal_snapshot": proposal,
                "new_decision": payload,
            },
        )
        self.refresh_review_index(run_dir)
        self.store.recompute_summaries(run_dir)
        return payload

    def bulk_accept_visible(self, run_dir: Path, filters: dict[str, Any]) -> dict[str, Any]:
        visible = self.list_proposals(run_dir, filters)["items"]
        undecided = [item for item in visible if item.get("review_decision") == ReviewDecisionType.UNDECIDED.value]
        changed: list[str] = []
        for item in undecided:
            decision = self.record_decision(
                run_dir,
                item["proposal_id"],
                ReviewDecisionType.ACCEPT,
                edited_value=None,
                reviewer_note="bulk_accept_visible_subset",
            )
            changed.append(decision["decision_id"])
        return {
            "updated": len(changed),
            "decision_ids": changed,
            "visible_count": len(visible),
            "undecided_visible": len(undecided),
        }
