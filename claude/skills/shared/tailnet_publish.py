#!/usr/bin/env python3
"""Publish a file or a local server on the tailnet, so a link handed to the user opens on any of their machines.

A `file:///` link opens only on the machine that wrote the file — the two machines' projects roots
share no path — and `localhost` names a different machine on every device that clicks it. A tailnet
URL names this machine from all of them, and Tailscale is already up on both with HTTPS certificates
issued, so publishing costs no new service and no new credential.

    tailnet_publish.py publish <file> [--as <path>]   # prints the URL; exit 1 with a NOTE otherwise
    tailnet_publish.py unpublish <path>               # drop one published file
    tailnet_publish.py publish-port <port>            # front a loopback server; prints https://<node>:<port>/
    tailnet_publish.py unpublish-port <port>
    tailnet_publish.py list                           # every published file and the path behind it
    tailnet_publish.py serve                          # the loopback file server (spawned by publish)

`--as` and `unpublish` take the URL path WITHOUT its leading slash (`claude/report.html`): Git Bash
rewrites a leading-slash argument into a Windows path before a native program ever sees it. The
default path is the file's path inside its git repo, prefixed with the repo's name
(`claude/tmp/report.html`), because the node's URL space is shared — `/` on the Windows box already
belongs to a media server — and two artifacts with one basename must not share an address.

Files: one loopback server on PUBLISH_PORT serves every published file from a registry, and each file
gets its own `tailscale serve --set-path=/<path> http://127.0.0.1:<port>/f/<path>`. Tailscale
replaces the mapped path with the target's own, so the key arrives intact and one server can tell the
files apart. The file form of `tailscale serve` would need no process, but the macOS App Store build
refuses it outright and Windows refuses it to a non-admin shell (`must be a Windows local admin to
serve a path`), so the proxy is the only shape that works on both machines. Only registered files are
reachable, every file is re-read per request, and the server answers only Host headers naming
loopback or a `*.ts.net` node, so a web page rebinding its own name to 127.0.0.1 reads nothing.

Servers: `publish-port N` maps `https://<node>:N/` to `http://127.0.0.1:N`. Tailscale listens on the
tailnet address and the server on loopback, so the two share the port number without colliding, the
server keeps its loopback bind, and the whole root is proxied, so no base path is stripped. A server
that checks the Host header (Vite's `server.allowedHosts`) has to allow the node's MagicDNS name.

Every publish verifies by fetching the URL — for a file, comparing the bytes — because the serve config
lives in tailscaled and survives a reboot while the loopback file server does not; a dead server leaves
every local check passing while the URL answers 502. A path or port already mapped to something this
module did not create is refused rather than repointed. The URL names whichever machine published, and
answers only while that machine is awake.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUBLISH_PORT = 8788
# Bumped whenever the server's routing or registry format changes, so a detached server started by an
# older copy of this module is recognised as stale and replaced rather than trusted.
PROTOCOL = "2"
MARKER = "X-Tailnet-Publish"
STATE_DIR = Path.home() / ".claude" / "tailnet-publish"
REGISTRY = STATE_DIR / "registry.json"
LOCK = STATE_DIR / "registry.lock"
LOG = STATE_DIR / "server.log"
KEY_PREFIX = "/f/"
TARGET_PREFIX = f"http://127.0.0.1:{PUBLISH_PORT}{KEY_PREFIX}"


def _note(text: str) -> None:
    print(f"NOTE: {text}", file=sys.stderr)


# ── registry ──────────────────────────────────────────────────────────────────


def _read_registry() -> dict[str, str]:
    """URL path (`claude/tmp/report.html`, no leading slash) → absolute file path.

    Retried briefly on a sharing violation: on Windows a reader can catch the instant a writer's
    os.replace swaps the file, and answering "nothing published" then would 404 a live file.
    """
    for attempt in range(10):
        try:
            data = json.loads(REGISTRY.read_text(encoding="utf-8"))
            break
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
        except OSError:
            if attempt == 9:
                return {}
            time.sleep(0.02)
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _write_registry(entries: dict[str, str]) -> None:
    """Replace the registry atomically, so the server never reads half a file.

    os.replace onto a file the server has open fails on Windows (CPython opens without
    FILE_SHARE_DELETE), so the swap is retried; the temp file is removed whatever happens.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix="registry.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2, sort_keys=True)
            fh.write("\n")
        for attempt in range(50):
            try:
                os.replace(tmp, REGISTRY)
                return
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.02)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)


@contextlib.contextmanager
def _registry_lock() -> Iterator[None]:
    """Serialise every read-modify-write of the registry across processes.

    Without it two publishes at once each write back the registry they read, and one entry is lost —
    its URL then 404s while its serve path stays mapped.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+b") as fh:
        if sys.platform == "win32":
            import msvcrt  # inline: Windows-only module

            fh.seek(0)
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # inline: POSIX-only module

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


# ── naming ────────────────────────────────────────────────────────────────────


def _default_path(file: Path) -> str:
    """`<repo>/<path inside the repo>` for a file in a git repo, else `<parent dir>/<filename>`."""
    for parent in file.parents:
        if (parent / ".git").exists():
            return f"{parent.name}/{file.relative_to(parent).as_posix()}"
    return f"{file.parent.name or 'file'}/{file.name}"


def _normalise_path(raw: str) -> str | None:
    """A URL path without its leading slash, or None when it cannot be one.

    Refuses the empty path (that is `/`, which may belong to another service), `.`/`..` segments,
    and backslashes or drive colons — the last two being what a Git Bash-mangled `/x` turns into.
    """
    path = raw.strip().strip("/")
    segments = path.split("/")
    if not path or "\\" in path or ":" in path or any(s in ("", ".", "..") for s in segments):
        return None
    return path


# ── tailscale ─────────────────────────────────────────────────────────────────


def _tailscale_cli() -> str | None:
    """The tailscale binary. A GUI install puts it nowhere on PATH, so the bundle
    locations are tried first and `which` is the fallback for a package install."""
    for candidate in ("/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                      r"C:\Program Files\Tailscale\tailscale.exe",
                      "/usr/bin/tailscale", "/usr/local/bin/tailscale", "/opt/homebrew/bin/tailscale"):
        if Path(candidate).exists():
            return candidate
    return shutil.which("tailscale")


def _tailscale_json(cli: str, *args: str) -> dict | None:
    try:
        r = subprocess.run([cli, *args, "--json"], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _node_name(cli: str) -> str | None:
    """`<this node>.<tailnet>.ts.net`, or None if it cannot be served.

    Both halves are required. Without a DNSName this node has no MagicDNS name to be reached by,
    and without CertDomains the tailnet has HTTPS certificates disabled, leaving `tailscale serve`
    nothing to terminate TLS with — it would accept the config and then fail every request.
    """
    data = _tailscale_json(cli, "status")
    if data is None:
        return None
    name = (data.get("Self") or {}).get("DNSName", "").rstrip(".")
    return name if name and data.get("CertDomains") else None


def _mapped_target(cli: str, host: str, port: int, path: str) -> str | None:
    """What the node currently proxies `/<path>` on `host:port` to, or None when nothing is mapped.

    `""` for a mapping this module cannot read as a proxy (a file, a text handler), which callers
    treat as foreign like any other target they did not create.
    """
    data = _tailscale_json(cli, "serve", "status") or {}
    handlers = ((data.get("Web") or {}).get(f"{host}:{port}") or {}).get("Handlers") or {}
    handler = handlers.get("/" + path.strip("/")) if path else handlers.get("/")
    if handler is None:
        return None
    return handler.get("Proxy", "") if isinstance(handler, dict) else ""


def _tailscale_serve(cli: str, args: list[str]) -> bool:
    """Run one `tailscale serve` change.

    Only ever scoped to one path or one port: `tailscale serve reset` would clear every other entry
    the node serves, the media server on `/` included.
    """
    try:
        r = subprocess.run([cli, "serve", "--yes", *args], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    # A refused config prints `error:` on stdout and still exits 0, so the text is read as well.
    return r.returncode == 0 and "error:" not in (r.stdout + r.stderr).lower()


def _set_path(cli: str, url_path: str, target: str) -> bool:
    return _tailscale_serve(cli, ["--bg", f"--set-path=/{url_path}", target])


def _clear_path(cli: str, url_path: str) -> bool:
    return _tailscale_serve(cli, [f"--set-path=/{url_path}", "off"])


# ── the loopback file server ──────────────────────────────────────────────────


def _probe_server() -> str:
    """What holds PUBLISH_PORT: `free`, `ours`, `stale` (an older copy of this server), or `other`.

    Spawning onto a port something else holds would fail invisibly — the bind error goes to a log
    nobody reads — and every published path would proxy to that other program.
    """
    conn = http.client.HTTPConnection("127.0.0.1", PUBLISH_PORT, timeout=2)
    try:
        conn.request("GET", "/__ping")
        response = conn.getresponse()
        response.read()
        marker = response.getheader(MARKER)
        return "other" if not marker else ("ours" if marker == PROTOCOL else "stale")
    except (OSError, http.client.HTTPException):
        return "free"
    finally:
        conn.close()


def _stop_stale_server() -> bool:
    """Ask an older server to exit, and wait for the port to free. A server too old to know
    /__shutdown stays up, and the caller says so rather than guessing at a pid to kill."""
    conn = http.client.HTTPConnection("127.0.0.1", PUBLISH_PORT, timeout=2)
    with contextlib.suppress(OSError, http.client.HTTPException):
        conn.request("POST", "/__shutdown")
        conn.getresponse().read()
    conn.close()
    for _ in range(25):
        if _probe_server() == "free":
            return True
        time.sleep(0.2)
    return False


def _start_server() -> bool:
    """Spawn `serve` detached, and wait for it to answer.

    Detached because it has to outlive this process — the link is meant to be clickable long after
    the file is written — with both streams into a log so a server complaining hours from now cannot
    surface in whatever terminal the user is using by then. Windows gets CREATE_NO_WINDOW so no
    console flashes onto the desktop.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    detach: dict[str, object] = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW}
                                 if sys.platform == "win32" else {"start_new_session": True})
    try:
        with LOG.open("ab") as fh:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve"],
                             stdin=subprocess.DEVNULL, stdout=fh, stderr=fh, **detach)
    except OSError as exc:
        _note(f"could not start the publish server: {exc}")
        return False
    for _ in range(25):
        time.sleep(0.2)
        if _probe_server() == "ours":
            return True
    _note(f"the publish server did not answer on port {PUBLISH_PORT} — see {LOG}.")
    return False


def _ensure_server() -> bool:
    held = _probe_server()
    if held == "stale" and not _stop_stale_server():
        _note(f"an older publish server holds 127.0.0.1:{PUBLISH_PORT} and would not exit — stop it "
             "by hand, then publish again.")
        return False
    if held == "other":
        _note(f"127.0.0.1:{PUBLISH_PORT} is held by something else, so nothing was published.")
        return False
    return held == "ours" or _start_server()


def _host_allowed(host: str | None) -> bool:
    """Loopback, or a MagicDNS node name. `tailscale serve` forwards the name the user typed, and
    anything else reaching a loopback socket is a page that rebound its own name to 127.0.0.1."""
    name = (host or "").rsplit(":", 1)[0].lower().rstrip(".")
    return name in ("127.0.0.1", "localhost") or name.endswith(".ts.net")


class Handler(BaseHTTPRequestHandler):
    server_version = "tailnet-publish/" + PROTOCOL
    protocol_version = "HTTP/1.1"

    def _head(self, status: HTTPStatus, length: int, ctype: str | None = None) -> None:
        self.send_response(status)
        self.send_header(MARKER, PROTOCOL)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        # Files are rewritten in place, and the point of a stable URL is that an open tab reloads
        # onto the new content.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _text(self, status: HTTPStatus, text: str, body: bool = True) -> None:
        data = text.encode()
        self._head(status, len(data), "text/plain; charset=utf-8")
        if body:
            self.wfile.write(data)

    def _serve(self, body: bool) -> None:
        if not _host_allowed(self.headers.get("Host")):
            self._text(HTTPStatus.MISDIRECTED_REQUEST, "unknown host\n", body)
            return
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path == "/__ping":
            self._head(HTTPStatus.NO_CONTENT, 0)
            return
        file = _read_registry().get(path[len(KEY_PREFIX):]) if path.startswith(KEY_PREFIX) else None
        if file is None:
            self._text(HTTPStatus.NOT_FOUND, "not published\n", body)
            return
        try:
            data = Path(file).read_bytes()
        except OSError:
            self._text(HTTPStatus.NOT_FOUND, "the published file no longer exists\n", body)
            return
        ctype = mimetypes.guess_type(file)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        self._head(HTTPStatus.OK, len(data), ctype)
        if body:
            self.wfile.write(data)

    def do_GET(self) -> None:
        self._serve(body=True)

    def do_HEAD(self) -> None:
        self._serve(body=False)

    def do_POST(self) -> None:
        # Only a loopback caller naming loopback may stop the server; the tailnet reaches this socket
        # through `tailscale serve` with a `*.ts.net` Host, and never gets to shut it down.
        name = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if self.path != "/__shutdown" or name not in ("127.0.0.1", "localhost"):
            self._text(HTTPStatus.NOT_FOUND, "not found\n")
            return
        self._head(HTTPStatus.NO_CONTENT, 0)
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format: str, *args: object) -> None:
        pass


def _serve() -> int:
    """Loopback only: the tailnet reaches this through `tailscale serve` or not at all."""
    server = ThreadingHTTPServer(("127.0.0.1", PUBLISH_PORT), Handler)
    server.daemon_threads = True
    print(f"serving {REGISTRY} on http://127.0.0.1:{PUBLISH_PORT}", flush=True)
    server.serve_forever()
    return 0


# ── publishing files ──────────────────────────────────────────────────────────


def _fetch_matches(url: str, file: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status == 200 and response.read() == file.read_bytes()
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _prune(cli: str, entries: dict[str, str]) -> dict[str, str]:
    """Unpublish every entry whose file is gone, so the node's serve config does not accrete a path
    per artifact ever handed over. An entry whose `off` failed is kept, so the next run retries it."""
    return {p: f for p, f in entries.items() if Path(f).exists() or not _clear_path(cli, p)}


def publish(file: Path, url_path: str | None = None) -> str | None:
    """Publish `file` and return its verified tailnet URL, else None with the reason on stderr.

    `url_path` is the path without its leading slash. An explicit one may take over a path another of
    this module's files holds; the default never does, since two files meeting there is an accident.
    """
    file = file.resolve()
    if not file.is_file():
        _note(f"{file} is not a file, so it was not published.")
        return None
    path = _normalise_path(url_path) if url_path is not None else _default_path(file)
    if path is None:
        _note(f"{url_path!r} is not a usable URL path (give it without a leading slash).")
        return None
    cli = _tailscale_cli()
    if not cli:
        _note("no tailscale binary found, so the file was not published.")
        return None
    host = _node_name(cli)
    if not host:
        _note("this node has no MagicDNS name with HTTPS certificates, so the file was not published.")
        return None
    quoted = urllib.parse.quote(path)
    target = TARGET_PREFIX + quoted
    url = f"https://{host}/{quoted}"

    with _registry_lock():
        entries = _prune(cli, _read_registry())
        previous = entries.get(path)
        if previous is not None and previous != str(file) and url_path is None and Path(previous).exists():
            _note(f"/{path} already publishes {previous}; pass --as <path> to publish {file.name} elsewhere.")
            return None
        mapped = _mapped_target(cli, host, 443, path)
        if mapped is not None and mapped != target:
            _note(f"/{path} on this node already serves {mapped or 'something else'}, which this module "
                 "did not create, so it was left alone.")
            return None
        entries[path] = str(file)
        _write_registry(entries)

    if _ensure_server() and _set_path(cli, path, target) and _fetch_matches(url, file):
        return url

    with _registry_lock():
        entries = _read_registry()
        if previous is None:
            entries.pop(path, None)
            if mapped is None:
                _clear_path(cli, path)
        else:
            entries[path] = previous
        _write_registry(entries)
    _note(f"{url} did not return this file, so it is not published.")
    return None


def _unpublish(url_path: str) -> bool:
    path = _normalise_path(url_path)
    cli = _tailscale_cli()
    if path is None or not cli:
        _note("nothing to unpublish: " + ("not a usable URL path." if path is None else "no tailscale binary."))
        return False
    with _registry_lock():
        entries = _read_registry()
        if path not in entries:
            _note(f"/{path} is not published by this module, so it was left alone.")
            return False
        if not _clear_path(cli, path):
            _note(f"tailscale refused to clear /{path}; it is still registered.")
            return False
        entries.pop(path)
        _write_registry(entries)
    return True


# ── publishing servers ────────────────────────────────────────────────────────


def _port_answers(url: str) -> bool:
    """Did a server answer through the proxy? Any status below 500 counts — a dev server's root may
    well 404 — while 502 is tailscale saying nothing listens on the loopback port."""
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _publish_port(port: int) -> str | None:
    """Front `http://127.0.0.1:<port>` at `https://<node>:<port>/` and return that verified URL."""
    if not 1 <= port <= 65535 or port == 443:
        _note(f"{port} is not a port this can publish (443 is the node's shared root).")
        return None
    cli = _tailscale_cli()
    if not cli:
        _note("no tailscale binary found, so the server was not published.")
        return None
    host = _node_name(cli)
    if not host:
        _note("this node has no MagicDNS name with HTTPS certificates, so the server was not published.")
        return None
    target = f"http://127.0.0.1:{port}"
    mapped = _mapped_target(cli, host, port, "")
    if mapped is not None and mapped != target:
        _note(f"https://{host}:{port}/ already serves {mapped or 'something else'}, so it was left alone.")
        return None
    url = f"https://{host}:{port}/"
    if _tailscale_serve(cli, ["--bg", f"--https={port}", target]) and _port_answers(url):
        return url
    if mapped is None:
        _tailscale_serve(cli, [f"--https={port}", "off"])
    _note(f"{url} got no answer from a server on 127.0.0.1:{port}, so it is not published.")
    return None


def _unpublish_port(port: int) -> bool:
    cli = _tailscale_cli()
    host = _node_name(cli) if cli else None
    if not cli or not host:
        _note("no tailscale binary or node name, so nothing was unpublished.")
        return False
    if _mapped_target(cli, host, port, "") != f"http://127.0.0.1:{port}":
        _note(f"port {port} is not fronting 127.0.0.1:{port}, so it was left alone.")
        return False
    return _tailscale_serve(cli, [f"--https={port}", "off"])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Publish a file or a local server on the tailnet.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("file", type=Path)
    p.add_argument("--as", dest="url_path", help="URL path without the leading slash")
    sub.add_parser("unpublish").add_argument("url_path")
    sub.add_parser("publish-port").add_argument("port", type=int)
    sub.add_parser("unpublish-port").add_argument("port", type=int)
    sub.add_parser("list")
    sub.add_parser("serve")
    args = ap.parse_args()

    if args.cmd == "serve":
        return _serve()
    if args.cmd == "list":
        for path, file in sorted(_read_registry().items()):
            print(f"/{path}  ->  {file}{'' if Path(file).exists() else '  (missing)'}")
        return 0
    if args.cmd == "unpublish":
        return 0 if _unpublish(args.url_path) else 1
    if args.cmd == "unpublish-port":
        return 0 if _unpublish_port(args.port) else 1
    url = _publish_port(args.port) if args.cmd == "publish-port" else publish(args.file, args.url_path)
    if url:
        print(url)
    return 0 if url else 1


if __name__ == "__main__":
    raise SystemExit(main())
