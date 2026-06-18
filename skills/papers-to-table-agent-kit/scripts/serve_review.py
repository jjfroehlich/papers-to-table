#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_review_decisions import apply_decisions, write_latest_decisions  # noqa: E402
from review_package_common import (  # noqa: E402
    DECISIONS,
    decisions_path,
    evidence_path,
    latest_decisions,
    proposals_path,
    read_json,
    read_jsonl,
    resolve_input_path,
    review_index_path,
    review_package_path,
    stable_id,
    utc_now,
)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _safe_path(root: Path, request_path: str) -> Path | None:
    parsed = urlparse(request_path)
    rel = unquote(parsed.path.lstrip("/"))
    if not rel:
        rel = "human_review/index.html"
    if rel in {"review", "human_review"}:
        rel = "human_review/index.html"
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _review_package(run_dir: Path) -> dict[str, Any]:
    payload = read_json(review_package_path(run_dir))
    if not isinstance(payload, dict):
        raise ValueError("human_review/review_package.json must contain an object.")
    return payload


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_title(row: dict[str, Any] | None, pdf: dict[str, Any] | None) -> str | None:
    values = row.get("values") if isinstance(row, dict) and isinstance(row.get("values"), dict) else {}
    for key in ("Title", "title", "paper_title", "Paper", "paper"):
        value = _text_value(values.get(key))
        if value:
            return value
    return _text_value(pdf.get("title") if pdf else None) or _text_value(row.get("paper_label") if row else None)


def _row_authors(row: dict[str, Any] | None, pdf: dict[str, Any] | None) -> str | None:
    values = row.get("values") if isinstance(row, dict) and isinstance(row.get("values"), dict) else {}
    authors = values.get("Authors") or values.get("authors") or (pdf.get("authors") if pdf else None)
    if isinstance(authors, list):
        return "; ".join(str(item) for item in authors if _text_value(item))
    return _text_value(authors)


def _row_year(row: dict[str, Any] | None, pdf: dict[str, Any] | None) -> str | int | None:
    values = row.get("values") if isinstance(row, dict) and isinstance(row.get("values"), dict) else {}
    return _text_value(values.get("Publication Year")) or _text_value(values.get("year")) or (pdf.get("year") if pdf else None)


def _package_maps(package: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = {
        str(row.get("row_id")): row
        for row in package.get("rows", [])
        if isinstance(row, dict) and row.get("row_id")
    }
    pdfs = {
        str(pdf.get("pdf_id")): pdf
        for pdf in package.get("pdfs", [])
        if isinstance(pdf, dict) and pdf.get("pdf_id")
    }
    columns = {
        str(column.get("column_name")): column
        for column in package.get("columns", [])
        if isinstance(column, dict) and column.get("column_name")
    }
    return rows, pdfs, columns


def _evidence_by_proposal(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(evidence_path(run_dir)):
        row = dict(row)
        if not row.get("quote_text"):
            row["quote_text"] = row.get("table_text") or row.get("evidence_text") or row.get("caption_text")
        grouped.setdefault(str(row.get("proposal_id") or ""), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: int(item.get("evidence_rank") or 9999))
    return grouped


def _enriched_proposals(run_dir: Path) -> list[dict[str, Any]]:
    package = _review_package(run_dir)
    rows, pdfs, _columns = _package_maps(package)
    latest = latest_decisions(read_jsonl(decisions_path(run_dir)))
    proposals: list[dict[str, Any]] = []
    for proposal in read_jsonl(proposals_path(run_dir)):
        item = dict(proposal)
        row = rows.get(str(item.get("row_id") or ""))
        pdf = pdfs.get(str(item.get("pdf_id") or ""))
        item["latest_decision"] = latest.get(str(item.get("proposal_id") or ""))
        item.setdefault("paper_title", _row_title(row, pdf))
        item.setdefault("paper_authors", _row_authors(row, pdf))
        item.setdefault("paper_year", _row_year(row, pdf))
        item.setdefault("is_figure_derived", False)
        item.setdefault("is_fallback_evidence", False)
        proposals.append(item)
    return proposals


def _proposal_detail(run_dir: Path, proposal_id: str) -> dict[str, Any]:
    package = _review_package(run_dir)
    rows, _pdfs, columns = _package_maps(package)
    decisions = read_jsonl(decisions_path(run_dir))
    decision_history = [row for row in decisions if str(row.get("proposal_id") or "") == proposal_id]
    latest = latest_decisions(decisions).get(proposal_id)
    evidence = _evidence_by_proposal(run_dir).get(proposal_id, [])
    for proposal in _enriched_proposals(run_dir):
        if str(proposal.get("proposal_id") or "") != proposal_id:
            continue
        proposal["latest_decision"] = latest
        return {
            "proposal": proposal,
            "evidence": evidence,
            "latest_decision": latest,
            "decision_history": decision_history,
            "row_context": rows.get(str(proposal.get("row_id") or ""), {}).get("values", {}),
            "column_definition": columns.get(str(proposal.get("column_name") or "")),
        }
    raise KeyError(f"Unknown proposal_id: {proposal_id}")


def _review_progress(run_dir: Path) -> dict[str, Any]:
    proposals = [item for item in _enriched_proposals(run_dir) if item.get("review_bucket") != "diagnostic"]
    counts = {"accepted": 0, "accepted_with_edit": 0, "confirmed_no_data": 0, "rejected": 0}
    for proposal in proposals:
        decision = (proposal.get("latest_decision") or {}).get("decision")
        if decision in counts:
            counts[decision] += 1
    reviewed = sum(counts.values())
    return {
        "run_id": proposals[0].get("run_id") if proposals else _review_package(run_dir).get("run_id", run_dir.name),
        "total_proposals": len(proposals),
        "reviewed": reviewed,
        "pending": max(len(proposals) - reviewed, 0),
        **counts,
    }


def _review_table(run_dir: Path) -> dict[str, Any]:
    package = _review_package(run_dir)
    proposals = _enriched_proposals(run_dir)
    proposals_by_cell = {
        (str(proposal.get("row_id") or ""), str(proposal.get("column_name") or "")): proposal
        for proposal in proposals
    }
    columns = [
        {
            "name": str(column.get("column_name") or ""),
            "description": column.get("description"),
            "field_type": column.get("field_type"),
            "is_target": bool(column.get("is_target", True)),
        }
        for column in package.get("columns", [])
        if isinstance(column, dict) and column.get("column_name")
    ]
    out_rows = []
    for row in package.get("rows", []):
        if not isinstance(row, dict):
            continue
        values = row.get("values") if isinstance(row.get("values"), dict) else {}
        cells: dict[str, Any] = {}
        for column in columns:
            column_name = column["name"]
            proposal = proposals_by_cell.get((str(row.get("row_id") or ""), column_name))
            original_value = values.get(column_name)
            decision = (proposal.get("latest_decision") or {}).get("decision") if proposal else None
            display_status = decision or ("pending" if proposal else "unchanged")
            if decision == "accepted":
                display_value = proposal.get("proposed_value")
            elif decision == "accepted_with_edit":
                display_value = (proposal.get("latest_decision") or {}).get("edited_value") or proposal.get("proposed_value")
            elif decision in {"confirmed_no_data", "rejected"}:
                display_value = original_value
            elif proposal:
                display_value = proposal.get("proposed_value") or original_value
            else:
                display_value = original_value
            cells[column_name] = {
                "column_name": column_name,
                "original_value": original_value,
                "display_value": display_value,
                "display_status": display_status,
                "has_proposal": proposal is not None,
                "proposal": proposal,
            }
        out_rows.append(
            {
                "row_id": row.get("row_id"),
                "row_index": row.get("row_index"),
                "paper_label": row.get("paper_label") or row.get("row_id"),
                "title": _row_title(row, None),
                "values": values,
                "cells": cells,
            }
        )
    return {"run_id": package.get("run_id", run_dir.name), "columns": columns, "rows": out_rows, "proposal_count": len(proposals)}


def make_handler(run_dir: Path):
    class ReviewHandler(BaseHTTPRequestHandler):
        server_version = "papers-to-table-agent-kit/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            if getattr(self.server, "quiet", False):
                return
            super().log_message(format, *args)

        def _send_json(self, status: int, payload: Any) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, status: int, message: str) -> None:
            body = message.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if path.suffix in {".json", ".html"} else "public, max-age=60")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/decisions":
                    self._send_json(200, {"decisions": read_jsonl(decisions_path(run_dir))})
                    return
                if parsed.path == "/api/proposals":
                    proposals = _enriched_proposals(run_dir)
                    query = parse_qs(parsed.query)
                    if (query.get("reviewable_only") or [""])[0].lower() in {"1", "true", "yes"}:
                        proposals = [proposal for proposal in proposals if proposal.get("review_bucket") != "diagnostic"]
                    self._send_json(200, {"run_id": _review_package(run_dir).get("run_id", run_dir.name), "count": len(proposals), "proposals": proposals})
                    return
                if parsed.path.startswith("/api/proposals/"):
                    proposal_id = unquote(parsed.path.removeprefix("/api/proposals/"))
                    self._send_json(200, _proposal_detail(run_dir, proposal_id))
                    return
                if parsed.path == "/api/review-table":
                    self._send_json(200, _review_table(run_dir))
                    return
                if parsed.path == "/api/progress-review":
                    self._send_json(200, _review_progress(run_dir))
                    return
                if parsed.path.startswith("/api/assets/pdf/"):
                    pdf_id = unquote(parsed.path.removeprefix("/api/assets/pdf/"))
                    package = _review_package(run_dir)
                    pdf = next((item for item in package.get("pdfs", []) if isinstance(item, dict) and str(item.get("pdf_id")) == pdf_id), None)
                    if not pdf:
                        self._send_text(404, f"Unknown pdf_id: {pdf_id}")
                        return
                    path_value = str(pdf.get("path") or "").strip()
                    candidate = resolve_input_path(run_dir, path_value)
                    if not candidate.exists() or not candidate.is_file():
                        self._send_text(404, f"PDF not found: {pdf_id}")
                        return
                    self._send_file(candidate)
                    return
            except KeyError as exc:
                self._send_json(404, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            path = _safe_path(run_dir, self.path)
            if path is None:
                self._send_text(403, "Path escapes run directory.")
                return
            if path.is_dir():
                path = path / "index.html"
            if not path.exists() or not path.is_file():
                self._send_text(404, f"Not found: {self.path}")
                return
            self._send_file(path)

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length) if length else b"{}"
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/proposals/") and parsed.path.endswith("/decision"):
                try:
                    proposal_id = unquote(parsed.path.removeprefix("/api/proposals/").removesuffix("/decision"))
                    payload = json.loads(body.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a decision object.")
                    if payload.get("decision") not in DECISIONS:
                        raise ValueError(f"Unsupported decision: {payload.get('decision')!r}")
                    proposal_map = {str(proposal.get("proposal_id")): proposal for proposal in _enriched_proposals(run_dir)}
                    proposal = proposal_map.get(proposal_id)
                    if proposal is None:
                        raise ValueError(f"Unknown proposal_id: {proposal_id}")
                    decided_at = utc_now()
                    row = {
                        "review_decision_id": stable_id("rev", proposal_id, payload.get("decision"), decided_at),
                        "run_id": proposal.get("run_id") or _review_package(run_dir).get("run_id", run_dir.name),
                        "proposal_id": proposal_id,
                        "cell_id": proposal.get("cell_id"),
                        "decision": payload.get("decision"),
                        "decision_source": payload.get("decision_source") or "human_individual",
                        "resolution_reason": payload.get("resolution_reason"),
                        "edited_value": payload.get("edited_value"),
                        "reviewer_note": payload.get("reviewer_note"),
                        "decided_at": decided_at,
                    }
                    write_latest_decisions(run_dir, [row])
                except Exception as exc:
                    self._send_json(422, {"ok": False, "error": str(exc)})
                    return
                self._send_json(200, row)
                return
            if parsed.path == "/api/decisions":
                try:
                    payload = json.loads(body.decode("utf-8"))
                    rows = payload.get("decisions", []) if isinstance(payload, dict) else payload
                    if not isinstance(rows, list):
                        raise ValueError("Expected a decisions list.")
                    proposals = read_jsonl(proposals_path(run_dir))
                    proposal_ids = {str(proposal.get("proposal_id")) for proposal in proposals if proposal.get("proposal_id")}
                    run_id = str(proposals[0].get("run_id") or run_dir.name) if proposals else run_dir.name
                    for row in rows:
                        if not isinstance(row, dict):
                            raise ValueError("Every decision must be an object.")
                        proposal_id = str(row.get("proposal_id") or "").strip()
                        if not proposal_id:
                            raise ValueError("Every decision must include proposal_id.")
                        if proposal_id not in proposal_ids:
                            raise ValueError(f"Unknown proposal_id: {proposal_id}")
                        if row.get("decision") not in DECISIONS:
                            raise ValueError(f"Unsupported decision: {row.get('decision')!r}")
                        row.setdefault("run_id", run_id)
                        row.setdefault("decision_source", "human_individual")
                        row.setdefault("decided_at", utc_now())
                        row.setdefault("review_decision_id", stable_id("rev", proposal_id, row.get("decision"), row.get("decided_at")))
                    decisions = write_latest_decisions(run_dir, rows)
                except Exception as exc:
                    self._send_json(422, {"ok": False, "error": str(exc)})
                    return
                self._send_json(200, {"ok": True, "decision_count": len(decisions), "decisions": decisions})
                return
            if parsed.path in {"/api/bulk-accept", "/api/proposals/bulk-accept"}:
                try:
                    payload = json.loads(body.decode("utf-8"))
                    proposal_ids = payload.get("proposal_ids", []) if isinstance(payload, dict) else []
                    if not isinstance(proposal_ids, list):
                        raise ValueError("Expected proposal_ids to be a list.")
                    proposals = read_jsonl(proposals_path(run_dir))
                    proposal_map = {str(proposal.get("proposal_id")): proposal for proposal in proposals if proposal.get("proposal_id")}
                    existing_latest = latest_decisions(read_jsonl(decisions_path(run_dir)))
                    run_id = str(proposals[0].get("run_id") or run_dir.name) if proposals else run_dir.name
                    decided_at = utc_now()
                    rows = []
                    for raw_id in proposal_ids:
                        proposal_id = str(raw_id or "").strip()
                        proposal = proposal_map.get(proposal_id)
                        if proposal is None or proposal_id in existing_latest:
                            continue
                        rows.append(
                            {
                                "review_decision_id": stable_id("rev", proposal_id, "human_bulk_accept", decided_at),
                                "run_id": run_id,
                                "proposal_id": proposal_id,
                                "cell_id": proposal.get("cell_id"),
                                "decision": "accepted",
                                "decision_source": "human_bulk_accept",
                                "edited_value": None,
                                "reviewer_note": "Bulk accepted in the standalone review UI.",
                                "decided_at": decided_at,
                            }
                        )
                    decisions = write_latest_decisions(run_dir, rows)
                except Exception as exc:
                    self._send_json(422, {"ok": False, "error": str(exc)})
                    return
                self._send_json(200, {"ok": True, "accepted_count": len(rows), "decision_count": len(decisions), "decisions": rows})
                return
            if parsed.path == "/api/export":
                try:
                    result = apply_decisions(run_dir, use_existing_decisions=True, export=True)
                except Exception as exc:
                    self._send_json(422, {"ok": False, "error": str(exc)})
                    return
                self._send_json(200, {"ok": True, **result})
                return
            self._send_text(404, f"Not found: {self.path}")

    return ReviewHandler


def serve(run_dir: Path, *, host: str = "127.0.0.1", port: int = 0, open_browser: bool = True, quiet: bool = False) -> tuple[ThreadingHTTPServer, str]:
    run_dir = run_dir.resolve()
    index = review_index_path(run_dir)
    if not index.exists():
        raise FileNotFoundError("human_review/index.html not found. Build with --with-review first.")
    server = ThreadingHTTPServer((host, port), make_handler(run_dir))
    server.quiet = quiet  # type: ignore[attr-defined]
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/human_review/index.html"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if open_browser:
        webbrowser.open(url)
    return server, url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve a rich papers-to-table agent-kit review bundle.")
    parser.add_argument("--run", required=True, help="Path to the generated review run directory.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Keep this on localhost unless you understand the risk.")
    parser.add_argument("--port", type=int, default=0, help="Bind port. 0 chooses a free port.")
    parser.add_argument("--no-open", action="store_true", help="Print URL without opening a browser.")
    parser.add_argument("--quiet", action="store_true", help="Suppress request logs.")
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("serve_review.py only supports localhost bind addresses.")
    server, url = serve(Path(args.run), host=args.host, port=args.port, open_browser=not args.no_open, quiet=args.quiet)
    print(f"review_url: {url}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.shutdown()
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
