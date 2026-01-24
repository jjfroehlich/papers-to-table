from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.evidence_finder import find_evidence_for_proposals
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.io.locks import is_empty
from paper_table_agent.io.schema import load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.pdf.highlight import locate_quote, render_page_image
from paper_table_agent.store.db import Store
from paper_table_agent.ui.defaults import load_default_run_config, resolve_default_paths
from paper_table_agent.ui.registry import discover_runs
from paper_table_agent.ui.review_queue import build_review_rows, remaining_review_count, review_items_for_row

DEFAULT_CONFIG_PATH = Path("run_config.json")
LOGGER = logging.getLogger("paper_table_agent.ui")



def _sort_proposals(proposals: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    if columns:
        column_order = {name: idx for idx, name in enumerate(columns)}
        return sorted(proposals, key=lambda item: column_order.get(item.get("column", ""), 9999))
    return sorted(proposals, key=lambda item: item.get("column", ""))


def _format_time(value: float | None) -> str:
    if not value:
        return "Unknown"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def _path_browser(
    label: str,
    path_key: str,
    base_path: Path,
    allow_files: bool,
    allowed_suffixes: set[str],
) -> None:
    if not base_path.exists() or not base_path.is_dir():
        base_path = Path.cwd()
    browser_key = f"{path_key}-browser"
    if browser_key not in st.session_state:
        st.session_state[browser_key] = str(base_path)

    current_dir = Path(st.session_state[browser_key]).expanduser()
    if not current_dir.exists() or not current_dir.is_dir():
        current_dir = base_path
    st.session_state[browser_key] = str(current_dir)

    with st.expander(label):
        st.caption(f"Browsing: {current_dir}")
        nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 2])
        with nav_col1:
            if st.button("Up", key=f"{browser_key}-up"):
                parent = current_dir.parent
                st.session_state[browser_key] = str(parent)
                st.experimental_rerun()
        with nav_col2:
            if st.button("Home", key=f"{browser_key}-home"):
                st.session_state[browser_key] = str(base_path)
                st.experimental_rerun()
        with nav_col3:
            st.caption("Select a directory to open, or pick a file/folder to use.")

        entries = sorted(current_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        dirs = [entry for entry in entries if entry.is_dir()]
        files = [
            entry
            for entry in entries
            if entry.is_file() and (not allowed_suffixes or entry.suffix.lower() in allowed_suffixes)
        ]

        dir_col, file_col = st.columns(2)
        with dir_col:
            st.markdown("**Folders**")
            dir_options = [str(path) for path in dirs]
            if dir_options:
                selected_dir = st.selectbox(
                    "Folders",
                    options=dir_options,
                    index=0,
                    key=f"{browser_key}-dir",
                    label_visibility="collapsed",
                )
                if st.button("Open folder", key=f"{browser_key}-open-dir"):
                    st.session_state[browser_key] = selected_dir
                    st.experimental_rerun()
            else:
                st.caption("No subfolders found.")
            if st.button("Use this folder", key=f"{browser_key}-select-dir"):
                st.session_state[path_key] = str(current_dir)
        with file_col:
            st.markdown("**Files**")
            if allow_files:
                file_options = [str(path) for path in files]
                if file_options:
                    selected_file = st.selectbox(
                        "Files",
                        options=file_options,
                        index=0,
                        key=f"{browser_key}-file",
                        label_visibility="collapsed",
                    )
                    if st.button("Use selected file", key=f"{browser_key}-select-file"):
                        st.session_state[path_key] = selected_file
                else:
                    st.caption("No matching files found.")
            else:
                st.caption("File selection is disabled for folder inputs.")


def _run_progress(store: Store) -> tuple[int, int, str | None]:
    pdfs = [dict(row) for row in store.list_pdfs()]
    if not pdfs:
        return 0, 0, None
    processed = sum(1 for pdf in pdfs if pdf.get("status") in {"processed", "failed"})
    total = len(pdfs)
    pending = next((pdf for pdf in pdfs if pdf.get("status") == "parsed"), None)
    current_name = Path(pending["path"]).name if pending and pending.get("path") else None
    return processed, total, current_name


def _proposal_state(proposal: dict[str, Any], review: dict[str, Any] | None) -> str:
    if review:
        return review.get("decision", "reviewed")
    flags = proposal.get("flags", {})
    if flags.get("needs_more_evidence"):
        return "needs_more_evidence"
    status = proposal.get("status") or "proposed"
    if status in {"found", "inferred", "verify"}:
        return "proposed"
    if status in {"unclear", "no_evidence", "not_found", "error"}:
        return "unclear"
    return status


def _evidence_label(evidence: dict[str, Any]) -> str:
    quote = (evidence.get("quote") or "").strip()
    snippet = quote[:120] + ("…" if len(quote) > 120 else "")
    page = evidence.get("page")
    return f"Page {page}: {snippet}".strip()


def _evidence_badge(proposal: dict[str, Any]) -> str:
    flags = proposal.get("flags") or {}
    evidence = proposal.get("evidence") or []
    evidence_quality = flags.get("evidence_quality")
    if not evidence:
        return "Evidence: missing"
    if evidence_quality:
        return f"Evidence: {evidence_quality}"
    if flags.get("evidence_validation_errors") or flags.get("quote_has_ellipsis"):
        return "Evidence: weak"
    return "Evidence: strong"

def _proposal_failure_reason(proposal: dict[str, Any]) -> str:
    flags = proposal.get("flags", {})
    reason = flags.get("failure_reason")
    if reason:
        return str(reason).replace("_", " ")
    if flags.get("error_type"):
        return str(flags["error_type"]).replace("_", " ")
    validation_errors = flags.get("evidence_validation_errors") or []
    if validation_errors:
        return "evidence validation failed"
    return "no evidence found"


def _next_undecided_index(proposals: list[dict[str, Any]], reviews: dict[str, dict[str, Any]]) -> int | None:
    for idx, proposal in enumerate(proposals):
        if proposal["proposal_id"] not in reviews:
            return idx
    return None


def _advance_review_position(
    row_index: int,
    column_index: int,
    review_rows: list[dict[str, Any]],
    review_items_by_row: dict[str, list[dict[str, Any]]],
) -> tuple[int, int]:
    if not review_rows:
        return row_index, column_index
    current_row = review_rows[row_index]
    current_items = review_items_by_row.get(str(current_row.get("row_id")), [])
    if column_index + 1 < len(current_items):
        return row_index, column_index + 1
    for next_row_idx in range(row_index + 1, len(review_rows)):
        next_row = review_rows[next_row_idx]
        next_items = review_items_by_row.get(str(next_row.get("row_id")), [])
        if next_items:
            return next_row_idx, 0
    return row_index, max(0, len(current_items) - 1)


def _next_pending_row_index(
    review_rows: list[dict[str, Any]],
    pending_counts: dict[str, int],
) -> int:
    for idx, row in enumerate(review_rows):
        if pending_counts.get(str(row.get("row_id")), 0) > 0:
            return idx
    return 0


def _log_review_debug(store: Store) -> None:
    if os.getenv("PAPER_TABLE_AGENT_REVIEW_DEBUG") != "1":
        return
    proposals = [
        dict(row)
        for row in store.conn.execute("SELECT status, flags_json FROM proposals")
    ]
    status_counts: dict[str, int] = {}
    mapping_counts: dict[str, int] = {"mapping_dependent": 0, "mapping_independent": 0}
    verification_counts: dict[str, int] = {}
    verify_only_counts: dict[str, int] = {}
    for proposal in proposals:
        status = proposal.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        flags = json.loads(proposal.get("flags_json") or "{}")
        if flags.get("mapping_dependent"):
            mapping_counts["mapping_dependent"] += 1
        else:
            mapping_counts["mapping_independent"] += 1
        verification_status = flags.get("verification_status")
        if verification_status:
            verification_counts[verification_status] = verification_counts.get(verification_status, 0) + 1
        if flags.get("verify_only"):
            verify_only_counts[status] = verify_only_counts.get(status, 0) + 1
    LOGGER.info("Review debug: proposal statuses=%s", status_counts)
    LOGGER.info("Review debug: mapping counts=%s", mapping_counts)
    if verification_counts:
        LOGGER.info("Review debug: verification statuses=%s", verification_counts)
    if verify_only_counts:
        LOGGER.info("Review debug: verify-only statuses=%s", verify_only_counts)


def build_app() -> None:
    st.set_page_config(page_title="Paper Table Agent", layout="wide")
    st.title("Paper Table Agent")

    test_mode = os.getenv("PAPER_TABLE_AGENT_TEST_MODE")
    if test_mode == "review":
        run_tab = st.container()
        review_tab = st.container()
        show_run_tab = False
    else:
        run_tab, review_tab = st.tabs(["Run", "Review"])
        show_run_tab = True

    if "default_config" not in st.session_state:
        st.session_state["default_config"] = load_default_run_config(DEFAULT_CONFIG_PATH)

    if "runs" not in st.session_state:
        st.session_state["runs"] = discover_runs()

    if "selected_run_dir" not in st.session_state:
        st.session_state["selected_run_dir"] = None

    default_config = st.session_state.get("default_config", {})
    config_table, config_pdf = resolve_default_paths(default_config)

    with run_tab:
        if not show_run_tab:
            pass
        else:
            st.header("Run")

            if "manual_table_path" not in st.session_state:
                st.session_state["manual_table_path"] = config_table or ""
            if "manual_pdf_folder" not in st.session_state:
                st.session_state["manual_pdf_folder"] = config_pdf or ""

            st.markdown("**Inputs**")
            st.text_input("Table path", key="manual_table_path")
            base_table = Path(config_table).parent if config_table else Path.cwd()
            _path_browser(
                "Browse tables",
                "manual_table_path",
                base_table,
                allow_files=True,
                allowed_suffixes={".xlsx", ".csv"},
            )

            st.text_input("PDF folder path", key="manual_pdf_folder")
            base_pdf = Path(config_pdf) if config_pdf else Path.cwd()
            _path_browser(
                "Browse PDF folders",
                "manual_pdf_folder",
                base_pdf,
                allow_files=False,
                allowed_suffixes=set(),
            )

            table_path = Path(st.session_state.get("manual_table_path", "")).expanduser()
            pdf_folder = Path(st.session_state.get("manual_pdf_folder", "")).expanduser()
            valid_table = table_path.exists()
            valid_pdf = pdf_folder.exists()

            if valid_table:
                st.caption(f"Selected table: {table_path.name} (last modified {_format_time(table_path.stat().st_mtime)})")
            if valid_pdf:
                st.caption(f"Selected PDF folder: {pdf_folder}")

            if st.button("Start run", disabled=not (valid_table and valid_pdf)):
                payload = dict(default_config)
                payload["table_path"] = str(table_path)
                payload["pdf_folder"] = str(pdf_folder)
                config = RunConfig.model_validate(payload)
                run_paths = create_run_paths(config.table_path, run_name=config.run_name)
                prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
                capture_run_config(config, run_paths, prompt_versions)
                store = Store.init_db(run_paths.db_path)
                run_workflow(config=config, run_paths=run_paths, store=store)
                st.session_state["selected_run_dir"] = run_paths.run_dir
                st.session_state["runs"] = discover_runs()
                st.success(f"Run completed: {run_paths.run_dir}")

            st.divider()
            st.subheader("Run status")
            runs = st.session_state.get("runs", [])
            selected_run_dir = st.session_state.get("selected_run_dir")
            selected_run = next((run for run in runs if run.run_dir == selected_run_dir), None)
            if not selected_run and runs:
                selected_run = runs[0]
            if not selected_run:
                st.info("No runs yet.")
            else:
                status_map = {
                    "completed": "Done",
                    "completed_with_errors": "Completed (errors)",
                    "completed_with_warnings": "Completed (warnings)",
                    "failed": "Failed",
                    "in_progress": "Running",
                    "paused": "Paused",
                    "stopped": "Stopped",
                }
                status_line = status_map.get(selected_run.status, selected_run.status.title())
                st.write(f"Status: **{status_line}**")
                store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
                _, _, current_pdf = _run_progress(store)
                if current_pdf:
                    st.caption(f"Current PDF: {current_pdf}")
                if selected_run.run_dir.exists():
                    st.link_button("Open run folder", f"file://{selected_run.run_dir}")


    with review_tab:
        st.header("Review")
        runs = [
            run
            for run in st.session_state.get("runs", [])
            if run.status in {"completed", "completed_with_errors", "completed_with_warnings"}
        ]
        if not runs:
            st.info("No completed runs yet.")
        else:
            run_labels = [run.label for run in runs]
            default_run_dir = st.session_state.get("selected_run_dir")
            default_index = 0
            if default_run_dir:
                for idx, run in enumerate(runs):
                    if run.run_dir == default_run_dir:
                        default_index = idx
                        break
            selected_label = st.selectbox("Run", run_labels, index=default_index, key="review-run")
            selected_run = runs[run_labels.index(selected_label)]
            st.session_state["selected_run_dir"] = selected_run.run_dir

            store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
            _log_review_debug(store)
            run_config = json.loads((selected_run.run_dir / "run_config.json").read_text(encoding="utf-8"))
            table = load_table(Path(run_config["table_path"]))
            schema_source = Path(run_config["table_path"])
            if run_config.get("schema_mode") == "separate" and run_config.get("schema_path"):
                schema_source = Path(run_config["schema_path"])
            specs = load_schema(schema_source, run_config["schema_sheet_name"])
            columns = [spec.column_name for spec in specs]

            proposals_meta = [
                dict(row)
                for row in store.conn.execute(
                "SELECT proposal_id, row_id, pdf_id, column, status, confidence, proposed_value, flags_json, evidence_json "
                "FROM proposals"
                )
            ]
            for proposal in proposals_meta:
                proposal["flags"] = json.loads(proposal.get("flags_json") or "{}")
                proposal["evidence"] = json.loads(proposal.get("evidence_json") or "[]")

            reviews = store.fetch_reviews()
            rows = [dict(row) for row in store.fetch_rows()]
            rows.sort(key=lambda row: row.get("row_index", 0))
            matches = [dict(row) for row in store.fetch_matches()]

            remaining = remaining_review_count(proposals_meta, reviews, rows, matches, table)
            st.caption(f"Remaining items: {remaining}")

            review_rows = build_review_rows(rows, matches, proposals_meta, table, reviews=reviews)
            matched_row_ids = {
                str(match.get("row_id"))
                for match in matches
                if match.get("status") == "matched" and match.get("row_id") is not None
            }
            rows_with_proposals = {str(proposal.get("row_id")) for proposal in proposals_meta}
            matched_without_proposals = matched_row_ids - rows_with_proposals
            if matched_without_proposals:
                st.info(
                    f"{len(matched_without_proposals)} matched row(s) have no proposals yet. "
                    "They are hidden from Review."
                )
            review_items_by_row = {}
            for row in review_rows:
                row_proposals = [
                    proposal for proposal in proposals_meta if proposal.get("row_id") == row.get("row_id")
                ]
                row_proposals = _sort_proposals(row_proposals, columns)
                review_items_by_row[str(row.get("row_id"))] = review_items_for_row(
                    row,
                    row_proposals,
                    table,
                    reviews=reviews,
                )

            pending_counts = {
                row_id: len(items)
                for row_id, items in review_items_by_row.items()
            }

            if not review_rows:
                st.info("No matched rows need review.")
            else:
                if "selected_row_index" not in st.session_state:
                    st.session_state["selected_row_index"] = _next_pending_row_index(review_rows, pending_counts)
                if st.session_state["selected_row_index"] >= len(review_rows):
                    st.session_state["selected_row_index"] = 0
                if pending_counts.get(str(review_rows[st.session_state["selected_row_index"]].get("row_id")), 0) == 0:
                    st.session_state["selected_row_index"] = _next_pending_row_index(review_rows, pending_counts)

                row_options = []
                for idx, row in enumerate(review_rows):
                    pending = pending_counts.get(str(row.get("row_id")), 0)
                    row_label = f"Row {row.get('row_index', idx) + 1} — {pending} pending"
                    row_options.append(row_label)
                selected_label = row_options[st.session_state["selected_row_index"]]
                selected_label = st.selectbox("Row", row_options, index=st.session_state["selected_row_index"])
                st.session_state["selected_row_index"] = row_options.index(selected_label)

                row_nav1, row_nav2, row_nav3 = st.columns([1, 1, 2])
                with row_nav1:
                    if st.button("Prev row"):
                        st.session_state["selected_row_index"] = max(0, st.session_state["selected_row_index"] - 1)
                with row_nav2:
                    if st.button("Next row"):
                        st.session_state["selected_row_index"] = min(
                            len(review_rows) - 1,
                            st.session_state["selected_row_index"] + 1,
                        )
                with row_nav3:
                    current_position = st.session_state["selected_row_index"] + 1
                    st.caption(f"Row {current_position} of {len(review_rows)}")

                row_data = review_rows[st.session_state["selected_row_index"]]
                row_id = row_data["row_id"]

                row_proposals = [proposal for proposal in proposals_meta if proposal.get("row_id") == row_id]
                row_proposals = _sort_proposals(row_proposals, columns)
                review_items = review_items_by_row.get(str(row_id), [])

                if not review_items:
                    st.info("No proposals for this row.")
                else:
                    index_key = f"proposal-index-{row_id}"
                    if index_key not in st.session_state:
                        st.session_state[index_key] = 0
                    if st.session_state[index_key] >= len(review_items):
                        st.session_state[index_key] = 0

                    col_left, col_right = st.columns([1.1, 1.4])
                    with col_left:
                        column_labels = [item.get("column", "Unknown") for item in review_items]
                        current_index = st.session_state[index_key]
                        nav_cols = st.columns([1, 1, 2])
                        with nav_cols[0]:
                            if st.button("Prev field", key=f"prev-field-{row_id}"):
                                st.session_state[index_key] = max(0, current_index - 1)
                                st.experimental_rerun()
                        with nav_cols[1]:
                            if st.button("Next field", key=f"next-field-{row_id}"):
                                st.session_state[index_key] = min(len(column_labels) - 1, current_index + 1)
                                st.experimental_rerun()
                        with nav_cols[2]:
                            st.caption(f"Field {current_index + 1} of {len(column_labels)}")
                        selected_column = st.selectbox(
                            "Column stepper",
                            column_labels,
                            index=current_index,
                            key=f"column-stepper-{row_id}",
                        )
                        current_index = column_labels.index(selected_column)
                        st.session_state[index_key] = current_index
                        current = review_items[current_index]
                        st.subheader("Row meta")
                        st.write(
                            {
                                "Title": row_data.get("title"),
                                "Authors": row_data.get("authors"),
                                "Year": row_data.get("year"),
                            }
                        )
                        st.subheader("Proposal")
                        st.markdown(f"### {current['column']}")
                        review = reviews.get(current["proposal_id"])
                        state = _proposal_state(current, review)
                        if state == "needs_more_evidence":
                            st.caption("⚠️ Needs more evidence")
                        st.caption(_evidence_badge(current))
                        search_hints = (current.get("flags") or {}).get("search_hints") or []
                        if search_hints:
                            st.caption(f"Search hints: {', '.join(search_hints)}")
                        current_value = table.dataframe.at[int(row_data["row_index"]), current["column"]]
                        st.write("Current value:", "—" if is_empty(current_value) else current_value)
                        proposed_value = current.get("proposed_value")
                        if proposed_value is None or is_empty(proposed_value):
                            st.write("Proposed value:", "No value proposed")
                            st.caption(f"No proposal because: {_proposal_failure_reason(current)}")
                        else:
                            st.write("Proposed value:", proposed_value)

                        evidence_items = current.get("evidence", [])
                        if evidence_items:
                            st.markdown("**Evidence**")
                            for evidence in evidence_items:
                                st.write(_evidence_label(evidence))
                        else:
                            st.caption("No evidence recorded.")

                        manual_value_default = (
                            review["final_value"]
                            if review and review["final_value"] is not None
                            else current.get("proposed_value") or ""
                        )
                        manual_value = st.text_input(
                            "Edited value",
                            value=manual_value_default,
                            key=f"manual-{current['proposal_id']}",
                        )
                        note = st.text_area(
                            "Note",
                            value=review["note"] if review else "",
                            key=f"note-{current['proposal_id']}",
                        )

                        def _apply_review_decision(decision: str, final_value: str | None) -> None:
                            store.insert_review(
                                {
                                    "review_id": current["proposal_id"],
                                    "proposal_id": current["proposal_id"],
                                    "decision": decision,
                                    "final_value": final_value,
                                    "note": note,
                                }
                            )
                            next_row, next_col = _advance_review_position(
                                st.session_state["selected_row_index"],
                                current_index,
                                review_rows,
                                review_items_by_row,
                            )
                            st.session_state["selected_row_index"] = next_row
                            st.session_state[index_key] = next_col

                        decision_cols = st.columns(3)
                        with decision_cols[0]:
                            if st.button("Accept", key=f"accept-{current['proposal_id']}"):
                                _apply_review_decision("accepted", current.get("proposed_value"))
                                st.success("Accepted")
                        with decision_cols[1]:
                            if st.button("Accept with edit", key=f"accept-edit-{current['proposal_id']}"):
                                _apply_review_decision("accepted", manual_value)
                                st.success("Accepted with edit")
                        with decision_cols[2]:
                            if st.button("Reject", key=f"reject-{current['proposal_id']}"):
                                _apply_review_decision("rejected", "")
                                st.warning("Rejected")

                    with col_right:
                        current = review_items[current_index]
                        st.subheader("PDF viewer")
                        with st.container(height=650):
                            evidence_items = current.get("evidence", [])
                            if evidence_items:
                                if len(evidence_items) > 1:
                                    evidence_index = st.selectbox(
                                        "Evidence",
                                        list(range(len(evidence_items))),
                                        format_func=lambda idx: _evidence_label(evidence_items[idx]),
                                        key=f"evidence-{current['proposal_id']}",
                                    )
                                else:
                                    evidence_index = 0
                                evidence = evidence_items[evidence_index]
                                st.write("Quote:", evidence.get("quote"))
                                st.write("Page:", evidence.get("page"))
                                rects = evidence.get("rects") or []
                                pdf_path = store.conn.execute(
                                    "SELECT path FROM pdfs WHERE pdf_id = ?",
                                    (current.get("pdf_id"),),
                                ).fetchone()
                                pdf_path = pdf_path["path"] if pdf_path else None
                                if pdf_path and evidence.get("page"):
                                    image = render_page_image(pdf_path, int(evidence["page"]), rects)
                                    if not rects:
                                        st.caption("Highlight not found.")
                                    st.image(image, caption=f"PDF page {evidence['page']}")
                                    if not rects:
                                        if st.button("Locate highlight", key=f"relocate-{current['proposal_id']}"):
                                            tokens_path = (
                                                Path(selected_run.run_dir)
                                                / "artifacts"
                                                / "parsed"
                                                / f"{current['pdf_id']}_tokens.jsonl"
                                            )
                                            tokens = []
                                            if tokens_path.exists():
                                                tokens = [
                                                    json.loads(line)
                                                    for line in tokens_path.read_text(encoding="utf-8").splitlines()
                                                    if line
                                                ]
                                            chunks = [
                                                dict(row)
                                                for row in store.conn.execute(
                                                    """
                                                    SELECT chunk_id, chunk_pk, chunk_idx, text, text_raw, text_norm, page_start, page_end, chunk_type
                                                    FROM retrieval_chunks WHERE pdf_id = ?
                                                    """,
                                                    (current.get("pdf_id"),),
                                                )
                                            ]
                                            parsed_path = (
                                                Path(selected_run.run_dir)
                                                / "artifacts"
                                                / "parsed"
                                                / f"{current['pdf_id']}_pymupdf.json"
                                            )
                                            page_text = []
                                            if parsed_path.exists():
                                                parsed_payload = json.loads(parsed_path.read_text(encoding="utf-8"))
                                                page_text = parsed_payload.get("page_text") or []
                                            refreshed = find_evidence_for_proposals(
                                                [current],
                                                chunks,
                                                page_text,
                                                tokens,
                                                pdf_path,
                                            )
                                            current = refreshed[0]
                                            evidence_items = current.get("evidence", [])
                                            if evidence_items:
                                                evidence = evidence_items[evidence_index]
                                            store.update_proposal_evidence(
                                                current["proposal_id"],
                                                evidence_items,
                                                current.get("flags", {}),
                                            )
                                            st.success("Re-locate attempted")
                                else:
                                    st.info("Evidence missing a page number or PDF path.")
                            else:
                                st.info("No evidence available for this proposal.")

                    st.divider()
                    st.subheader("Export updated table")
                    if st.checkbox("I confirm export settings"):
                        if st.button("Export updated table"):
                            export_run(Path(selected_run.run_dir))
                            st.success("Export completed")


if os.getenv("PAPER_TABLE_AGENT_UI_SMOKE") == "1":
    st.set_page_config(page_title="Paper Table Agent", layout="wide")
    st.title("Paper Table Agent")
    st.write("UI smoke check complete.")
else:
    build_app()
