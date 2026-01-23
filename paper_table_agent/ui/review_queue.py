from __future__ import annotations

from typing import Any, Iterable

from paper_table_agent.config import DEFAULT_EMPTY_VALUES
from paper_table_agent.io.locks import is_empty


def build_review_rows(
    rows: list[dict[str, Any]],
    matches: Iterable[dict[str, Any]],
    proposals: list[dict[str, Any]],
    table: Any,
    reviews: dict[str, dict[str, Any]] | None = None,
    empty_values: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    matched_row_ids = {
        str(match.get("row_id"))
        for match in matches
        if match.get("status") == "matched" and match.get("row_id") is not None
    }
    proposals_by_row: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposals:
        row_id = str(proposal.get("row_id"))
        proposals_by_row.setdefault(row_id, []).append(proposal)
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id not in matched_row_ids:
            continue
        row_proposals = proposals_by_row.get(row_id, [])
        review_items = review_items_for_row(
            row,
            row_proposals,
            table,
            reviews=reviews,
            empty_values=empty_values,
        )
        if review_items:
            review_rows.append(row)
    return review_rows


def review_items_for_row(
    row: dict[str, Any],
    proposals: list[dict[str, Any]],
    table: Any,
    reviews: dict[str, dict[str, Any]] | None = None,
    empty_values: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    empty_values = empty_values or DEFAULT_EMPTY_VALUES
    row_index = row.get("row_index")
    review_items: list[dict[str, Any]] = []
    for proposal in proposals:
        if reviews and proposal.get("proposal_id") in reviews:
            continue
        column = proposal.get("column")
        if column not in table.dataframe.columns:
            continue
        cell_value = table.dataframe.at[int(row_index), column]
        cell_empty = is_empty(cell_value, empty_values)
        verification_status = _verification_status(proposal)
        if cell_empty or verification_status in {"contradicts", "unclear"}:
            review_items.append(proposal)
    return review_items


def remaining_review_count(
    proposals: list[dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    matches: Iterable[dict[str, Any]],
    table: Any,
    empty_values: Iterable[str] | None = None,
) -> int:
    review_rows = build_review_rows(rows, matches, proposals, table, reviews=reviews, empty_values=empty_values)
    review_row_ids = {str(row.get("row_id")) for row in review_rows}
    count = 0
    for proposal in proposals:
        if str(proposal.get("row_id")) not in review_row_ids:
            continue
        if proposal.get("proposal_id") in reviews:
            continue
        column = proposal.get("column")
        if column not in table.dataframe.columns:
            continue
        row_index = next(
            (row.get("row_index") for row in rows if str(row.get("row_id")) == str(proposal.get("row_id"))),
            None,
        )
        if row_index is None:
            continue
        cell_value = table.dataframe.at[int(row_index), column]
        cell_empty = is_empty(cell_value, empty_values or DEFAULT_EMPTY_VALUES)
        verification_status = _verification_status(proposal)
        if cell_empty or verification_status in {"contradicts", "unclear"}:
            count += 1
    return count


def _verification_status(proposal: dict[str, Any]) -> str:
    flags = proposal.get("flags") or {}
    if flags.get("verify_only"):
        return proposal.get("status") or "unclear"
    return flags.get("verification_status") or "unclear"
