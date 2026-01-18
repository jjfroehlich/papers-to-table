from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from paper_table_agent.config import RunConfig, create_run_paths, load_prompt_versions, capture_run_config
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.runner import run_pipeline
from paper_table_agent.store.db import Store

st.set_page_config(page_title="Paper Table Agent", layout="wide")

st.title("Paper Table Agent")

run_tab, review_tab, export_tab, debug_tab = st.tabs(["Run", "Review", "Export", "Advanced"])

with run_tab:
    st.header("Start a Run")
    table_path = st.text_input("Table path", value="")
    pdf_folder = st.text_input("PDF folder", value="")
    schema_sheet = st.text_input("Schema sheet", value="schema")
    title_col = st.text_input("Title column", value="")
    authors_col = st.text_input("Authors column", value="")
    year_col = st.text_input("Year column", value="")
    if st.button("Start run"):
        config = RunConfig(
            table_path=Path(table_path),
            pdf_folder=Path(pdf_folder),
            schema_sheet_name=schema_sheet,
            title_col=title_col or None,
            authors_col=authors_col or None,
            year_col=year_col or None,
        )
        run_paths = create_run_paths(config.table_path)
        prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
        capture_run_config(config, run_paths, prompt_versions)
        store = Store.init_db(run_paths.db_path)
        run_pipeline(config=config, run_paths=run_paths, store=store)
        st.success(f"Run completed: {run_paths.run_dir}")

with review_tab:
    st.header("Review Proposals")
    run_dir = st.text_input("Run directory", value="")
    if run_dir:
        store = Store.init_db(Path(run_dir) / "proposals.sqlite")
        rows = store.fetch_rows()
        row_ids = [row["row_id"] for row in rows]
        selection = st.selectbox("Row", row_ids)
        proposals = store.fetch_proposals_for_row(selection)
        reviews = store.fetch_reviews()
        for proposal in proposals:
            st.subheader(f"{proposal['column']}")
            st.write("Proposed:", proposal["proposed_value"])
            st.write("Evidence:", proposal["evidence_json"])
            decision = st.radio(
                "Decision",
                ["pending", "accepted", "rejected", "revised"],
                index=0,
                key=f"decision-{proposal['proposal_id']}",
            )
            final_value = st.text_input(
                "Final value",
                value=reviews.get(proposal["proposal_id"], {}).get("final_value", ""),
                key=f"final-{proposal['proposal_id']}",
            )
            if st.button("Save", key=f"save-{proposal['proposal_id']}"):
                store.insert_review(
                    {
                        "review_id": proposal["proposal_id"],
                        "proposal_id": proposal["proposal_id"],
                        "decision": decision,
                        "final_value": final_value,
                        "note": "",
                    }
                )
                st.success("Saved")

with export_tab:
    st.header("Export")
    export_run_dir = st.text_input("Run directory to export", value="")
    if st.button("Export") and export_run_dir:
        export_run(Path(export_run_dir))
        st.success("Export completed")

with debug_tab:
    st.header("Retrieval Debug")
    st.write("Provide a run directory and PDF ID to inspect retrieval chunks.")
    run_dir = st.text_input("Run dir", value="", key="debug-run-dir")
    pdf_id = st.text_input("PDF ID", value="", key="debug-pdf-id")
    query = st.text_input("Query", value="", key="debug-query")
    if st.button("Retrieve") and run_dir and pdf_id and query:
        from paper_table_agent.retrieval.index import build_index
        from paper_table_agent.retrieval.chunking import build_chunks
        from paper_table_agent.retrieval.retrieve import retrieve

        parsed_path = Path(run_dir) / "artifacts" / "parsed" / f"{pdf_id}_pymupdf.json"
        if not parsed_path.exists():
            st.error("Parsed PDF artifact not found")
        else:
            payload = json.loads(parsed_path.read_text(encoding="utf-8"))
            chunks = build_chunks(payload["page_text"])
            index = build_index(chunks)
            results = retrieve(index, query)
            for result in results:
                st.write(result.chunk_id, result.score, f"pages {result.page_start}-{result.page_end}")
                st.code(result.text[:800])
