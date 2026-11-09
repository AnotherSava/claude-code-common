#!/usr/bin/env python3
"""Cases for `peer_relay.py clear`, the one subcommand that makes the dashboard type into another session.

A receipt that reads as success when nothing was typed leaves a peer believing a session was cleared, so each case
pins what the line says and what the exit code is: `typed` exits 0, a refusal with its reason exits 1, and a dashboard
that does not answer prints UNMEASURED and exits 1. A stand-in dashboard on a loopback port answers the way
`/api/session/command` does, and records the body it was sent, so the request shape is pinned too.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import threading

from git_scratch import check, report

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "shared", "peer_relay.py")

class Dashboard(http.server.BaseHTTPRequestHandler):
    """Answers POST /api/session/command with the status and receipt the test queued, and keeps what it received.

    A queued receipt of None answers with an empty body, the way a dashboard built before the route does.
    """

    answer: tuple[int, dict | None] = (200, {})
    received: list[tuple[str, dict]] = []

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        Dashboard.received.append((self.path, body))
        status, receipt = Dashboard.answer
        data = b"" if receipt is None else json.dumps(receipt).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_: object) -> None:
        pass


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def clear(url: str, *extra: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TAURI_DASHBOARD_URL=url, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, SCRIPT, "clear", *extra], capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)


def main() -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Dashboard)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        Dashboard.answer = (200, {"outcome": "typed"})
        done = clear(url, "--project", "scheduler")
        check("typed prints the project and outcome", done.stdout.strip(), "scheduler: typed")
        check("typed exits 0", done.returncode, 0)
        check("the request goes to the command route", Dashboard.received[-1], ("/api/session/command", {"project": "scheduler", "command": "/clear"}))

        Dashboard.answer = (409, {"outcome": "refused", "reason": "the composer holds a draft"})
        done = clear(url, "--project", "scheduler")
        check("a refusal carries its reason", done.stdout.strip(), "scheduler: refused — the composer holds a draft")
        check("a refusal exits 1", done.returncode, 1)

        Dashboard.answer = (200, {"outcome": "typed"})
        clear(url)
        check("the project defaults to this repo's", Dashboard.received[-1][1].get("project"), os.path.basename(ROOT))

        Dashboard.answer = (404, None)
        done = clear(url, "--project", "scheduler")
        check("a dashboard without the route reads as unmeasured", done.stdout.startswith("UNMEASURED — the local dashboard answered /api/session/command with HTTP 404"), True)
        check("a dashboard without the route exits 1", done.returncode, 1)
    finally:
        server.shutdown()

    done = clear(f"http://127.0.0.1:{free_port()}", "--project", "scheduler")
    check("no dashboard reads as unmeasured", done.stdout.startswith("UNMEASURED — the local dashboard did not answer"), True)
    check("no dashboard exits 1", done.returncode, 1)

    raise SystemExit(report("peer-relay tests"))


if __name__ == "__main__":
    main()
