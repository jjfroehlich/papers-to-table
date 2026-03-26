from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .schemas import (
    ProposalRecord,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewerSummary,
    SummaryCounts,
    WarningStatusCategory,
)


BUNDLE_DIRS = [
    "inputs",
    "style_profiles",
    "parsed",
    "matching",
    "retrieval",
    "proposals",
    "evidence",
    "review",
    "summaries",
    "exports",
    "logs",
]


class RunArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def create(cls, output_dir: Path, run_id: str) -> "RunArtifacts":
        run_root = output_dir / run_id
        run_root.mkdir(parents=True, exist_ok=False)
        for directory in BUNDLE_DIRS:
            (run_root / directory).mkdir(parents=True, exist_ok=True)
        return cls(run_root)

    def path(self, relative_path: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative_path: str, payload: Any) -> Path:
        destination = self.path(relative_path)
        atomic_write_json(destination, payload)
        return destination

    def read_json(self, relative_path: str) -> Any:
        with self.path(relative_path).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def append_jsonl(self, relative_path: str, record: dict[str, Any]) -> Path:
        destination = self.path(relative_path)
        line = json.dumps(record, ensure_ascii=False)
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return destination

    def read_jsonl(self, relative_path: str) -> list[dict[str, Any]]:
        source = self.path(relative_path)
        if not source.exists():
            return []
        rows: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if raw:
                    rows.append(json.loads(raw))
        return rows

    def find_by_id(self, relative_path: str, id_field: str, value: str) -> dict[str, Any] | None:
        for item in self.read_jsonl(relative_path):
            if item.get(id_field) == value:
                return item
        return None

    def find_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        return self.find_by_id("proposals/proposals.jsonl", "proposal_id", proposal_id)

    def find_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        return self.find_by_id("evidence/evidence.jsonl", "evidence_id", evidence_id)

    def find_review_decision(self, decision_id: str) -> dict[str, Any] | None:
        return self.find_by_id("review/decisions.jsonl", "decision_id", decision_id)

    def recompute_summaries(self, run_id: str, verify_mode: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:  # noqa: C901
        proposal_rows = self.read_jsonl("proposals/proposals.jsonl")
        decision_rows = self.read_jsonl("review/decisions.jsonl")

        # Load matching summary if available
        matching_summary: dict[str, Any] = {}
        try:
            matching_summary = self.read_json("matching/matching_summary.json")
        except (FileNotFoundError, KeyError):
            pass

        # Load config snapshot for provider/run info
        snapshot: dict[str, Any] = {}
        try:
            snapshot = self.read_json("config.snapshot.json")
        except (FileNotFoundError, KeyError):
            pass

        # Load input summary for paths / verify_mode
        input_summary: dict[str, Any] = {}
        try:
            input_summary = self.read_json("inputs/input_summary.json")
        except (FileNotFoundError, KeyError):
            pass

        effective_verify_mode = input_summary.get("verify_mode", snapshot.get("verify_mode", verify_mode))

        proposals: list[ProposalRecord] = []
        decisions: list[ReviewDecisionRecord] = []
        for row in proposal_rows:
            try:
                proposals.append(ProposalRecord.model_validate(row))
            except Exception:
                continue
        for row in decision_rows:
            try:
                decisions.append(ReviewDecisionRecord.model_validate(row))
            except Exception:
                continue

        latest_by_proposal: dict[str, ReviewDecisionRecord] = {}
        for decision in decisions:
            current = latest_by_proposal.get(decision.proposal_id)
            if current is None or decision.decided_at >= current.decided_at:
                latest_by_proposal[decision.proposal_id] = decision

        reviewed = 0
        accepted = 0
        accepted_with_edit = 0
        rejected = 0
        for proposal in proposals:
            decision = latest_by_proposal.get(proposal.proposal_id)
            if decision is None or decision.decision == ReviewDecision.UNDECIDED:
                continue
            reviewed += 1
            if decision.decision == ReviewDecision.ACCEPT:
                accepted += 1
            elif decision.decision == ReviewDecision.ACCEPT_WITH_EDIT:
                accepted_with_edit += 1
            elif decision.decision == ReviewDecision.REJECT:
                rejected += 1

        counts = SummaryCounts(
            proposals_generated=len(proposals),
            reviewed_proposals=reviewed,
            accepted_as_is=accepted,
            accepted_with_edit=accepted_with_edit,
            rejected=rejected,
            pending=max(len(proposals) - reviewed, 0),
            changed_cells_exported=0,
        )
        reviewer_summary = ReviewerSummary(run_id=run_id, counts=counts, verify_mode=effective_verify_mode)

        # Compute run-level status flags
        run_status_flags: list[str] = []
        if matching_summary.get("ambiguous", 0) > 0:
            run_status_flags.append(WarningStatusCategory.AMBIGUOUS_MATCH)
        if matching_summary.get("duplicate_row_conflict", 0) > 0:
            run_status_flags.append(WarningStatusCategory.DUPLICATE_ROW_CONFLICT)
        if proposals and accepted == 0 and accepted_with_edit == 0:
            run_status_flags.append(WarningStatusCategory.NO_REVIEWED_VERIFIED_CELLS)

        provider = snapshot.get("provider", {})
        provider_name = provider.get("provider_name") or provider.get("name")
        model_name = provider.get("model_name") or provider.get("model")
        provider_locality = provider.get("locality", "local")

        run_summary_payload: dict[str, Any] = {
            "run_id": run_id,
            "status": "completed_with_warnings",
            "operator_status": "completed with warnings",
            "message": "Summary recomputed from artifact files.",
            "progress": {"stage": "summary_recompute", "item": "artifacts"},
            "config_path": snapshot.get("paths", {}).get("config_path", ""),
            "artifact_dir": str(self.root),
            "verify_mode": effective_verify_mode,
            "table_path": input_summary.get("table_path"),
            "schema_path": input_summary.get("schema_path"),
            "pdf_dir": input_summary.get("pdf_dir"),
            "output_dir": input_summary.get("output_dir"),
            "target_columns": input_summary.get("target_columns", []),
            "provider_name": provider_name,
            "model_name": model_name,
            "provider_locality": provider_locality,
            "counts": counts.model_dump(mode="json"),
            "pdfs_processed": matching_summary.get("total", 0),
            "pdfs_matched": matching_summary.get("matched", 0),
            "pdfs_unmatched": matching_summary.get("unmatched", 0),
            "pdfs_ambiguous": matching_summary.get("ambiguous", 0),
            "run_status_flags": run_status_flags,
        }

        reviewer_payload = reviewer_summary.model_dump(mode="json")
        reviewer_payload["provider_name"] = provider_name
        reviewer_payload["model_name"] = model_name
        reviewer_payload["provider_locality"] = provider_locality
        reviewer_payload["pdfs_matched"] = matching_summary.get("matched", 0)
        reviewer_payload["pdfs_unmatched"] = matching_summary.get("unmatched", 0)
        reviewer_payload["pdfs_ambiguous"] = matching_summary.get("ambiguous", 0)

        self.write_json("summaries/run_summary.json", run_summary_payload)
        self.write_json("summaries/reviewer_summary.json", reviewer_payload)
        return run_summary_payload, reviewer_payload


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
