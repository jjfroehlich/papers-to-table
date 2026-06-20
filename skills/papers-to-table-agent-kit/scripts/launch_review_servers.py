#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_review_package import build_review_package  # noqa: E402
from review_package_common import review_index_path  # noqa: E402


LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _available_port(host: str, preferred_port: int) -> int:
    if preferred_port <= 0:
        with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])
    for port in range(preferred_port, preferred_port + 200):
        if _port_is_available(host, port):
            return port
    raise RuntimeError(f"No free localhost port found at or above {preferred_port}.")


def _probe(url: str, *, timeout_seconds: float) -> tuple[bool, str | None]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return True, None
                last_error = f"HTTP {response.status}"
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.2)
    return False, last_error


def _tail(path: Path, *, max_chars: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


def launch_review_servers(
    run_dirs: list[Path],
    *,
    host: str,
    start_port: int,
    build: bool,
    quiet: bool,
    probe_timeout: float,
) -> dict[str, Any]:
    if host not in LOCALHOST_HOSTS:
        raise ValueError("launch_review_servers.py only supports localhost bind addresses.")

    servers: list[dict[str, Any]] = []
    next_port = start_port
    for run_dir in run_dirs:
        run_dir = run_dir.resolve()
        if build:
            build_review_package(run_dir, from_review_input=True, with_review=True)
        if not review_index_path(run_dir).exists():
            raise FileNotFoundError(f"human_review/index.html not found for {run_dir}; build review artifacts first.")

        port = _available_port(host, next_port)
        next_port = port + 1 if start_port > 0 else 0
        log_dir = run_dir / "human_review"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = log_dir / "serve_stdout.log"
        stderr_log = log_dir / "serve_stderr.log"
        command = [
            sys.executable,
            str(SCRIPT_DIR / "serve_review.py"),
            "--run",
            str(run_dir),
            "--host",
            host,
            "--port",
            str(port),
            "--no-open",
        ]
        if quiet:
            command.append("--quiet")

        creationflags = 0
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            popen_kwargs["start_new_session"] = True

        with stdout_log.open("ab") as stdout_handle, stderr_log.open("ab") as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=str(run_dir),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=creationflags,
                **popen_kwargs,
            )

        url = f"http://{host}:{port}/human_review/index.html"
        reachable, error = _probe(url, timeout_seconds=probe_timeout)
        status = "running" if reachable and process.poll() is None else "failed"
        servers.append(
            {
                "run_dir": str(run_dir),
                "status": status,
                "review_url": url,
                "process_id": process.pid,
                "port": port,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "error": error if status != "running" else None,
                "stderr_tail": _tail(stderr_log) if status != "running" else "",
                "command": command,
            }
        )

    return {
        "ok": all(item["status"] == "running" for item in servers),
        "servers": servers,
    }


def _print_summary(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    for item in result["servers"]:
        print(f"{Path(item['run_dir']).name}: {item['status']}")
        print(f"  review_url: {item['review_url']}")
        print(f"  process_id: {item['process_id']}")
        print(f"  stdout_log: {item['stdout_log']}")
        print(f"  stderr_log: {item['stderr_log']}")
        if item.get("error"):
            print(f"  error: {item['error']}")
    if not result["ok"]:
        print("One or more review servers failed to start.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, launch, probe, and print papers-to-table review server URLs.")
    parser.add_argument("--run", action="append", required=True, help="Run directory. Repeat for multiple independent runs.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Localhost only.")
    parser.add_argument("--start-port", type=int, default=8761, help="First preferred port. Use 0 for ephemeral ports.")
    parser.add_argument("--build", action="store_true", help="Build human_review artifacts before launching servers.")
    parser.add_argument("--quiet", action="store_true", help="Suppress request logs in server output.")
    parser.add_argument("--probe-timeout", type=float, default=8.0, help="Seconds to wait for each server URL to respond.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable launch results.")
    args = parser.parse_args(argv)

    result = launch_review_servers(
        [Path(value) for value in args.run],
        host=args.host,
        start_port=args.start_port,
        build=args.build,
        quiet=args.quiet,
        probe_timeout=args.probe_timeout,
    )
    _print_summary(result, as_json=args.json)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
