from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .models import ReviewDecisionType, ReviewerSummary, RunSummary

RUN_DIRS = [
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


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create_bundle(self, run_id: str) -> Path:
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        for name in RUN_DIRS:
            (run_dir / name).mkdir(parents=True, exist_ok=True)
        return run_dir

    @staticmethod
    def atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as temp:
            temp.write(content)
            temp_path = Path(temp.name)
        os.replace(temp_path, path)

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self.atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False))

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def artifact_path(self, run_dir: Path, relative: str) -> Path:
        return run_dir / relative

    def find_by_id(self, run_dir: Path, relative_jsonl: str, id_field: str, value: str) -> dict[str, Any] | None:
        for row in self.read_jsonl(run_dir / relative_jsonl):
            if row.get(id_field) == value:
                return row
        return None

    def recompute_summaries(self, run_dir: Path) -> tuple[RunSummary, ReviewerSummary]:
        decisions = self.read_jsonl(run_dir / "review" / "decisions.jsonl")
        proposals = self.read_jsonl(run_dir / "proposals" / "proposals.jsonl")
        run_data = self.read_json(run_dir / "run.json")
        accepted = sum(1 for d in decisions if d.get("decision") == ReviewDecisionType.ACCEPT.value)
        accepted_edit = sum(1 for d in decisions if d.get("decision") == ReviewDecisionType.ACCEPT_EDITED.value)
        rejected = sum(1 for d in decisions if d.get("decision") == ReviewDecisionType.REJECT.value)
        reviewed = accepted + accepted_edit + rejected
        pending = max(len(proposals) - reviewed, 0)
        summary = RunSummary(
            run_id=run_data["run_id"],
            run_status=run_data["status"],
            provider_locality=run_data.get("provider_locality", "local"),
            provider_name=run_data.get("provider_name", "lm_studio"),
            model_name=run_data.get("model_name", "unconfigured"),
            pdfs_processed=run_data.get("pdf_count", 0),
            proposals_generated=len(proposals),
            reviewed_proposals=reviewed,
            accepted_as_is=accepted,
            accepted_with_edit=accepted_edit,
            rejected=rejected,
            pending=pending,
            changed_cells_exported=accepted + accepted_edit,
            verify_mode=run_data.get("verify_mode", False),
        )
        reviewer = ReviewerSummary(**summary.model_dump(exclude={"run_status"}))
        self.write_json(run_dir / "summaries" / "run_summary.json", summary.model_dump())
        self.write_json(run_dir / "summaries" / "reviewer_summary.json", reviewer.model_dump())
        return summary, reviewer
