#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_review_package import build_review_package  # noqa: E402
from serve_review import serve  # noqa: E402


LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _command_text(parts: list[str]) -> str:
    quoted: list[str] = []
    for part in parts:
        if any(char.isspace() for char in part):
            quoted.append(f'"{part}"')
        else:
            quoted.append(part)
    return " ".join(quoted)


def _serve_command(run_dir: Path, host: str, port: int, open_browser: bool, quiet: bool) -> list[str]:
    command = [
        "python",
        str(SCRIPT_DIR / "serve_review.py"),
        "--run",
        str(run_dir),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if not open_browser:
        command.append("--no-open")
    if quiet:
        command.append("--quiet")
    return command


def _summary(
    run_dir: Path,
    build_result: dict[str, Any],
    *,
    host: str,
    port: int,
    open_browser: bool,
    quiet: bool,
    served: bool,
    review_url: str | None,
) -> dict[str, Any]:
    serve_command = _serve_command(run_dir, host, port, open_browser, quiet)
    return {
        "run_dir": str(run_dir),
        "validation_status": "ok",
        "authoring_validation": "ok",
        "generated_validation": "ok",
        "served": served,
        "review_url": review_url,
        "serve_command": serve_command,
        "serve_command_text": _command_text(serve_command),
        **build_result,
    }


def build_and_serve_review(
    run_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    quiet: bool = False,
    build_only: bool = False,
) -> tuple[dict[str, Any], ThreadingHTTPServer | None]:
    """Validate, build, validate generated artifacts, and optionally serve review UI."""
    if host not in LOCALHOST_HOSTS:
        raise ValueError("build_and_serve_review.py only supports localhost bind addresses.")
    run_dir = run_dir.resolve()
    build_result = build_review_package(run_dir, from_review_input=True)
    if build_only:
        return (
            _summary(
                run_dir,
                build_result,
                host=host,
                port=port,
                open_browser=open_browser,
                quiet=quiet,
                served=False,
                review_url=None,
            ),
            None,
        )
    server, review_url = serve(run_dir, host=host, port=port, open_browser=open_browser, quiet=quiet)
    return (
        _summary(
            run_dir,
            build_result,
            host=host,
            port=port,
            open_browser=open_browser,
            quiet=quiet,
            served=True,
            review_url=review_url,
        ),
        server,
    )


def _print_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    print(f"run_dir: {summary['run_dir']}")
    print(f"validation_status: {summary['validation_status']}")
    print(f"review_index: {Path(summary['review_index_path']).resolve()}")
    print(f"review_package: {Path(summary['review_package_path']).resolve()}")
    if summary.get("draft_filled_table_path"):
        print(f"draft_filled_table: {Path(summary['draft_filled_table_path']).resolve()}")
    if summary.get("review_url"):
        print(f"review_url: {summary['review_url']}")
    else:
        print(f"serve_command: {summary['serve_command_text']}")
    if not summary.get("pdfjs_assets_copied"):
        print("warning: PDF.js assets were not copied; the review UI will use browser PDF fallback.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and serve a papers-to-table agent-kit review package.")
    parser.add_argument("--run", required=True, help="Path to the run directory containing review_input.json.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Localhost only.")
    parser.add_argument("--port", type=int, default=0, help="Bind port. 0 chooses a free port.")
    parser.add_argument("--no-open", action="store_true", help="Print URL without opening a browser.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    parser.add_argument("--build-only", action="store_true", help="Validate and build without starting the review server.")
    parser.add_argument("--quiet", action="store_true", help="Suppress request logs.")
    args = parser.parse_args(argv)

    summary, server = build_and_serve_review(
        Path(args.run),
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
        quiet=args.quiet,
        build_only=args.build_only,
    )
    _print_summary(summary, as_json=args.json)
    if server is None:
        return 0
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
