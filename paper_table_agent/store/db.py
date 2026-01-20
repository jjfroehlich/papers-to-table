from __future__ import annotations

import json
import sqlite3
import uuid
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
        conn = sqlite3.connect(path, check_same_thread=False)
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

    def insert_pdf_metadata(
        self,
        pdf_id: str,
        title: str | None,
        authors: list[str],
        year: str | None,
        evidence: list[dict[str, Any]],
        confidence: float | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO pdf_metadata
            (pdf_id, title, authors, year, confidence, evidence_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pdf_id,
                title,
                ", ".join(authors),
                year,
                confidence,
                json.dumps(evidence),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    def insert_match_candidates(self, candidates: Iterable[dict[str, Any]]) -> None:
        payload = [
            (
                str(uuid.uuid4()),
                candidate.get("pdf_id"),
                candidate.get("row_id"),
                candidate.get("score"),
                candidate.get("title"),
                candidate.get("authors"),
                candidate.get("year"),
                candidate.get("rank"),
                candidate.get("source"),
                datetime.utcnow().isoformat(),
            )
            for candidate in candidates
        ]
        if not payload:
            return
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO match_candidates
            (candidate_id, pdf_id, row_id, score, title, authors, year, rank, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        self.conn.commit()

    def insert_retrieval_chunks(self, pdf_id: str, chunks: Iterable[dict[str, Any]]) -> None:
        payload = [
            (
                pdf_id,
                chunk.get("chunk_id"),
                chunk.get("text"),
                chunk.get("page_start"),
                chunk.get("page_end"),
                chunk.get("source"),
                datetime.utcnow().isoformat(),
            )
            for chunk in chunks
        ]
        if not payload:
            return
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO retrieval_chunks
            (pdf_id, chunk_id, text, page_start, page_end, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
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

    def update_proposal_evidence(
        self,
        proposal_id: str,
        evidence: list[dict[str, Any]],
        flags: dict[str, Any] | None = None,
    ) -> None:
        if flags is None:
            existing = self.conn.execute(
                "SELECT flags_json FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            flags_payload = json.loads(existing["flags_json"] or "{}") if existing else {}
        else:
            flags_payload = flags
        self.conn.execute(
            "UPDATE proposals SET evidence_json = ?, flags_json = ? WHERE proposal_id = ?",
            (json.dumps(evidence), json.dumps(flags_payload), proposal_id),
        )
        self.conn.commit()

    def update_proposal_flags(self, proposal_id: str, flags: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE proposals SET flags_json = ? WHERE proposal_id = ?",
            (json.dumps(flags), proposal_id),
        )
        self.conn.commit()

    def fetch_rows(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM rows"))

    def fetch_proposals_for_row(self, row_id: str) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM proposals WHERE row_id = ?", (row_id,)))

    def fetch_matches(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM matches"))

    def fetch_match_candidates(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM match_candidates"))

    def fetch_pdf_metadata(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM pdf_metadata"))

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
