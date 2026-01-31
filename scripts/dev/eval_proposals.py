from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _load_proposals(db_path: Path) -> list[dict[str, object]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute("SELECT evidence_json, flags_json, proposed_value FROM proposals"))
    conn.close()
    proposals = []
    for row in rows:
        evidence = json.loads(row["evidence_json"] or "[]")
        flags = json.loads(row["flags_json"] or "{}")
        proposals.append(
            {
                "evidence": evidence,
                "flags": flags,
                "proposed_value": row["proposed_value"],
            }
        )
    return proposals


def _metrics(proposals: list[dict[str, object]]) -> dict[str, object]:
    total = len(proposals)
    evidence_items_total = 0
    highlighted_items = 0
    proposals_with_evidence = 0
    proposals_with_highlight = 0
    proposals_with_value = 0
    for proposal in proposals:
        evidence = proposal.get("evidence") or []
        if proposal.get("proposed_value"):
            proposals_with_value += 1
        if evidence:
            proposals_with_evidence += 1
        has_highlight = False
        for item in evidence:
            evidence_items_total += 1
            status = item.get("highlight_status")
            rects = item.get("rects") or []
            if status == "highlighted" or rects:
                highlighted_items += 1
                has_highlight = True
        if has_highlight:
            proposals_with_highlight += 1
    highlight_rate = (highlighted_items / evidence_items_total) if evidence_items_total else 0.0
    return {
        "proposals_total": total,
        "proposals_with_value": proposals_with_value,
        "proposals_with_evidence": proposals_with_evidence,
        "proposals_with_highlight": proposals_with_highlight,
        "evidence_items_total": evidence_items_total,
        "highlight_rate": round(highlight_rate, 4),
        "avg_evidence_items_per_proposal": round((evidence_items_total / total), 3) if total else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate proposal evidence + highlight coverage.")
    parser.add_argument("db", type=Path, help="Path to proposals.sqlite")
    args = parser.parse_args()
    proposals = _load_proposals(args.db)
    metrics = _metrics(proposals)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
