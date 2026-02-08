from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from paper_table_agent.graph.evaluation import evaluate_run
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.store.db import Store


def _write_table(path: Path) -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Title": "Synthetic MPRA Study",
                "Variants": "48,391",
                "Method": "",
            }
        ]
    )
    dataframe.to_csv(path, index=False)


def _seed_audit_proposal(run_dir: Path, proposal_kind: str, column: str, value: str) -> None:
    store = Store.init_db(run_dir / "proposals.sqlite")
    store.insert_proposals(
        [
            {
                "proposal_id": "proposal-1",
                "pdf_id": "pdf-1",
                "row_id": "0",
                "column": column,
                "proposed_value": value,
                "status": "found",
                "confidence": 0.9,
                "evidence": [
                    {
                        "quote": "We tested 48,391 variants.",
                        "page": 1,
                        "highlight_status": "highlighted",
                        "rects": [[10.0, 10.0, 100.0, 20.0]],
                    }
                ],
                "reasoning": "Matched fixture text.",
                "flags": {"proposal_kind": proposal_kind},
            }
        ]
    )


def test_eval_harness_metrics_and_run_report_update(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    table_path = run_dir / "table.csv"
    _write_table(table_path)
    (run_dir / "run_config.json").write_text(
        json.dumps(
            {
                "table_path": str(table_path),
                "schema_sheet_name": "schema",
                "pdf_folder": str(run_dir),
                "audit": {"use_filled_cells_as_gold": True},
                "provider": {"model_extract": "stub-model"},
                "retrieval": {"max_context_tokens": 1200},
            }
        ),
        encoding="utf-8",
    )
    _seed_audit_proposal(run_dir, "audit", "Variants", "48,391")
    parsed_dir = run_dir / "artifacts" / "parsed"
    parsed_dir.mkdir(parents=True)
    (parsed_dir / "pdf-1_pymupdf.json").write_text(
        json.dumps(
            {
                "pdf_id": "pdf-1",
                "page_text": ["We tested 48,391 variants."],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_report.json").write_text(json.dumps({"summary": {}}), encoding="utf-8")

    payload = evaluate_run(
        run_dir=run_dir,
        db_path=run_dir / "proposals.sqlite",
        table_path=table_path,
        schema_sheet_name=None,
        pdf_folder=None,
        output_dir=run_dir / "exports",
    )

    assert payload["summary"]["match_rate"] == 1.0
    assert payload["summary"]["anchorable_quote_rate"] == 1.0

    run_report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    assert run_report["summary"]["evaluation"]["match_rate"] == 1.0
    assert (run_dir / "exports" / "proposal_eval.json").exists()
    assert (run_dir / "exports" / "proposal_eval.md").exists()


def test_export_skips_audit_proposals(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    table_path = run_dir / "table.csv"
    _write_table(table_path)
    (run_dir / "run_config.json").write_text(
        json.dumps(
            {
                "table_path": str(table_path),
                "schema_sheet_name": "schema",
                "pdf_folder": str(run_dir),
            }
        ),
        encoding="utf-8",
    )
    store = Store.init_db(run_dir / "proposals.sqlite")
    store.insert_proposals(
        [
            {
                "proposal_id": "audit-1",
                "pdf_id": "pdf-1",
                "row_id": "0",
                "column": "Variants",
                "proposed_value": "100",
                "status": "found",
                "confidence": 0.9,
                "evidence": [],
                "reasoning": "",
                "flags": {"proposal_kind": "audit"},
            },
            {
                "proposal_id": "fill-1",
                "pdf_id": "pdf-1",
                "row_id": "0",
                "column": "Method",
                "proposed_value": "plasmid-based MPRA",
                "status": "found",
                "confidence": 0.9,
                "evidence": [],
                "reasoning": "",
                "flags": {},
            },
        ]
    )
    store.insert_review(
        {
            "review_id": "review-audit",
            "proposal_id": "audit-1",
            "decision": "accepted",
            "final_value": "100",
        }
    )
    store.insert_review(
        {
            "review_id": "review-fill",
            "proposal_id": "fill-1",
            "decision": "accepted",
            "final_value": "plasmid-based MPRA",
        }
    )

    export_run(run_dir)

    updated = pd.read_excel(run_dir / "exports" / "updated_table.xlsx")
    assert updated.at[0, "Variants"] == "48,391"
    assert updated.at[0, "Method"] == "plasmid-based MPRA"
