from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[5] / "specs" / "contracts" / "schemas"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path} line {i}: {exc.msg}") from exc
    return rows


def _validate(schema_name: str, payload: Any, label: str, errors: list[str]) -> None:
    schema = _load_json(SCHEMA_DIR / schema_name)
    validator = Draft202012Validator(schema)
    for err in validator.iter_errors(payload):
        loc = ".".join(str(x) for x in err.path) or "$"
        errors.append(f"{label}: schema violation at {loc}: {err.message}")


def verify_run_bundle(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = ["run.json", "proposals/proposals.jsonl", "review/decisions.jsonl", "summaries/run_summary.json"]
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"Missing required artifact: {rel}")

    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    run = _load_json(run_dir / "run.json")
    _validate("run.schema.json", run, "run.json", errors)

    proposals = _load_jsonl(run_dir / "proposals" / "proposals.jsonl")
    for idx,rec in enumerate(proposals, start=1):
        _validate("proposals.schema.json", rec, f"proposals/proposals.jsonl#{idx}", errors)

    evidence_path = run_dir / "evidence" / "evidence.jsonl"
    evidence = _load_jsonl(evidence_path) if evidence_path.exists() else []
    for idx,rec in enumerate(evidence, start=1):
        _validate("evidence.schema.json", rec, f"evidence/evidence.jsonl#{idx}", errors)

    decisions = _load_jsonl(run_dir / "review" / "decisions.jsonl")
    for idx,rec in enumerate(decisions, start=1):
        _validate("decisions.schema.json", rec, f"review/decisions.jsonl#{idx}", errors)

    run_summary = _load_json(run_dir / "summaries" / "run_summary.json")
    _validate("run_summary.schema.json", run_summary, "summaries/run_summary.json", errors)

    proposal_ids = {p.get("proposal_id") for p in proposals if p.get("proposal_id")}
    evidence_ids = {e.get("evidence_id") for e in evidence if e.get("evidence_id")}
    for p in proposals:
        for evid in p.get("evidence_ids", []) or []:
            if evid not in evidence_ids:
                errors.append(f"proposal {p.get('proposal_id')} references missing evidence_id {evid}")
    accepted = {"accepted", "accepted_with_edit"}
    accepted_proposal_ids = set()
    for d in decisions:
        pid = d.get("proposal_id")
        if pid not in proposal_ids:
            errors.append(f"decision {d.get('review_decision_id')} references missing proposal_id {pid}")
        if d.get("decision") in accepted:
            accepted_proposal_ids.add(pid)

    audit_files = sorted((run_dir / "exports").glob("audit_log_*.json")) if (run_dir / "exports").exists() else []
    for af in audit_files:
        payload = _load_json(af)
        rows = payload if isinstance(payload,list) else payload.get("entries",[])
        if isinstance(rows,list):
            for i,row in enumerate(rows,start=1):
                _validate("audit_log.schema.json", row, f"{af.name}#{i}", errors)
                pid = row.get("proposal_id")
                if pid and pid not in accepted_proposal_ids:
                    errors.append(f"{af.name} has exported proposal_id {pid} without accepted/accepted_with_edit decision")
        else:
            errors.append(f"{af.name}: expected list or object with entries list")

    return {"ok": len(errors)==0, "errors": errors, "warnings": warnings, "counts": {"proposals": len(proposals), "evidence": len(evidence), "decisions": len(decisions), "audit_logs": len(audit_files)}}
