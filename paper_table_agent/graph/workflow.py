from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from paper_table_agent.config import RunConfig, RunPaths
from paper_table_agent.graph.checkpoint import SqliteSaver
from paper_table_agent.graph.reporting import write_mapping_report, write_run_report
from paper_table_agent.graph.runner import PdfRecord, prepare_context, process_pdf, _stop_requested
from paper_table_agent.store.db import Store


class WorkflowState(TypedDict):
    pdf_index: int
    pdf_ids: list[str]
    done: bool


def run_workflow(config: RunConfig, run_paths: RunPaths, store: Store, resume: bool = False) -> None:
    context, pdfs = prepare_context(config, run_paths, store)
    pdf_ids = [pdf.pdf_id for pdf in pdfs]
    pdf_map = {pdf.pdf_id: pdf for pdf in pdfs}
    existing_pdfs = {row["pdf_id"]: row for row in store.list_pdfs()}

    def init_state(_: WorkflowState) -> WorkflowState:
        return {"pdf_index": 0, "pdf_ids": pdf_ids, "done": False}

    def process_next(state: WorkflowState) -> WorkflowState:
        if _stop_requested(run_paths):
            return {"pdf_index": state["pdf_index"], "pdf_ids": state["pdf_ids"], "done": True}
        if state["pdf_index"] >= len(state["pdf_ids"]):
            return {"pdf_index": state["pdf_index"], "pdf_ids": state["pdf_ids"], "done": True}
        pdf_id = state["pdf_ids"][state["pdf_index"]]
        pdf_record: PdfRecord = pdf_map[pdf_id]
        processed = process_pdf(context, pdf_record, existing_pdfs)
        if processed:
            existing_pdfs[pdf_id] = {"status": "processed"}
        return {
            "pdf_index": state["pdf_index"] + 1,
            "pdf_ids": state["pdf_ids"],
            "done": False,
        }

    def should_continue(state: WorkflowState) -> str:
        if state["done"]:
            return "done"
        if state["pdf_index"] >= len(state["pdf_ids"]):
            return "done"
        return "continue"

    graph = StateGraph(WorkflowState)
    graph.add_node("init", init_state)
    graph.add_node("process_next", process_next)
    graph.set_entry_point("init")
    graph.add_edge("init", "process_next")
    graph.add_conditional_edges(
        "process_next",
        should_continue,
        {"continue": "process_next", "done": END},
    )
    checkpoint_path = run_paths.run_dir / "checkpoints.sqlite"
    checkpointer = SqliteSaver(checkpoint_path)
    compiled = graph.compile(checkpointer=checkpointer)
    config_payload = {"configurable": {"thread_id": run_paths.run_dir.name}}
    if resume:
        try:
            compiled.invoke(None, config=config_payload)
            write_mapping_report(store, run_paths.exports_dir, write_reports=config.output.debug_reports)
            status = write_run_report(store, run_paths)
            _mark_run_finished(run_paths, status)
            return
        except Exception:
            compiled.invoke({"pdf_index": 0, "pdf_ids": pdf_ids, "done": False}, config=config_payload)
            write_mapping_report(store, run_paths.exports_dir, write_reports=config.output.debug_reports)
            status = write_run_report(store, run_paths)
            _mark_run_finished(run_paths, status)
            return
    compiled.invoke({"pdf_index": 0, "pdf_ids": pdf_ids, "done": False}, config=config_payload)
    write_mapping_report(store, run_paths.exports_dir, write_reports=config.output.debug_reports)
    status = write_run_report(store, run_paths)
    _mark_run_finished(run_paths, status)


def _mark_run_finished(run_paths: RunPaths, status: str) -> None:
    if (run_paths.run_dir / "STOP").exists():
        return
    if (run_paths.run_dir / "PAUSE").exists():
        return
    if status == "failed" or (run_paths.run_dir / "FAILED").exists():
        return
    (run_paths.run_dir / "COMPLETED").write_text("done", encoding="utf-8")
