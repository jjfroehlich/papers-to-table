from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from paper_table_agent.io.xlsx import load_table, write_table_copy
from paper_table_agent.store.db import Store


def export_run(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    store = Store.init_db(run_dir / "proposals.sqlite")
    run_config_path = run_dir / "run_config.json"
    config = json.loads(run_config_path.read_text(encoding="utf-8"))
    table = load_table(Path(config["table_path"]))

    reviews = store.fetch_reviews()
    proposals = store.conn.execute("SELECT * FROM proposals").fetchall()
    for proposal in proposals:
        review = reviews.get(proposal["proposal_id"])
        if not review:
            continue
        if review["decision"] != "accepted":
            continue
        row_index = int(proposal["row_id"])
        final_value = review["final_value"] or proposal["proposed_value"]
        table.dataframe.at[row_index, proposal["column"]] = str(final_value) if final_value is not None else ""

    exports_dir = run_dir / "exports"
    write_table_copy(table, exports_dir / "updated_table.xlsx")

    _export_audit(store, exports_dir / "audit_log.csv")
    _export_proposals(store, exports_dir / "proposals.jsonl")


def _export_audit(store: Store, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proposals = store.conn.execute("SELECT * FROM proposals").fetchall()
    reviews = store.fetch_reviews()
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "proposal_id",
                "pdf_id",
                "row_id",
                "column",
                "old_value",
                "proposed_value",
                "decision",
                "final_value",
                "evidence_json",
            ]
        )
        for proposal in proposals:
            review = reviews.get(proposal["proposal_id"])
            writer.writerow(
                [
                    proposal["proposal_id"],
                    proposal["pdf_id"],
                    proposal["row_id"],
                    proposal["column"],
                    "",
                    proposal["proposed_value"],
                    review["decision"] if review else "",
                    review["final_value"] if review else "",
                    proposal["evidence_json"],
                ]
            )


def _export_proposals(store: Store, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proposals = store.conn.execute("SELECT * FROM proposals").fetchall()
    with output_path.open("w", encoding="utf-8") as handle:
        for proposal in proposals:
            handle.write(json.dumps(dict(proposal)) + "\n")
