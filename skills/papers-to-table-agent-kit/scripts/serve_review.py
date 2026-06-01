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
from urllib.parse import unquote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_review_decisions import apply_decisions, write_latest_decisions  # noqa: E402
from review_package_common import DECISIONS, read_jsonl, stable_id, utc_now  # noqa: E402


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _safe_path(root: Path, request_path: str) -> Path | None:
    parsed = urlparse(request_path)
    rel = unquote(parsed.path.lstrip("/"))
    if not rel:
        rel = "review/index.html"
    if rel == "review":
        rel = "review/index.html"
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


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

        def do_GET(self) -> None:
            if self.path == "/api/decisions":
                self._send_json(200, {"decisions": read_jsonl(run_dir / "review" / "decisions.jsonl")})
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
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if path.suffix in {".json", ".html"} else "public, max-age=60")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length) if length else b"{}"
            if self.path == "/api/decisions":
                try:
                    payload = json.loads(body.decode("utf-8"))
                    rows = payload.get("decisions", []) if isinstance(payload, dict) else payload
                    if not isinstance(rows, list):
                        raise ValueError("Expected a decisions list.")
                    proposals = read_jsonl(run_dir / "normalized" / "proposals.jsonl")
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
            if self.path == "/api/export":
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
    index = run_dir / "review" / "index.html"
    if not index.exists():
        raise FileNotFoundError("review/index.html not found. Run build_review_package.py first.")
    server = ThreadingHTTPServer((host, port), make_handler(run_dir))
    server.quiet = quiet  # type: ignore[attr-defined]
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/review/index.html"
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
