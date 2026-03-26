"""
Batch 6 — T096, T097, T098, T099

Implements:
- T096: Content-only XLSX export with accepted-only changes and changed-cell highlighting.
- T097: Best-effort detection and reporting of unsupported workbook features.
- T098: Audit-log CSV generation with row/column ids, old/new values, proposal source,
        reviewer decision, and real decision timestamps.
- T099: Diagnostics JSON covering matching failures, blocked/unclear/skipped/error outcomes,
        weak evidence, unsupported feature warnings, and completed-with-warnings status.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from .schemas import ExportCandidate, ReviewDecision, WarningStatusCategory

logger = logging.getLogger(__name__)

# Yellow highlight for changed cells.
CHANGED_CELL_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")


# ---------------------------------------------------------------------------
# T097 — Unsupported-feature detection
# ---------------------------------------------------------------------------

UNSUPPORTED_FEATURE_NAMES = [
    "merged_cells",
    "formulas",
    "conditional_formatting",
    "charts",
    "named_ranges",
    "frozen_panes",
    "hidden_rows",
    "hidden_columns",
    "comments",
    "macros",
]


def detect_unsupported_features(source_path: Path) -> list[str]:
    """
    T097: Inspect the source XLSX workbook for unsupported advanced features.

    Returns a list of human-readable warning strings for any features found.
    Detection is best-effort; missing any particular feature does not imply the
    feature is absent from the workbook.
    """
    warnings: list[str] = []

    # Macros (.xlsm extension)
    if source_path.suffix.lower() == ".xlsm":
        warnings.append("macros: source workbook is macro-enabled (.xlsm); macros will not be preserved")

    try:
        wb = load_workbook(source_path, data_only=False, keep_links=False)
    except Exception as exc:
        logger.warning("Could not open workbook for feature inspection: %s", exc)
        return warnings

    for ws in wb.worksheets:
        sheet_name = ws.title

        # Merged cells
        if ws.merged_cells.ranges:
            warnings.append(
                f"merged_cells: sheet '{sheet_name}' contains merged cells; "
                "merged cell structure will not be preserved"
            )

        # Formulas (scan all cells)
        formula_found = False
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formula_found = True
                    break
            if formula_found:
                break
        if formula_found:
            warnings.append(
                f"formulas: sheet '{sheet_name}' contains formulas; "
                "formulas will be replaced with their last-computed values (or None)"
            )

        # Conditional formatting
        if ws.conditional_formatting:
            warnings.append(
                f"conditional_formatting: sheet '{sheet_name}' has conditional formatting; "
                "it will not be preserved"
            )

        # Charts
        if ws._charts:  # noqa: SLF001
            warnings.append(
                f"charts: sheet '{sheet_name}' contains charts; "
                "charts will not be preserved"
            )

        # Comments
        if ws._comments:  # noqa: SLF001
            warnings.append(
                f"comments: sheet '{sheet_name}' contains cell comments; "
                "comments will not be preserved"
            )

        # Frozen panes
        if ws.freeze_panes:
            warnings.append(
                f"frozen_panes: sheet '{sheet_name}' has frozen panes; "
                "pane state will not be preserved"
            )

        # Hidden rows
        hidden_rows = [
            row_dim for row_dim in ws.row_dimensions.values() if row_dim.hidden
        ]
        if hidden_rows:
            warnings.append(
                f"hidden_rows: sheet '{sheet_name}' has {len(hidden_rows)} hidden row(s); "
                "hidden-row state will not be preserved"
            )

        # Hidden columns
        hidden_cols = [
            col_dim for col_dim in ws.column_dimensions.values() if col_dim.hidden
        ]
        if hidden_cols:
            warnings.append(
                f"hidden_columns: sheet '{sheet_name}' has {len(hidden_cols)} hidden column(s); "
                "hidden-column state will not be preserved"
            )

    # Named ranges
    if wb.defined_names:
        names = list(wb.defined_names)
        if names:
            warnings.append(
                f"named_ranges: workbook contains {len(names)} named range(s); "
                "named ranges will not be preserved"
            )

    return warnings


# ---------------------------------------------------------------------------
# T096 — Content-only XLSX export with changed-cell highlighting
# ---------------------------------------------------------------------------


def _build_row_lookup(table_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a {row_id → row_data} mapping from table_rows using Title as the row_id."""
    lookup: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(table_rows):
        title = row.get("Title")
        row_id = str(title) if title is not None else f"row_{idx + 1}"
        lookup[row_id] = row
    return lookup


def _build_change_index(
    candidates: list[ExportCandidate],
) -> dict[tuple[str, str], ExportCandidate]:
    """Build a {(row_id, column_name) → ExportCandidate} index."""
    return {(c.row_id, c.column_name): c for c in candidates}


def generate_xlsx_export(
    source_path: Path,
    table_rows: list[dict[str, Any]],
    candidates: list[ExportCandidate],
    output_path: Path,
) -> list[str]:
    """
    T096: Write a content-only updated workbook to output_path.

    - Reads the source workbook with data_only=True so formulas are replaced by
      their last-computed values; new cell values are plain strings/numbers/dates.
    - Applies only the explicitly accepted changes from candidates.
    - Highlights every changed cell with CHANGED_CELL_FILL (yellow).
    - Does not preserve formulas, filters, frozen panes, merged cells,
      conditional formatting, comments, named ranges, charts, shapes, or macros.

    Returns a list of unsupported-feature warning strings detected from the source
    workbook (same output as detect_unsupported_features, called here so the
    inspection and the export use the same workbook open).
    """
    feature_warnings = detect_unsupported_features(source_path)

    # Load with data_only=True so formula cells yield their last-computed value
    src_wb = load_workbook(source_path, data_only=True, keep_links=False)
    src_ws = src_wb.active

    change_index = _build_change_index(candidates)

    # Read headers from the first row
    header_row = next(src_ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header_row is None:
        header_row = ()
    headers: list[str] = [str(h) if h is not None else "" for h in header_row]
    col_index: dict[str, int] = {h: i for i, h in enumerate(headers) if h}

    # Build a row_id → row_number mapping using the Title column
    title_col_idx = col_index.get("Title")
    # row_number here is 1-based Excel row number (row 1 = header, row 2 = first data row)
    row_id_to_row_num: dict[str, int] = {}
    if title_col_idx is not None:
        for excel_row in src_ws.iter_rows(min_row=2):
            cell_val = excel_row[title_col_idx].value
            if cell_val is not None:
                row_id_to_row_num[str(cell_val)] = excel_row[0].row

    # Create a new content-only workbook
    out_wb = Workbook()
    out_ws = out_wb.active
    assert out_ws is not None
    out_ws.title = src_ws.title if src_ws.title else "Sheet1"

    # Write header row
    out_ws.append(list(header_row))

    # Track changed (row, col) pairs for highlighting
    changed_cells: set[tuple[int, int]] = set()

    # Write data rows
    for src_row in src_ws.iter_rows(min_row=2):
        # Determine row_id from Title column
        if title_col_idx is not None and title_col_idx < len(src_row):
            title_val = src_row[title_col_idx].value
            row_id = str(title_val) if title_val is not None else None
        else:
            row_id = None

        row_values: list[Any] = [cell.value for cell in src_row]

        # Apply accepted changes for this row
        if row_id is not None:
            for col_name, col_idx in col_index.items():
                key = (row_id, col_name)
                if key in change_index:
                    candidate = change_index[key]
                    row_values[col_idx] = candidate.accepted_value
                    changed_cells.add((src_row[0].row, col_idx + 1))  # 1-based col

        out_ws.append(row_values)

    # Apply yellow highlighting to changed cells
    # The out_ws rows start at 1 (header) and data rows start at 2.
    # The src row numbers map directly since we copy row-by-row in order.
    # Re-compute the actual output row numbers from the written rows.
    # Since we wrote header at row 1 and data rows in src order, we can map
    # src_row_num → out_row_num by offset (both start at row 2 for data).
    # src_ws may have gaps so we need a direct mapping.
    src_row_to_out_row: dict[int, int] = {}
    out_row_num = 2  # data starts at row 2
    for src_row in src_ws.iter_rows(min_row=2):
        src_row_to_out_row[src_row[0].row] = out_row_num
        out_row_num += 1

    for src_row_num, col_num in changed_cells:
        out_row_num_mapped = src_row_to_out_row.get(src_row_num)
        if out_row_num_mapped is None:
            continue
        cell = out_ws.cell(row=out_row_num_mapped, column=col_num)
        cell.fill = CHANGED_CELL_FILL

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_wb.save(str(output_path))
    logger.info("Wrote updated workbook to %s (%d changes)", output_path, len(changed_cells))
    return feature_warnings


# ---------------------------------------------------------------------------
# T098 — Audit-log CSV generation
# ---------------------------------------------------------------------------

AUDIT_LOG_FIELDS = [
    "row_id",
    "column_name",
    "old_value",
    "new_value",
    "proposal_id",
    "decision",
    "decided_at",
]


def generate_audit_log(
    candidates: list[ExportCandidate],
    row_lookup: dict[str, dict[str, Any]],
    decision_records: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """
    T098: Write the audit log CSV to output_path.

    Columns: row_id, column_name, old_value, new_value, proposal_id, decision, decided_at.
    Decision timestamps are derived from persisted ReviewDecisionRecord entries.
    """
    # Build a {proposal_id → latest decision record} index
    decision_by_proposal: dict[str, dict[str, Any]] = {}
    for rec in decision_records:
        pid = rec.get("proposal_id", "")
        existing = decision_by_proposal.get(pid)
        if existing is None or rec.get("decided_at", "") >= existing.get("decided_at", ""):
            decision_by_proposal[pid] = rec

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_LOG_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            row_data = row_lookup.get(candidate.row_id, {})
            old_value = row_data.get(candidate.column_name)
            old_value_str = "" if old_value is None else str(old_value)

            dec_rec = decision_by_proposal.get(candidate.proposal_id, {})
            decided_at = dec_rec.get("decided_at", "")

            writer.writerow(
                {
                    "row_id": candidate.row_id,
                    "column_name": candidate.column_name,
                    "old_value": old_value_str,
                    "new_value": candidate.accepted_value if candidate.accepted_value is not None else "",
                    "proposal_id": candidate.proposal_id,
                    "decision": candidate.decision,
                    "decided_at": decided_at,
                }
            )
    logger.info("Wrote audit log to %s (%d entries)", output_path, len(candidates))


# ---------------------------------------------------------------------------
# T099 — Diagnostics JSON
# ---------------------------------------------------------------------------


def generate_diagnostics(
    run_id: str,
    proposals: list[dict[str, Any]],
    decision_records: list[dict[str, Any]],
    unresolved_matches: list[dict[str, Any]],
    feature_warnings: list[str],
    candidates: list[ExportCandidate],
) -> dict[str, Any]:
    """
    T099: Build a diagnostics dict covering:
    - matching failures (unmatched, ambiguous, duplicate-row-conflict PDFs)
    - blocked/unclear/skipped/error proposal outcomes
    - weak evidence and evidence recovery
    - unsupported workbook feature warnings
    - completed-with-warnings summary
    """
    # --- Matching failures ---
    unmatched = [m for m in unresolved_matches if m.get("outcome") == "unmatched"]
    ambiguous = [m for m in unresolved_matches if m.get("outcome") == "ambiguous"]
    duplicate_row = [m for m in unresolved_matches if m.get("outcome") == "duplicate_row_conflict"]

    # --- Proposal outcome breakdown ---
    blocked: list[dict[str, Any]] = []
    unclear: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    error: list[dict[str, Any]] = []
    weak_evidence: list[dict[str, Any]] = []
    evidence_recovery: list[dict[str, Any]] = []

    for proposal in proposals:
        state = proposal.get("proposal_state", "")
        flags: list[str] = proposal.get("status_flags", [])
        entry = {
            "proposal_id": proposal.get("proposal_id"),
            "row_id": proposal.get("row_id"),
            "column_name": proposal.get("column_name"),
            "pdf_id": proposal.get("pdf_id"),
        }
        if state == "blocked":
            blocked.append(entry)
        elif state == "unclear":
            unclear.append(entry)
        elif state == "skipped":
            skipped.append(entry)
        elif state == "error":
            error.append(entry)

        if WarningStatusCategory.WEAK_EVIDENCE in flags:
            weak_evidence.append(entry)
        if WarningStatusCategory.QUOTE_PAGE_FALLBACK in flags:
            evidence_recovery.append({**entry, "reason": "quote_page_fallback"})
        if WarningStatusCategory.FIGURE_DERIVED in flags:
            evidence_recovery.append({**entry, "reason": "figure_derived"})

    # --- Completed-with-warnings signals ---
    warning_signals: list[str] = []
    if unmatched:
        warning_signals.append(f"{len(unmatched)} unmatched PDF(s)")
    if ambiguous:
        warning_signals.append(f"{len(ambiguous)} ambiguous match(es)")
    if duplicate_row:
        warning_signals.append(f"{len(duplicate_row)} duplicate-row conflict(s)")
    if blocked:
        warning_signals.append(f"{len(blocked)} blocked proposal(s)")
    if unclear:
        warning_signals.append(f"{len(unclear)} unclear proposal outcome(s)")
    if error:
        warning_signals.append(f"{len(error)} proposal error(s)")
    if weak_evidence:
        warning_signals.append(f"{len(weak_evidence)} proposal(s) with weak evidence")
    if feature_warnings:
        warning_signals.append(f"{len(feature_warnings)} unsupported workbook feature warning(s)")
    if not candidates:
        warning_signals.append("no proposals accepted for export")

    completed_with_warnings = len(warning_signals) > 0

    return {
        "run_id": run_id,
        "matching_failures": {
            "unmatched": unmatched,
            "ambiguous": ambiguous,
            "duplicate_row_conflict": duplicate_row,
        },
        "proposal_outcomes": {
            "blocked": blocked,
            "unclear": unclear,
            "skipped": skipped,
            "error": error,
        },
        "weak_evidence": weak_evidence,
        "evidence_recovery": evidence_recovery,
        "unsupported_workbook_features": feature_warnings,
        "export_summary": {
            "accepted_changes": len(candidates),
        },
        "completed_with_warnings": completed_with_warnings,
        "warning_signals": warning_signals,
    }


# ---------------------------------------------------------------------------
# Top-level export orchestrator
# ---------------------------------------------------------------------------


class ExportError(RuntimeError):
    pass


def run_export(artifacts: Any, run_id: str) -> dict[str, Any]:
    """
    Orchestrate T096–T099: load artifacts, generate workbook, audit log, and diagnostics.

    Returns a summary dict with paths and warning counts.
    Raises ExportError if the source workbook cannot be located or written.
    """
    from .review import get_export_candidates

    # --- Load inputs ---
    try:
        input_summary = artifacts.read_json("inputs/input_summary.json")
    except (FileNotFoundError, KeyError) as exc:
        raise ExportError(f"Cannot read input_summary.json: {exc}") from exc

    table_path = Path(input_summary.get("table_path", ""))
    if not table_path.is_file():
        raise ExportError(f"Source table not found at '{table_path}'; cannot generate XLSX export")

    try:
        input_details = artifacts.read_json("inputs/input_details.json")
    except (FileNotFoundError, KeyError):
        input_details = {}

    table_rows: list[dict[str, Any]] = input_details.get("table_rows", [])
    row_lookup = _build_row_lookup(table_rows)

    # Accepted proposals
    candidates = get_export_candidates(artifacts)

    # Decision records for audit log timestamps
    decision_records = artifacts.read_jsonl("review/decisions.jsonl")

    # Unresolved matches for diagnostics
    try:
        unresolved_matches = artifacts.read_json("matching/unresolved.json")
        if not isinstance(unresolved_matches, list):
            unresolved_matches = []
    except (FileNotFoundError, KeyError):
        unresolved_matches = []

    # All proposals for diagnostics
    proposals = artifacts.read_jsonl("proposals/proposals.jsonl")

    # --- T096 + T097: Generate XLSX and detect unsupported features ---
    workbook_path = artifacts.root / "exports" / "updated_workbook.xlsx"
    feature_warnings = generate_xlsx_export(
        source_path=table_path,
        table_rows=table_rows,
        candidates=candidates,
        output_path=workbook_path,
    )

    # --- T098: Audit log ---
    audit_log_path = artifacts.root / "exports" / "audit_log.csv"
    generate_audit_log(
        candidates=candidates,
        row_lookup=row_lookup,
        decision_records=decision_records,
        output_path=audit_log_path,
    )

    # --- T099: Diagnostics ---
    diagnostics = generate_diagnostics(
        run_id=run_id,
        proposals=proposals,
        decision_records=decision_records,
        unresolved_matches=unresolved_matches,
        feature_warnings=feature_warnings,
        candidates=candidates,
    )
    diagnostics_path = artifacts.root / "exports" / "diagnostics.json"
    artifacts.write_json("exports/diagnostics.json", diagnostics)

    return {
        "run_id": run_id,
        "accepted_changes": len(candidates),
        "feature_warnings": feature_warnings,
        "workbook_path": str(workbook_path),
        "audit_log_path": str(audit_log_path),
        "diagnostics_path": str(diagnostics_path),
        "completed_with_warnings": diagnostics["completed_with_warnings"],
        "warning_signals": diagnostics["warning_signals"],
    }
