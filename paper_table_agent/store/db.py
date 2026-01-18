from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Store:
    conn: sqlite3.Connection

    @classmethod
    def init_db(cls, path: Path) -> "Store":
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        schema_path = Path(__file__).with_name("schema.sql")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        return cls(conn=conn)

    def insert_pdf(self, pdf_id: str, path: str, sha1: str, status: str = "pending") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pdfs (pdf_id, path, sha1, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (pdf_id, path, sha1, status, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def update_pdf_status(
        self,
        pdf_id: str,
        status: str,
        error: str | None = None,
        n_pages: int | None = None,
        parse_source: str | None = None,
    ) -> None:
        if parse_source is None:
            self.conn.execute(
                "UPDATE pdfs SET status = ?, error = ?, n_pages = ? WHERE pdf_id = ?",
                (status, error, n_pages, pdf_id),
            )
        else:
            self.conn.execute(
                "UPDATE pdfs SET status = ?, error = ?, n_pages = ?, parse_source = ? WHERE pdf_id = ?",
                (status, error, n_pages, parse_source, pdf_id),
            )
        self.conn.commit()

    def list_pdfs(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM pdfs"))

    def insert_rows(self, rows: Iterable[dict[str, Any]]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO rows (row_id, row_index, title, authors, year, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    row["row_id"],
                    row["row_index"],
                    row.get("title"),
                    row.get("authors"),
                    row.get("year"),
                    row.get("status", "ready"),
                )
                for row in rows
            ],
        )
        self.conn.commit()

    def insert_locks(self, locks: Iterable[dict[str, Any]]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO locks (row_id, column, locked, reason) VALUES (?, ?, ?, ?)",
            [(lock["row_id"], lock["column"], lock["locked"], lock.get("reason")) for lock in locks],
        )
        self.conn.commit()

    def insert_match(self, match: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO matches
            (match_id, pdf_id, row_id, confidence, status, evidence_json, rationale, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match["match_id"],
                match["pdf_id"],
                match.get("row_id"),
                match.get("confidence"),
                match.get("status"),
                json.dumps(match.get("evidence")),
                match.get("rationale"),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    def update_match_status(self, match_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE matches SET status = ? WHERE match_id = ?",
            (status, match_id),
        )
        self.conn.commit()

    def insert_proposals(self, proposals: Iterable[dict[str, Any]]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO proposals
            (proposal_id, pdf_id, row_id, column, proposed_value, status, confidence, evidence_json, reasoning, flags_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    proposal["proposal_id"],
                    proposal["pdf_id"],
                    proposal["row_id"],
                    proposal["column"],
                    proposal.get("proposed_value"),
                    proposal.get("status"),
                    proposal.get("confidence"),
                    json.dumps(proposal.get("evidence", [])),
                    proposal.get("reasoning"),
                    json.dumps(proposal.get("flags", {})),
                    datetime.utcnow().isoformat(),
                )
                for proposal in proposals
            ],
        )
        self.conn.commit()

    def insert_review(self, review: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO reviews
            (review_id, proposal_id, decision, final_value, note, reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                review["review_id"],
                review["proposal_id"],
                review.get("decision"),
                review.get("final_value"),
                review.get("note"),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    def fetch_rows(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM rows"))

    def fetch_proposals_for_row(self, row_id: str) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM proposals WHERE row_id = ?", (row_id,)))

    def fetch_matches(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM matches"))

    def fetch_reviews(self) -> dict[str, sqlite3.Row]:
        rows = self.conn.execute("SELECT * FROM reviews")
        return {row["proposal_id"]: row for row in rows}

    def list_locks(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM locks"))

    def record_event(self, level: str, event_type: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO events (event_id, level, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                f"{event_type}-{datetime.utcnow().timestamp()}",
                level,
                event_type,
                json.dumps(payload),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()
