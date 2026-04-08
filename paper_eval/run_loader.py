from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from paper_eval.contracts import EvidenceItem, LoadedRun, ProposalRecord, RunMetadata
from paper_eval.errors import CliUsageError, ContractError

_REQUIRED_RUN_FILES = ("run.json", "proposals/proposals.jsonl")
_OPTIONAL_RUN_FILES = ("config.snapshot.json", "inputs/input_summary.json", "summaries/run_summary.json")
_SIDE_CAR_EVIDENCE_FILES = ("evidence/evidence.jsonl", "evidence/evidence.json", "support/evidence.jsonl")
_PAGE_TEXT_FILES = (
    "evidence/page_text.json",
    "evidence/page_texts.json",
    "evidence/pages.json",
    "support/page_text.json",
    "support/page_texts.json",
    "support/pages.json",
)
_EVAL_MODE = "eval"
_EVAL_PROVENANCE_TEXT_FIELDS = {
    "gold_source_ref": (
        ("gold_source_ref",),
        ("gold_table_source_reference",),
        ("gold_table_source_ref",),
        ("eval", "gold_source_ref"),
        ("eval", "gold_table_source_ref"),
        ("provenance", "gold_source_ref"),
        ("provenance", "gold_table_source_ref"),
        ("eval_artifacts", "gold_table", "source_reference"),
    ),
    "gold_table_hash": (
        ("gold_table_hash",),
        ("gold_table_content_hash",),
        ("gold_content_hash",),
        ("eval", "gold_table_hash"),
        ("eval", "gold_table_content_hash"),
        ("provenance", "gold_table_hash"),
        ("provenance", "gold_table_content_hash"),
        ("eval_artifacts", "gold_table", "content_hash"),
    ),
    "gold_table_snapshot_path": (
        ("gold_table_snapshot_path",),
        ("gold_snapshot_path",),
        ("eval", "gold_table_snapshot_path"),
        ("eval", "gold_snapshot_path"),
        ("provenance", "gold_table_snapshot_path"),
        ("provenance", "gold_snapshot_path"),
        ("eval_artifacts", "gold_table", "snapshot_path"),
    ),
    "masked_table_hash": (
        ("masked_table_hash",),
        ("masked_working_table_hash",),
        ("masked_table_content_hash",),
        ("eval", "masked_table_hash"),
        ("eval", "masked_working_table_hash"),
        ("provenance", "masked_table_hash"),
        ("provenance", "masked_working_table_hash"),
        ("eval_artifacts", "masked_working_table", "content_hash"),
    ),
    "masked_table_snapshot_path": (
        ("masked_table_snapshot_path",),
        ("masked_working_table_path",),
        ("masked_working_table_snapshot_path",),
        ("masked_snapshot_path",),
        ("eval", "masked_table_snapshot_path"),
        ("eval", "masked_working_table_path"),
        ("eval", "masked_working_table_snapshot_path"),
        ("provenance", "masked_table_snapshot_path"),
        ("provenance", "masked_working_table_path"),
        ("provenance", "masked_working_table_snapshot_path"),
        ("eval_artifacts", "masked_working_table", "path"),
    ),
}
_REQUIRED_EVAL_PROVENANCE_FIELDS = (
    "gold_table_hash",
    "gold_table_snapshot_path",
    "masked_table_hash",
    "masked_table_snapshot_path",
)


def _normalize_optional_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value)


def _normalize_optional_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return dict(value)


def discover_run_directories(run_paths: list[Path], runs_root: Path | None) -> list[Path]:
    if run_paths and runs_root is not None:
        raise CliUsageError("Use either repeated --run values or --runs-root, not both.")
    if not run_paths and runs_root is None:
        raise CliUsageError("Provide at least one --run or --runs-root.")

    if run_paths:
        resolved = [path.resolve() for path in run_paths]
        missing = [str(path) for path in resolved if not path.exists()]
        if missing:
            raise CliUsageError(f"Run path does not exist: {', '.join(missing)}")
        not_directories = [str(path) for path in resolved if not path.is_dir()]
        if not_directories:
            raise CliUsageError(f"Run path is not a directory: {', '.join(not_directories)}")
    else:
        if not runs_root.exists():
            raise CliUsageError(f"Runs root does not exist: {runs_root}")
        if not runs_root.is_dir():
            raise CliUsageError(f"Runs root is not a directory: {runs_root}")
        resolved = sorted(
            path.resolve()
            for path in runs_root.iterdir()
            if path.is_dir() and (path / "proposals" / "proposals.jsonl").exists()
        )

    if not resolved:
        raise CliUsageError("No run directories matched the provided inputs.")
    return resolved


def load_run(run_dir: Path) -> LoadedRun:
    if not run_dir.exists():
        raise ContractError(f"Run bundle directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ContractError(f"Run bundle path is not a directory: {run_dir}")
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
    page_text_by_page = _load_page_text_by_page(run_dir, sidecar_evidence)

    metadata = _build_run_metadata(
        run_dir=run_dir,
        run_payload=run_payload,
        config_payload=config_payload,
        input_summary_payload=input_summary_payload,
        run_summary_payload=run_summary_payload,
    )
    _validate_eval_mode_provenance(
        metadata=metadata,
        run_dir=run_dir,
    )
    proposals = _load_proposals(run_dir, metadata.run_id, sidecar_evidence)
    return LoadedRun(
        run_dir=run_dir,
        metadata=metadata,
        proposals=proposals,
        page_text_by_page=page_text_by_page,
        contract_warnings=warnings,
    )


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
            try:
                payload = json.loads(line)
            except JSONDecodeError as exc:
                raise ContractError(
                    f"Invalid JSON in {proposal_path} line {line_number}: {exc.msg}"
                ) from exc
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
                    allowed_values=_normalize_optional_list(payload.get("allowed_values")),
                    numeric_value_form=_required_text(payload.get("numeric_value_form")),
                    scoring_policy=_required_text(payload.get("scoring_policy")),
                    aliases=_normalize_optional_dict(payload.get("aliases")),
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
    eval_provenance = {
        field_name: _first_present(
            run_payload,
            config_payload,
            input_summary_payload,
            run_summary_payload,
            keys=key_paths,
        )
        for field_name, key_paths in _EVAL_PROVENANCE_TEXT_FIELDS.items()
    }
    return RunMetadata(
        run_id=run_id,
        run_dir=run_dir,
        run_mode=_first_present(
            run_payload,
            config_payload,
            keys=(("run_mode",), ("mode",)),
        ),
        provider_token=_first_present(
            run_payload,
            config_payload,
            keys=(("provider_token",), ("provider", "token")),
        ),
        text_model_id=_first_present(
            run_payload,
            config_payload,
            keys=(
                ("provider_text_model_id",),
                ("text_model_id",),
                ("model_id",),
                ("provider", "text_model_id"),
                ("provider", "model_id"),
                ("model", "id"),
            ),
        ),
        vision_model_id=_first_present(
            run_payload,
            config_payload,
            keys=(
                ("provider_vision_model_id",),
                ("vision_model_id",),
                ("provider", "vision_model_id"),
                ("vision_model", "id"),
            ),
        ),
        parser_identity=_first_present(
            run_payload,
            config_payload,
            keys=(("parser_identity",), ("parser", "identity"), ("parser", "name")),
        ),
        parser_version=_first_present(
            run_payload,
            config_payload,
            keys=(("parser_version",), ("parser", "version")),
        ),
        prompt_version=_first_present(
            run_payload,
            config_payload,
            keys=(("prompt_version",), ("prompt", "version"), ("prompt", "id")),
        ),
        prompt_hash=_first_present(
            run_payload,
            config_payload,
            keys=(("prompt_hash",), ("prompt", "hash")),
        ),
        schema_hash=_first_present(
            run_payload,
            config_payload,
            keys=(("schema_hash",), ("schema", "hash")),
        ),
        schema_version=_first_present(
            run_payload,
            config_payload,
            keys=(("schema_version",), ("schema", "version")),
        ),
        config_hash=_first_present(
            run_payload,
            config_payload,
            keys=(("config_hash",), ("config", "hash")),
        ),
        page_count=_first_present_int(
            run_payload,
            config_payload,
            input_summary_payload,
            run_summary_payload,
            keys=(("page_count",), ("total_pages",), ("num_pages",), ("document", "page_count")),
        ),
        gold_source_ref=eval_provenance["gold_source_ref"],
        gold_table_hash=eval_provenance["gold_table_hash"],
        gold_table_snapshot_path=eval_provenance["gold_table_snapshot_path"],
        masked_table_hash=eval_provenance["masked_table_hash"],
        masked_table_snapshot_path=eval_provenance["masked_table_snapshot_path"],
        extras={
            "run": run_payload,
            "config_snapshot": config_payload,
            "input_summary": input_summary_payload,
            "run_summary": run_summary_payload,
        },
    )


def _validate_eval_mode_provenance(*, metadata: RunMetadata, run_dir: Path) -> None:
    if _normalize_run_mode(metadata.run_mode) != _EVAL_MODE:
        return

    missing_fields = [
        field_name
        for field_name in _REQUIRED_EVAL_PROVENANCE_FIELDS
        if not _required_text(getattr(metadata, field_name))
    ]
    if missing_fields:
        raise ContractError(
            "Eval-mode run bundles must publish provenance fields for reproducibility. "
            f"Missing fields for run '{metadata.run_id}': {', '.join(missing_fields)}."
        )

    for field_name in ("gold_table_snapshot_path", "masked_table_snapshot_path"):
        path_text = _required_text(getattr(metadata, field_name))
        if path_text is None:
            continue
        path = Path(path_text)
        if not path.is_absolute():
            path = run_dir / path
        if not path.exists():
            raise ContractError(
                f"Eval-mode run '{metadata.run_id}' references missing provenance artifact "
                f"'{field_name}': {path_text}"
            )


def _first_present(*payloads: dict[str, Any], keys: tuple[tuple[str, ...], ...]) -> str | None:
    for payload in payloads:
        for key_path in keys:
            value = _required_text(_lookup(payload, key_path))
            if value:
                return value
    return None


def _first_present_int(*payloads: dict[str, Any], keys: tuple[tuple[str, ...], ...]) -> int | None:
    for payload in payloads:
        for key_path in keys:
            value = _lookup(payload, key_path)
            if value is None or value == "":
                continue
            return int(value)
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise ContractError(f"Invalid JSON in {path}: {exc.msg}") from exc


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
                    try:
                        payload = json.loads(line)
                    except JSONDecodeError as exc:
                        raise ContractError(f"Invalid JSON in {path}: {exc.msg}") from exc
                    evidence_id = _required_text(payload.get("evidence_id") or payload.get("id"))
                    if evidence_id:
                        evidence_by_id[evidence_id] = payload
            return evidence_by_id
    return {}


def _load_page_text_by_page(
    run_dir: Path,
    sidecar_evidence: dict[str, dict[str, Any]],
) -> dict[int, str]:
    for payload in sidecar_evidence.values():
        page = _optional_int(payload.get("page"))
        text = _required_text(payload.get("page_text") or payload.get("page_content") or payload.get("source_text"))
        if page is not None and text:
            page_text_by_page = {page: text}
            for evidence_payload in sidecar_evidence.values():
                evidence_page = _optional_int(evidence_payload.get("page"))
                evidence_text = _required_text(
                    evidence_payload.get("page_text")
                    or evidence_payload.get("page_content")
                    or evidence_payload.get("source_text")
                )
                if evidence_page is not None and evidence_text:
                    page_text_by_page[evidence_page] = evidence_text
            return page_text_by_page

    for relative_path in _PAGE_TEXT_FILES:
        path = run_dir / relative_path
        if not path.exists():
            continue
        if path.suffix == ".json":
            payload = _load_json(path)
            return _page_text_mapping_from_payload(payload)
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


def _page_text_mapping_from_payload(payload: Any) -> dict[int, str]:
    if isinstance(payload, dict):
        if all(_optional_int(key) is not None for key in payload.keys()):
            return {
                int(key): text
                for key, value in payload.items()
                if (text := _required_text(value)) is not None
            }
        if isinstance(payload.get("pages"), list):
            return _page_text_mapping_from_payload(payload["pages"])
    if isinstance(payload, list):
        mapping: dict[int, str] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            page = _optional_int(item.get("page") or item.get("page_number"))
            text = _required_text(item.get("text") or item.get("page_text") or item.get("content"))
            if page is not None and text:
                mapping[page] = text
        return mapping
    return {}


def _lookup(payload: dict[str, Any], key_path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in key_path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _required_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _normalize_run_mode(value: Any) -> str:
    return _required_text(value).casefold() if _required_text(value) else ""
