#!/usr/bin/env python3
"""Send a message to the session working on a project on the OTHER machine, via the dashboard relay.

Claude Code's own `SendMessage` reaches sessions on this machine only. Across machines, the local
dashboard relays: `POST /api/message` on this box hops to the peer's dashboard, which resolves the
project in its own session registry and writes the frame into that session's inbox. The peer's
resolution is authoritative, so this helper does not look the session up first — a roster read here
misses a session that has been idle since the peer's dashboard restarted, and the relay can even
start a session the peer's owner has allowed. The roster is read for one fact only: which peer
devices exist, since the relay refuses a bare project and wants `{device}/{project}`.

Two addressing rules this encodes, both of which cost real sends when done by hand:
- `target` is namespaced (`AIR/claude`); `from_agent` is BARE (`claude`). A prefixed `from_agent`
  mints a reply address like `CHROME/CHROME/claude`, refused one round trip later.
- Both are PROJECT ids — the directory name the dashboard derives — never a `ListAgents` session name.

The one local lookup is `session`: it asks this machine's dashboard for the `SendMessage` address of
the session working in a project, matched by working directory, because a session renamed away from
its directory name no longer matches a `ListAgents` name prefix.

Receipts are reported literally. `written` means the peer's session accepted the bytes, not that the
model read them; `unknown` means the answer was lost and the frame may exist, so it is never retried.

    peer_relay.py send [--project P] [--label L] [TEXT]   # TEXT or stdin; P defaults to this repo
    peer_relay.py peers                                   # the peer devices the dashboard hears
    peer_relay.py session [--project P]                   # the ListAgents name of P's session on THIS machine
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT_DASHBOARD = "http://127.0.0.1:9077"


class PeerUnmeasured(Exception):
    """The dashboard could not answer the question asked, which is not the same as nobody being there."""


def dashboard_url() -> str:
    """The local dashboard's base URL. Public because `session_clean.py` posts to the same one."""
    return os.environ.get("TAURI_DASHBOARD_URL", DEFAULT_DASHBOARD).rstrip("/")


def _request(path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data else {}
    with urllib.request.urlopen(urllib.request.Request(dashboard_url() + path, data=data, headers=headers), timeout=120) as response:
        return json.load(response)


def current_project() -> str:
    """This repo's project id — the directory name, which is what the dashboard derives from a cwd."""
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    return os.path.basename(root or os.getcwd())


def peer_devices() -> list[str]:
    """Names of the peer devices this dashboard currently hears. Raises PeerUnmeasured when it cannot tell."""
    try:
        roster = _request("/api/agents")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise PeerUnmeasured(f"the dashboard at {dashboard_url()} did not answer ({exc})") from exc
    if not roster.get("sync_listening"):
        raise PeerUnmeasured("this dashboard is not syncing with a peer")
    devices = [p["device"] for p in roster.get("peers", [])]
    if not devices:
        raise PeerUnmeasured("no peer device has been heard from recently (its dashboard may be down)")
    return devices


def local_session(project: str) -> tuple[str | None, str]:
    """The `ListAgents` name of the one live session on this machine working in `project`, or None and why.

    The dashboard owns this match: it reads Claude Code's session registry and derives the project id
    from each session's cwd, so it finds a session renamed away from its directory name, which a
    `ListAgents` name-prefix match misses. Raises PeerUnmeasured when the dashboard cannot answer.
    """
    try:
        roster = _request("/api/agents")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise PeerUnmeasured(f"the dashboard at {dashboard_url()} did not answer ({exc})") from exc
    if (roster.get("device") or "this device") in roster.get("registry_unreadable", []):
        raise PeerUnmeasured("the dashboard could not read this machine's session registry")
    rows = [r for r in roster.get("agents", []) + roster.get("registry_only", []) if r.get("local") and r.get("project") == project]
    if not rows:
        return None, "no live session on this machine works in it"
    row = rows[0]
    if row.get("name"):
        return row["name"], ""
    sessions = row.get("sessions")
    if sessions is None:
        raise PeerUnmeasured("the running dashboard predates the session name on agents rows; redeploy it")
    if sessions == 0:
        return None, "no live session on this machine works in it"
    return None, f"{sessions} live sessions share its directory, so neither address is the one"


def _send(target: str, text: str, from_agent: str, from_label: str | None = None) -> dict:
    """Relay one message to `target` (`{device}/{project}`) and return the receipt, never raising for a refusal."""
    body = {"target": target, "text": text, "from_agent": from_agent}
    if from_label:
        body["from_label"] = from_label
    try:
        return _request("/api/message", body)
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8", "replace"))
        except ValueError:
            return {"outcome": "refused", "reason": f"HTTP {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"outcome": "unknown", "detail": f"no answer from the local dashboard ({exc}); the frame may or may not have been written"}


def send_to_project(project: str, text: str, from_label: str | None = None) -> list[tuple[str, dict]]:
    """Send to `project` on every peer device; the sender is this session's own project, bare."""
    return [(f"{device}/{project}", _send(f"{device}/{project}", text, current_project(), from_label)) for device in peer_devices()]


def describe(target: str, receipt: dict) -> str:
    extra = " — ".join(str(receipt[k]) for k in ("reason", "detail") if receipt.get(k))
    return f"{target}: {receipt.get('outcome', '?')}{' — ' + extra if extra else ''}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Message the session on the other machine through the dashboard relay.")
    sub = parser.add_subparsers(dest="command", required=True)
    send_parser = sub.add_parser("send")
    send_parser.add_argument("--project", default=None, help="target project id (default: this repo's)")
    send_parser.add_argument("--label", default=None, help="free description of the sender")
    send_parser.add_argument("text", nargs="?", help="message text (default: read stdin)")
    sub.add_parser("peers")
    session_parser = sub.add_parser("session")
    session_parser.add_argument("--project", default=None, help="project id (default: this repo's)")
    args = parser.parse_args()
    try:
        if args.command == "peers":
            print("\n".join(peer_devices()))
            return 0
        if args.command == "session":
            name, why = local_session(args.project or current_project())
            print(name or f"none — {why}")
            return 0
        text = args.text if args.text is not None else sys.stdin.read()
        receipts = send_to_project(args.project or current_project(), text, args.label)
        for target, receipt in receipts:
            print(describe(target, receipt))
    except PeerUnmeasured as exc:
        if args.command == "session":
            print(f"UNMEASURED — {exc}")
            return 1
        print(f"NOT SENT — {exc}, so the other machine is unmeasured")
        return 1
    return 0 if all(r.get("outcome") in ("written", "duplicate") for _, r in receipts) else 1


if __name__ == "__main__":
    sys.exit(main())
