from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.io.schema import load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.pdf.highlight import locate_quote, render_page_image
from paper_table_agent.store.db import Store
from paper_table_agent.ui.defaults import load_default_run_config, resolve_default_paths
from paper_table_agent.ui.registry import discover_runs

st.set_page_config(page_title="Paper Table Agent", layout="wide")

DEFAULT_CONFIG_PATH = Path("run_config.json")

st.title("Paper Table Agent")

run_tab, review_tab = st.tabs(["Run", "Review"])


def _normalize_column_name(value: object) -> str:
    return str(value).replace("\u00a0", " ").strip()


def _build_column_map(columns: Iterable[object]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for col in columns:
        normalized = _normalize_column_name(col)
        if normalized and normalized not in mapping:
            mapping[normalized] = col
    return mapping


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


def _run_progress(store: Store) -> tuple[float, str | None]:
    pdfs = [dict(row) for row in store.list_pdfs()]
    if not pdfs:
        return 0.0, None
    processed = sum(1 for pdf in pdfs if pdf.get("status") in {"processed", "failed"})
    total = len(pdfs)
    pending = next((pdf for pdf in pdfs if pdf.get("status") == "parsed"), None)
    progress = processed / total if total else 0.0
    current_name = Path(pending["path"]).name if pending and pending.get("path") else None
    return progress, current_name


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


def _next_undecided_index(proposals: list[dict[str, Any]], reviews: dict[str, dict[str, Any]]) -> int | None:
    for idx, proposal in enumerate(proposals):
        if proposal["proposal_id"] not in reviews:
            return idx
    return None


def _advance_row_column(
    row_index: int,
    column_index: int,
    total_rows: int,
    total_columns: int,
) -> tuple[int, int]:
    if total_columns == 0:
        return row_index, column_index
    next_column = min(column_index + 1, total_columns - 1)
    if column_index < total_columns - 1:
        return row_index, next_column
    next_row = min(row_index + 1, total_rows - 1)
    return next_row, 0


if "default_config" not in st.session_state:
    st.session_state["default_config"] = load_default_run_config(DEFAULT_CONFIG_PATH)

if "runs" not in st.session_state:
    st.session_state["runs"] = discover_runs()

if "selected_run_dir" not in st.session_state:
    st.session_state["selected_run_dir"] = None

if "review_auto_advance" not in st.session_state:
    st.session_state["review_auto_advance"] = True


default_config = st.session_state.get("default_config", {})
config_table, config_pdf = resolve_default_paths(default_config)

with run_tab:
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

    run_col, resume_col = st.columns([1, 1])
    with run_col:
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

    resumable = [run for run in st.session_state.get("runs", []) if run.status in {"paused", "in_progress"}]
    with resume_col:
        if resumable:
            resume_label = st.selectbox(
                "Resume run",
                options=[run.label for run in resumable],
                key="resume-run",
            )
            if st.button("Resume", key="resume-run-button"):
                selected_run = resumable[[run.label for run in resumable].index(resume_label)]
                config_path = selected_run.run_dir / "run_config.json"
                config = RunConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
                store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
                run_workflow(
                    config=config,
                    run_paths=RunPaths(run_dir=selected_run.run_dir),
                    store=store,
                    resume=True,
                )
                st.session_state["selected_run_dir"] = selected_run.run_dir
                st.session_state["runs"] = discover_runs()
                st.success(f"Resumed run: {selected_run.run_dir}")
        else:
            st.caption("No resumable runs found.")

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
        st.write(f"Status: **{selected_run.status}**")
        store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
        progress, current_pdf = _run_progress(store)
        st.progress(progress)
        st.write("Current PDF:", current_pdf or "—")


with review_tab:
    st.header("Review")
    runs = [run for run in st.session_state.get("runs", []) if run.status == "completed"]
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
        run_config = json.loads((selected_run.run_dir / "run_config.json").read_text(encoding="utf-8"))
        table = load_table(Path(run_config["table_path"]))
        column_map = _build_column_map(list(table.dataframe.columns))
        schema_source = Path(run_config["table_path"])
        if run_config.get("schema_mode") == "separate" and run_config.get("schema_path"):
            schema_source = Path(run_config["schema_path"])
        specs = load_schema(schema_source, run_config["schema_sheet_name"])
        columns = [spec.column_name for spec in specs]

        proposals_meta = [dict(row) for row in store.conn.execute(
            "SELECT proposal_id, row_id, pdf_id, column, status, confidence, proposed_value, flags_json, evidence_json "
            "FROM proposals"
        )]
        for proposal in proposals_meta:
            proposal["flags"] = json.loads(proposal.get("flags_json") or "{}")
            proposal["evidence"] = json.loads(proposal.get("evidence_json") or "[]")

        reviews = store.fetch_reviews()
        rows = [dict(row) for row in store.fetch_rows()]
        rows.sort(key=lambda row: row.get("row_index", 0))

        remaining = sum(1 for proposal in proposals_meta if proposal["proposal_id"] not in reviews)
        st.caption(f"Remaining items: {remaining}")

        if not rows:
            st.info("No rows found for this run.")
        else:
            if "selected_row_index" not in st.session_state:
                st.session_state["selected_row_index"] = 0
            if st.session_state["selected_row_index"] >= len(rows):
                st.session_state["selected_row_index"] = 0

            row_nav1, row_nav2, row_nav3 = st.columns([1, 1, 2])
            with row_nav1:
                if st.button("Prev row"):
                    st.session_state["selected_row_index"] = max(0, st.session_state["selected_row_index"] - 1)
            with row_nav2:
                if st.button("Next row"):
                    st.session_state["selected_row_index"] = min(
                        len(rows) - 1,
                        st.session_state["selected_row_index"] + 1,
                    )
            with row_nav3:
                current_position = st.session_state["selected_row_index"] + 1
                st.caption(f"Row {current_position} of {len(rows)}")

            row_data = rows[st.session_state["selected_row_index"]]
            row_id = row_data["row_id"]

            row_proposals = [proposal for proposal in proposals_meta if proposal.get("row_id") == row_id]
            if columns:
                column_order = {name: idx for idx, name in enumerate(columns)}
                row_proposals.sort(key=lambda item: column_order.get(item.get("column", ""), 9999))
            else:
                row_proposals.sort(key=lambda item: item.get("column", ""))

            if not row_proposals:
                st.info("No proposals for this row.")
            else:
                index_key = f"proposal-index-{row_id}"
                if index_key not in st.session_state:
                    st.session_state[index_key] = 0
                if st.session_state[index_key] >= len(row_proposals):
                    st.session_state[index_key] = 0

                current_index = st.session_state[index_key]
                current = row_proposals[current_index]

                col_left, col_right = st.columns([1.1, 1.4])
                with col_left:
                    st.subheader("Row context")
                    context_payload = {
                        "Title": row_data.get("title"),
                        "Authors": row_data.get("authors"),
                        "Year": row_data.get("year"),
                    }
                    for col in columns[:3]:
                        normalized = _normalize_column_name(col)
                        resolved = column_map.get(normalized)
                        if resolved is not None:
                            context_payload[col] = table.dataframe.loc[row_data["row_index"], resolved]
                    st.write(context_payload)

                    st.subheader("Proposal")
                    st.markdown(f"### {current['column']}")
                    review = reviews.get(current["proposal_id"])
                    state = _proposal_state(current, review)
                    if state == "needs_more_evidence":
                        st.caption("⚠️ Needs more evidence")
                    st.write("Proposed value:", current.get("proposed_value"))
                    st.write("Confidence:", current.get("confidence"))

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

                    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 2])
                    with nav_col1:
                        if st.button("Prev column", key=f"prev-col-{row_id}"):
                            st.session_state[index_key] = max(current_index - 1, 0)
                    with nav_col2:
                        if st.button("Next column", key=f"next-col-{row_id}"):
                            st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)
                    with nav_col3:
                        if st.button("Next undecided", key=f"next-undecided-{row_id}"):
                            undecided = _next_undecided_index(row_proposals, reviews)
                            if undecided is not None:
                                st.session_state[index_key] = undecided

                    st.session_state["review_auto_advance"] = st.toggle(
                        "Auto-advance",
                        value=st.session_state["review_auto_advance"],
                        key="review_auto_advance",
                    )

                    decision_cols = st.columns(3)
                    with decision_cols[0]:
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
                            if st.session_state["review_auto_advance"]:
                                next_row, next_col = _advance_row_column(
                                    st.session_state["selected_row_index"],
                                    current_index,
                                    len(rows),
                                    len(row_proposals),
                                )
                                st.session_state["selected_row_index"] = next_row
                                st.session_state[index_key] = next_col
                    with decision_cols[1]:
                        if st.button("Accept with edit", key=f"accept-edit-{current['proposal_id']}"):
                            store.insert_review(
                                {
                                    "review_id": current["proposal_id"],
                                    "proposal_id": current["proposal_id"],
                                    "decision": "accepted",
                                    "final_value": manual_value,
                                    "note": note,
                                }
                            )
                            st.success("Accepted with edit")
                            if st.session_state["review_auto_advance"]:
                                next_row, next_col = _advance_row_column(
                                    st.session_state["selected_row_index"],
                                    current_index,
                                    len(rows),
                                    len(row_proposals),
                                )
                                st.session_state["selected_row_index"] = next_row
                                st.session_state[index_key] = next_col
                    with decision_cols[2]:
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
                            if st.session_state["review_auto_advance"]:
                                next_row, next_col = _advance_row_column(
                                    st.session_state["selected_row_index"],
                                    current_index,
                                    len(rows),
                                    len(row_proposals),
                                )
                                st.session_state["selected_row_index"] = next_row
                                st.session_state[index_key] = next_col

                with col_right:
                    st.subheader("PDF viewer")
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
                            st.image(image, caption=f"PDF page {evidence['page']}")
                            if not rects:
                                if st.button("Try re-locate", key=f"relocate-{current['proposal_id']}"):
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
                                    highlight = locate_quote(
                                        pdf_path,
                                        evidence.get("quote", ""),
                                        int(evidence.get("page", 1)),
                                        locator_hint=evidence.get("locator_hint"),
                                        tokens=tokens,
                                    )
                                    evidence["rects"] = highlight.rects
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
