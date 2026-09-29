#!/usr/bin/env python3
"""serve-report — hand ONE html file to the tailnet over loopback.

`tailscale serve` can publish a file path directly, but not on macOS: the
sandboxed App Store build refuses it outright ("Path serving is not supported on
macOS due to sandbox restrictions"). Proxying a local port works on every
variant, so this is what listens on that port.

It serves exactly one file, whatever path is requested, so the only thing
reachable through the proxy is the report itself — a directory server rooted at
the repo's tmp/ would also expose the state file and the description cache. Any
path has to answer because `tailscale serve --set-path` strips the path it was
mapped at: a request for /github-status.html arrives here as `GET /`. The
bytes are read per request, so a regenerated report is served without restarting
anything, and the bind is loopback-only: the tailnet reaches this through
`tailscale serve` or not at all.

  serve-report.py --file <path> [--port 8787]

GET /__ping answers 204 and names the file being served, which is how a caller
tells this server apart from whatever else might hold the port.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Kept equal to SERVE_MARKER in repos-status.py, which reads it to tell this server from
# anything else holding the port. The two files cannot share a constant — one spawns the
# other as a subprocess and neither filename is importable — so changing this name alone
# makes that check classify us as a stranger and decline to publish, saying nothing useful.
MARKER = "X-Github-Status-Serve"


def handler_for(target: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "github-status-serve/1"
        protocol_version = "HTTP/1.1"

        def _head(self, status: HTTPStatus, length: int, ctype: str | None = None) -> None:
            self.send_response(status)
            self.send_header(MARKER, str(target))
            if ctype:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            # The report is rewritten in place on every run, and the whole point of a
            # stable URL is that an open tab reloads onto the new one.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def _serve(self, body: bool) -> None:
            if self.path == "/__ping":
                self._head(HTTPStatus.NO_CONTENT, 0)
                return
            try:
                data = target.read_bytes()
            except OSError as exc:
                text = f"{target} could not be read: {exc}\n".encode()
                self._head(HTTPStatus.NOT_FOUND, len(text), "text/plain; charset=utf-8")
                if body:
                    self.wfile.write(text)
                return
            self._head(HTTPStatus.OK, len(data), "text/html; charset=utf-8")
            if body:
                self.wfile.write(data)

        def do_GET(self) -> None:
            self._serve(body=True)

        def do_HEAD(self) -> None:
            self._serve(body=False)

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(args.file.resolve()))
    server.daemon_threads = True
    print(f"serving {args.file.resolve()} on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
