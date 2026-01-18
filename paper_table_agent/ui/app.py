from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.pdf.highlight import locate_quote, render_page_image
from paper_table_agent.retrieval.index import load_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.store.db import Store
from paper_table_agent.ui.registry import discover_pdf_folders, discover_runs, discover_tables

st.set_page_config(page_title="Paper Table Agent", layout="wide")

st.title("Paper Table Agent")

run_tab, review_tab, export_tab, debug_tab = st.tabs(["Run", "Review", "Export", "Advanced"])


def _refresh_registry() -> None:
    st.session_state["runs"] = discover_runs()
    st.session_state["tables"] = discover_tables()
    st.session_state["pdf_folders"] = discover_pdf_folders()


if "runs" not in st.session_state:
    _refresh_registry()


with run_tab:
    st.header("Start a Run")
    if st.button("Refresh registry"):
        _refresh_registry()

    runs = st.session_state.get("runs", [])
    tables = st.session_state.get("tables", [])
    pdf_folders = st.session_state.get("pdf_folders", [])

    with st.expander("Run registry", expanded=False):
        st.write("Available tables:", [str(path) for path in tables] or "None found")
        st.write("Available PDF folders:", [str(path) for path in pdf_folders] or "None found")
        st.write("Runs:")
        for run in runs:
            st.write(f"- {run.label}")

    table_path = st.selectbox(
        "Table file",
        options=tables or [None],
        format_func=lambda path: str(path) if path else "No tables found",
    )
    pdf_folder = st.selectbox(
        "PDF folder",
        options=pdf_folders or [None],
        format_func=lambda path: str(path) if path else "No PDF folders found",
    )

    schema_sheet = "schema"
    table_columns: list[str] = []
    if table_path is not None:
        if table_path.suffix.lower() == ".xlsx":
            try:
                sheet_names = pd.ExcelFile(table_path).sheet_names
                schema_sheet = st.selectbox("Schema sheet", options=sheet_names)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to read workbook sheets: {exc}")
        else:
            st.caption("Schema sheet defaults to 'schema' for CSV inputs.")
        try:
            table = load_table(Path(table_path))
            table_columns = list(table.dataframe.columns)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load table: {exc}")

    column_options = ["(auto)"] + table_columns if table_columns else ["(auto)"]
    title_col = st.selectbox("Title column", options=column_options)
    authors_col = st.selectbox("Authors column", options=column_options)
    year_col = st.selectbox("Year column", options=column_options)

    verify_mode = st.checkbox("Verify locked cells", value=False)
    fast_mode = st.checkbox("Fast mode (skip HyDE/query expansion)", value=False)

    if "group_mapping" not in st.session_state:
        st.session_state["group_mapping"] = {}
    if "group_selection" not in st.session_state:
        st.session_state["group_selection"] = []

    if table_path and schema_sheet:
        if st.button("Load schema"):
            try:
                specs = load_schema(Path(table_path), schema_sheet)
                grouped = group_columns(specs)
                st.session_state["group_mapping"] = {
                    name: [spec.column_name for spec in specs] for name, specs in grouped.items()
                }
                st.session_state["group_selection"] = list(st.session_state["group_mapping"].keys())
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to load schema: {exc}")

    if st.session_state["group_mapping"]:
        st.session_state["group_selection"] = st.multiselect(
            "Groups to extract (order matters)",
            list(st.session_state["group_mapping"].keys()),
            default=st.session_state["group_selection"],
        )

    if st.button("Start run"):
        if not table_path or not pdf_folder:
            st.error("Select a table and PDF folder before starting a run.")
        else:
            config = RunConfig(
                table_path=Path(table_path),
                pdf_folder=Path(pdf_folder),
                schema_sheet_name=schema_sheet,
                title_col=None if title_col == "(auto)" else title_col,
                authors_col=None if authors_col == "(auto)" else authors_col,
                year_col=None if year_col == "(auto)" else year_col,
                verify_mode=verify_mode,
                fast_mode=fast_mode,
            )
            if st.session_state["group_selection"] and st.session_state["group_mapping"]:
                config.extraction.groups = [
                    {"name": group, "columns": st.session_state["group_mapping"][group]}
                    for group in st.session_state["group_selection"]
                ]
            run_paths = create_run_paths(config.table_path)
            prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
            capture_run_config(config, run_paths, prompt_versions)
            store = Store.init_db(run_paths.db_path)
            run_workflow(config=config, run_paths=run_paths, store=store)
            st.session_state["selected_run_dir"] = run_paths.run_dir
            _refresh_registry()
            st.success(f"Run completed: {run_paths.run_dir}")

    st.divider()
    st.subheader("Resume or stop a run")
    run_options = {run.label: run for run in runs}
    resume_label = st.selectbox("Run", options=list(run_options.keys())) if run_options else None
    selected_run = run_options.get(resume_label) if resume_label else None
    col_resume, col_stop = st.columns(2)
    with col_resume:
        if st.button("Resume run") and selected_run:
            run_dir = selected_run.run_dir
            config_path = run_dir / "run_config.json"
            config = RunConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
            store = Store.init_db(run_dir / "proposals.sqlite")
            run_workflow(config=config, run_paths=RunPaths(run_dir=run_dir), store=store, resume=True)
            st.session_state["selected_run_dir"] = run_dir
            _refresh_registry()
            st.success(f"Resumed run: {run_dir}")
    with col_stop:
        if st.button("Stop run") and selected_run:
            (selected_run.run_dir / "STOP").write_text("stop", encoding="utf-8")
            st.warning("Stop requested. The run will halt after the current PDF.")


with review_tab:
    st.header("Review Proposals")
    runs = st.session_state.get("runs", [])
    run_labels = [run.label for run in runs]
    default_run_dir = st.session_state.get("selected_run_dir")
    default_index = 0
    if default_run_dir:
        for idx, run in enumerate(runs):
            if run.run_dir == default_run_dir:
                default_index = idx
                break
    selected_label = st.selectbox("Run", run_labels, index=default_index) if run_labels else None
    selected_run = runs[default_index] if run_labels else None
    if selected_label:
        selected_run = runs[run_labels.index(selected_label)]

    if selected_run:
        run_dir_path = selected_run.run_dir
        store = Store.init_db(run_dir_path / "proposals.sqlite")
        run_config = json.loads((run_dir_path / "run_config.json").read_text(encoding="utf-8"))
        table = load_table(Path(run_config["table_path"]))

        rows = [dict(row) for row in store.fetch_rows()]
        proposals = [dict(row) for row in store.conn.execute("SELECT * FROM proposals")]
        matches = [dict(row) for row in store.fetch_matches()]
        reviews = store.fetch_reviews()

        proposal_by_row: dict[str, list[dict[str, Any]]] = {}
        needs_evidence_rows: set[str] = set()
        for proposal in proposals:
            flags = json.loads(proposal.get("flags_json") or "{}")
            proposal["flags"] = flags
            proposal["evidence"] = json.loads(proposal.get("evidence_json") or "[]")
            proposal_by_row.setdefault(proposal["row_id"], []).append(proposal)
            if flags.get("needs_more_evidence"):
                needs_evidence_rows.add(proposal["row_id"])

        match_by_row: dict[str, list[dict[str, Any]]] = {}
        for match in matches:
            if match.get("row_id") is None:
                continue
            match_by_row.setdefault(match["row_id"], []).append(match)

        st.subheader("Filters")
        only_with_proposals = st.checkbox("Only rows with proposals", value=True)
        only_ambiguous = st.checkbox("Only ambiguous mappings", value=False)
        only_duplicates = st.checkbox("Only duplicates", value=False)
        only_needs_evidence = st.checkbox("Only needs more evidence", value=False)
        search = st.text_input("Search title", value="")

        filtered_rows = []
        for row in rows:
            row_id = row["row_id"]
            if only_with_proposals and row_id not in proposal_by_row:
                continue
            row_matches = match_by_row.get(row_id, [])
            if only_ambiguous and not any(match["status"] == "ambiguous" for match in row_matches):
                continue
            if only_duplicates and not any(match["status"] == "duplicate" for match in row_matches):
                continue
            if only_needs_evidence and row_id not in needs_evidence_rows:
                continue
            if search and search.lower() not in str(row.get("title", "")).lower():
                continue
            filtered_rows.append(row)

        row_options = {f"{row['row_id']} | {row.get('title', '')}": row["row_id"] for row in filtered_rows}
        selection = st.selectbox("Row", list(row_options.keys()) if row_options else [])
        if selection:
            row_id = row_options[selection]
            row_data = next((row for row in rows if row["row_id"] == row_id), {})
            st.subheader("Row details")
            st.write(
                {
                    "Title": row_data.get("title"),
                    "Authors": row_data.get("authors"),
                    "Year": row_data.get("year"),
                }
            )
            row_matches = match_by_row.get(row_id, [])
            if row_matches:
                st.write("Mapping status:", [match["status"] for match in row_matches])

            row_proposals = proposal_by_row.get(row_id, [])
            if not row_proposals:
                st.info("No proposals for this row.")
            else:
                row_proposals.sort(key=lambda item: item.get("column", ""))
                index_key = f"proposal-index-{row_id}"
                if index_key not in st.session_state:
                    st.session_state[index_key] = 0
                current_index = st.session_state[index_key]
                if current_index >= len(row_proposals):
                    current_index = 0
                current = row_proposals[current_index]

                col_prev, col_next = st.columns(2)
                with col_prev:
                    if st.button("Prev", key=f"prev-{row_id}"):
                        st.session_state[index_key] = max(current_index - 1, 0)
                with col_next:
                    if st.button("Next", key=f"next-{row_id}"):
                        st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)

                st.markdown(f"### {current['column']}")
                st.write("Status:", current.get("status"))
                st.write("Current value:", table.dataframe.at[int(row_id), current["column"]])
                st.write("Proposed value:", current.get("proposed_value"))
                st.write("Confidence:", current.get("confidence"))
                if current["flags"].get("needs_more_evidence"):
                    st.warning("Needs more evidence")

                evidence_items = current.get("evidence", [])
                evidence = None
                if evidence_items:
                    evidence_choice = st.selectbox(
                        "Evidence",
                        list(range(len(evidence_items))),
                        format_func=lambda idx: f"Page {evidence_items[idx].get('page')}",
                        key=f"evidence-{current['proposal_id']}",
                    )
                    evidence = evidence_items[evidence_choice]
                    st.write("Quote:", evidence.get("quote"))
                    st.write("Page:", evidence.get("page"))

                review = reviews.get(current["proposal_id"])
                manual_value_default = (
                    review["final_value"] if review and review["final_value"] else current.get("proposed_value") or ""
                )
                manual_value = st.text_input(
                    "Proposed value (editable)",
                    value=manual_value_default,
                    key=f"manual-{current['proposal_id']}",
                )
                note = st.text_area(
                    "Note",
                    value=review["note"] if review else "",
                    key=f"note-{current['proposal_id']}",
                )

                col_accept, col_accept_edit, col_reject, col_revise = st.columns(4)
                with col_accept:
                    if st.button("Accept", key=f"accept-{current['proposal_id']}"):
                        store.insert_review(
                            {
                                "review_id": current["proposal_id"],
                                "proposal_id": current["proposal_id"],
                                "decision": "accepted",
                                "final_value": current.get("proposed_value"),
                                "note": note,
                            }
                        )
                        st.success("Accepted")
                with col_accept_edit:
                    if st.button("Accept with manual edit", key=f"accept-edit-{current['proposal_id']}"):
                        store.insert_review(
                            {
                                "review_id": current["proposal_id"],
                                "proposal_id": current["proposal_id"],
                                "decision": "accepted",
                                "final_value": manual_value,
                                "note": note,
                            }
                        )
                        st.success("Accepted with manual edit")
                with col_reject:
                    if st.button("Reject", key=f"reject-{current['proposal_id']}"):
                        store.insert_review(
                            {
                                "review_id": current["proposal_id"],
                                "proposal_id": current["proposal_id"],
                                "decision": "rejected",
                                "final_value": "",
                                "note": note,
                            }
                        )
                        st.warning("Rejected")
                with col_revise:
                    if st.button("Revise", key=f"revise-{current['proposal_id']}"):
                        store.insert_review(
                            {
                                "review_id": current["proposal_id"],
                                "proposal_id": current["proposal_id"],
                                "decision": "revise",
                                "final_value": "",
                                "note": note,
                            }
                        )
                        store.record_event(
                            "info",
                            "revise_request",
                            {
                                "proposal_id": current["proposal_id"],
                                "row_id": row_id,
                                "column": current["column"],
                                "note": note,
                            },
                        )
                        st.info("Revision requested")

                pdf_map = {row["pdf_id"]: row["path"] for row in store.list_pdfs()}
                with st.sidebar:
                    st.subheader("Evidence preview")
                    pdf_path = pdf_map.get(current.get("pdf_id"))
                    if pdf_path and evidence and evidence.get("page"):
                        rects = evidence.get("rects") or []
                        if not rects:
                            highlight = locate_quote(
                                pdf_path,
                                evidence.get("quote") or "",
                                int(evidence["page"]),
                                locator_hint=evidence.get("locator_hint"),
                            )
                            rects = highlight.rects
                            if not rects:
                                st.warning("No highlight rectangles available for this evidence.")
                        image = render_page_image(pdf_path, int(evidence["page"]), rects)
                        st.image(image, caption=f"PDF page {evidence['page']}")
                    else:
                        st.info("Select evidence with a page to preview the PDF.")


with export_tab:
    st.header("Export")
    runs = st.session_state.get("runs", [])
    run_labels = [run.label for run in runs]
    selected_label = st.selectbox("Run", run_labels) if run_labels else None
    if st.button("Export") and selected_label:
        run_dir = runs[run_labels.index(selected_label)].run_dir
        export_run(Path(run_dir))
        st.success("Export completed")


with debug_tab:
    st.header("Retrieval Debug")
    runs = st.session_state.get("runs", [])
    run_labels = [run.label for run in runs]
    selected_label = st.selectbox("Run", run_labels, key="debug-run") if run_labels else None
    if selected_label:
        run_dir = runs[run_labels.index(selected_label)].run_dir
        store = Store.init_db(run_dir / "proposals.sqlite")
        pdfs = store.list_pdfs()
        pdf_options = {pdf["pdf_id"]: pdf["pdf_id"] for pdf in pdfs}
        pdf_id = st.selectbox("PDF", list(pdf_options.keys()), key="debug-pdf") if pdf_options else None
        run_config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
        specs = load_schema(Path(run_config["table_path"]), run_config["schema_sheet_name"])
        column_options = [spec.column_name for spec in specs]
        column = st.selectbox("Column", column_options, key="debug-column") if column_options else None
        query_mode = st.selectbox(
            "Query preset",
            ["Column name", "Column description", "Column name + description"],
            key="debug-query-mode",
        )
        query = None
        if column:
            description = next((spec.description for spec in specs if spec.column_name == column), "")
            if query_mode == "Column name":
                query = column
            elif query_mode == "Column description":
                query = description
            else:
                query = f"{column}: {description}"
        if st.button("Retrieve") and run_dir and pdf_id and query:
            index = load_index(Path(run_dir) / "artifacts" / "retrieval_indexes" / pdf_id)
            if not index:
                st.error("Retrieval index not found for that PDF.")
            else:
                context = retrieve_context(index, query, RetrievalConfig())
                for chunk in context.chunks:
                    st.write(
                        chunk.chunk_id,
                        f"score {chunk.score:.3f}",
                        f"pages {chunk.page_start}-{chunk.page_end}",
                    )
                    st.code(chunk.text[:800])
