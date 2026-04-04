from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper_eval.contracts import EvidenceItem, LoadedRun, ProposalRecord, RunMetadata
from paper_eval.errors import CliUsageError, ContractError

_REQUIRED_RUN_FILES = ("run.json", "proposals/proposals.jsonl")
_OPTIONAL_RUN_FILES = ("config.snapshot.json", "inputs/input_summary.json", "summaries/run_summary.json")
_SIDE_CAR_EVIDENCE_FILES = ("evidence/evidence.jsonl", "evidence/evidence.json", "support/evidence.jsonl")


def discover_run_directories(run_paths: list[Path], runs_root: Path | None) -> list[Path]:
    if run_paths and runs_root is not None:
        raise CliUsageError("Use either repeated --run values or --runs-root, not both.")
    if not run_paths and runs_root is None:
        raise CliUsageError("Provide at least one --run or --runs-root.")

    if run_paths:
        resolved = [path.resolve() for path in run_paths]
    else:
        resolved = sorted(
            path.resolve()
            for path in runs_root.iterdir()
            if path.is_dir() and (path / "proposals" / "proposals.jsonl").exists()
        )

    if not resolved:
        raise CliUsageError("No run directories matched the provided inputs.")
    return resolved


def load_run(run_dir: Path) -> LoadedRun:
    missing_files = [relative_path for relative_path in _REQUIRED_RUN_FILES if not (run_dir / relative_path).exists()]
    if missing_files:
        raise ContractError(
            f"Run bundle '{run_dir}' is missing required artifact files: {', '.join(missing_files)}"
        )

    warnings = [
        f"Optional artifact file not found: {relative_path}"
        for relative_path in _OPTIONAL_RUN_FILES
        if not (run_dir / relative_path).exists()
    ]

    run_payload = _load_json(run_dir / "run.json")
    config_payload = _load_optional_json(run_dir / "config.snapshot.json")
    input_summary_payload = _load_optional_json(run_dir / "inputs" / "input_summary.json")
    run_summary_payload = _load_optional_json(run_dir / "summaries" / "run_summary.json")
    sidecar_evidence = _load_sidecar_evidence(run_dir)

    metadata = _build_run_metadata(
        run_dir=run_dir,
        run_payload=run_payload,
        config_payload=config_payload,
        input_summary_payload=input_summary_payload,
        run_summary_payload=run_summary_payload,
    )
    proposals = _load_proposals(run_dir, metadata.run_id, sidecar_evidence)
    return LoadedRun(run_dir=run_dir, metadata=metadata, proposals=proposals, contract_warnings=warnings)


def _load_proposals(
    run_dir: Path,
    default_run_id: str,
    sidecar_evidence: dict[str, dict[str, Any]],
) -> list[ProposalRecord]:
    proposal_path = run_dir / "proposals" / "proposals.jsonl"
    proposals: list[ProposalRecord] = []
    with proposal_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            missing_fields = [
                field_name
                for field_name in ("row_id", "column_name", "cell_id")
                if not _required_text(payload.get(field_name))
            ]
            if missing_fields:
                raise ContractError(
                    "Proposal record is missing required stable join fields "
                    f"{', '.join(missing_fields)} in {proposal_path} line {line_number}."
                )
            run_id = _required_text(payload.get("run_id")) or default_run_id
            proposals.append(
                ProposalRecord(
                    run_id=run_id,
                    row_id=_required_text(payload.get("row_id")),
                    column_name=_required_text(payload.get("column_name")),
                    cell_id=_required_text(payload.get("cell_id")),
                    proposed_value=payload.get("proposed_value"),
                    pdf_id=_required_text(payload.get("pdf_id")),
                    state=_required_text(payload.get("state")),
                    support=payload.get("support"),
                    field_type=_required_text(payload.get("field_type")),
                    allowed_values=list(payload.get("allowed_values", [])),
                    numeric_value_form=_required_text(payload.get("numeric_value_form")),
                    scoring_policy=_required_text(payload.get("scoring_policy")),
                    aliases=dict(payload.get("aliases", {})),
                    evidence_items=_extract_evidence_items(payload, sidecar_evidence),
                    row_index=_optional_int(payload.get("row_index")),
                    raw=payload,
                )
            )
    return proposals


def _build_run_metadata(
    *,
    run_dir: Path,
    run_payload: dict[str, Any],
    config_payload: dict[str, Any],
    input_summary_payload: dict[str, Any],
    run_summary_payload: dict[str, Any],
) -> RunMetadata:
    run_id = (
        _required_text(run_payload.get("run_id"))
        or _required_text(run_summary_payload.get("run_id"))
        or run_dir.name
    )
    return RunMetadata(
        run_id=run_id,
        run_dir=run_dir,
        run_mode=_first_present(run_payload, config_payload, keys=("run_mode", "mode")),
        provider_token=_first_present(run_payload, config_payload, keys=("provider_token",)),
        text_model_id=_first_present(
            run_payload,
            config_payload,
            keys=("provider_text_model_id", "text_model_id", "model_id"),
        ),
        vision_model_id=_first_present(
            run_payload,
            config_payload,
            keys=("provider_vision_model_id", "vision_model_id"),
        ),
        parser_identity=_first_present(run_payload, config_payload, keys=("parser_identity",)),
        parser_version=_first_present(run_payload, config_payload, keys=("parser_version",)),
        prompt_version=_first_present(run_payload, config_payload, keys=("prompt_version",)),
        prompt_hash=_first_present(run_payload, config_payload, keys=("prompt_hash",)),
        schema_hash=_first_present(run_payload, config_payload, keys=("schema_hash",)),
        schema_version=_first_present(run_payload, config_payload, keys=("schema_version",)),
        config_hash=_first_present(run_payload, config_payload, keys=("config_hash",)),
        extras={
            "run": run_payload,
            "config_snapshot": config_payload,
            "input_summary": input_summary_payload,
            "run_summary": run_summary_payload,
        },
    )


def _first_present(*payloads: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for payload in payloads:
        for key in keys:
            value = _required_text(payload.get(key))
            if value:
                return value
    return None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _load_sidecar_evidence(run_dir: Path) -> dict[str, dict[str, Any]]:
    for relative_path in _SIDE_CAR_EVIDENCE_FILES:
        path = run_dir / relative_path
        if not path.exists():
            continue
        if path.suffix == ".json":
            payload = _load_json(path)
            if isinstance(payload, list):
                return {_required_text(item.get("evidence_id") or item.get("id")): item for item in payload}
        if path.suffix == ".jsonl":
            evidence_by_id: dict[str, dict[str, Any]] = {}
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    evidence_id = _required_text(payload.get("evidence_id") or payload.get("id"))
                    if evidence_id:
                        evidence_by_id[evidence_id] = payload
            return evidence_by_id
    return {}


def _extract_evidence_items(
    payload: dict[str, Any],
    sidecar_evidence: dict[str, dict[str, Any]],
) -> list[EvidenceItem]:
    records: list[dict[str, Any]] = []
    embedded = payload.get("evidence") or payload.get("evidence_items")
    if isinstance(embedded, list):
        records.extend(item for item in embedded if isinstance(item, dict))

    support = payload.get("support")
    if isinstance(support, list):
        records.extend(item for item in support if isinstance(item, dict))
    elif isinstance(support, dict):
        evidence_ids = support.get("evidence_ids") or support.get("support_ids") or []
        for evidence_id in evidence_ids:
            evidence_payload = sidecar_evidence.get(str(evidence_id))
            if evidence_payload:
                records.append(evidence_payload)

    evidence_items: list[EvidenceItem] = []
    for record in records:
        evidence_items.append(
            EvidenceItem(
                page=_optional_int(record.get("page")),
                quote_text=_required_text(record.get("quote_text") or record.get("quote")),
                evidence_id=_required_text(record.get("evidence_id") or record.get("id")),
                raw=record,
            )
        )
    return evidence_items


def _required_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
