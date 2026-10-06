#!/usr/bin/env python3
"""Who holds a TCP port on this machine, including the holder `lsof` cannot see.

A dev server that will not start, reporting `EADDRINUSE` while every process listing shows the port
free, has a holder outside this user's view. On macOS the usual one is Tailscale: `tailscale serve
--https=N` puts its listener in a root-owned system extension, so an unprivileged
`lsof -nP -iTCP:N -sTCP:LISTEN` prints nothing about a port that cannot be bound. A detector built on
process listings alone then says "nothing listening on port N" about a port it made unbindable itself.

So two instruments, and `verdict` composes them:

  listing    `lsof` on POSIX, `netstat -ano` on Windows. Names the process and its bind address, and
             sees only what this user may see.
  bind       an actual `bind()` on `0.0.0.0`. Authoritative about whether a server can take the port,
             and silent about who stopped it.

Bind-style matters because the two addresses are separate claims. Measured on macOS 2026-10-05 with
`SO_REUSEADDR` on both sockets: a wildcard listener does not stop a `127.0.0.1` bind, and a loopback
listener does not stop a `0.0.0.0` bind — while a second wildcard bind fails with errno 48. A
`tailscale serve` mapping takes the wildcard and tailnet addresses and leaves loopback free, which is
why `bind_probe` tests the wildcard: it is the one address that answers for both of them.

Usage as a CLI, for the shell callers that need one fact:
    port_probe.py pids <port>        # one PID per line, every listener this user can see
    port_probe.py served <port>      # the serve mapping's target; exit 0 mapped, 1 not
    port_probe.py verdict <port>     # a sentence naming the holder; exit 0 free, 1 held
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
from typing import List, NamedTuple

WILDCARD = "wildcard"
LOOPBACK = "loopback"
SPECIFIC = "specific"

WILDCARD_ADDRESSES = ("*", "0.0.0.0", "::", "[::]")
LOOPBACK_ADDRESSES = ("127.0.0.1", "::1", "[::1]", "localhost")


class Holder(NamedTuple):
    """One listening socket a process listing reported."""

    pid: int
    command: str
    address: str
    bind: str


class Verdict(NamedTuple):
    """What holds `port`, from both instruments at once.

    `free` is the bind probe's answer and the one a server will agree with. `summary` is what the two
    instruments say together — a port that cannot be bound with no listener in sight is the
    invisible-holder case, and the sentence names it rather than leaving a caller to read an empty
    list as nothing. A caller that wants the listing itself calls `holders(port)`.
    """

    port: int
    free: bool
    summary: str


def _bind_style(address: str) -> str:
    bare = address.rsplit(":", 1)[0] if re.search(r":\d+$", address) else address
    if bare in WILDCARD_ADDRESSES:
        return WILDCARD
    if bare in LOOPBACK_ADDRESSES:
        return LOOPBACK
    return SPECIFIC


def _run(argv: List[str]) -> str:
    """Stdout of a listing command, or "" when it is absent or fails.

    A missing or broken listing tool must not read as an empty port: every caller pairs this with
    `bind_probe`, which answers whether the port is takeable regardless.
    """
    try:
        result = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout or ""


def listeners() -> List[Holder]:
    """Every listening socket on this machine that a process listing shows this user.

    One enumeration rather than one per port: a caller comparing a record against the machine wants
    the sockets nothing claims, and those are invisible to a per-port query.
    """
    found = []
    windows = sys.platform == "win32"
    # netstat gives no command name, only a PID; its address column is `0.0.0.0:N` or `[::]:N`.
    lines = (_run(["netstat", "-ano", "-p", "tcp"]) if windows
             else _run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])).splitlines()
    for line in lines:
        fields = line.split()
        if windows:
            if len(fields) < 5 or fields[3].upper() != "LISTENING":
                continue
            address, pid_text, command = fields[1], fields[4], ""
        else:
            if len(fields) < 9 or fields[0] == "COMMAND":
                continue
            address, pid_text, command = fields[8], fields[1], fields[0]
        if not re.search(r"[:.]\d+$", address):
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        found.append(Holder(pid=pid, command=command, address=address, bind=_bind_style(address)))
    return found


def port_of(holder: Holder) -> int:
    """The port a listing row's address ends in."""
    return int(holder.address.rsplit(":", 1)[-1].rsplit(".", 1)[-1])


def holders(port: int) -> List[Holder]:
    """Every listener on `port` a process listing shows this user."""
    return [holder for holder in listeners() if port_of(holder) == port]


def bind_probe(port: int, address: str = "0.0.0.0") -> bool:
    """Could a server bind `port` on `address` right now?

    `SO_REUSEADDR` is set because that is what a real server sets, and the answer differs without it:
    the probe would refuse a port whose previous listener is still in `TIME_WAIT` and report it held.
    """
    probe = socket.socket()
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind((address, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def verdict(port: int) -> Verdict:
    """Both instruments on one port, with a summary that never calls an invisible holder nothing."""
    from tailnet_publish import serve_port_target  # inline to avoid circular import

    seen = holders(port)
    free = bind_probe(port)
    served = serve_port_target(port)

    if seen:
        who = ", ".join(f"{h.command or 'pid'} {h.pid} on {h.address}" for h in seen)
        summary = f"port {port} is held by {who}"
    elif served is not None:
        summary = (f"port {port} is held by this node's `tailscale serve` mapping to {served or 'something else'}, "
                   f"whose listener lives in a root-owned system extension and appears in no process listing. "
                   f"Clear it with `tailnet_publish.py unpublish-port {port}`.")
    elif not free:
        summary = (f"port {port} cannot be bound and no listener is visible to this user — a root-owned or "
                   f"another user's process holds it. `sudo lsof -nP -iTCP:{port} -sTCP:LISTEN` names it.")
    else:
        summary = f"port {port} is free"
    return Verdict(port=port, free=free, summary=summary)


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("pids", "served", "verdict"):
        print(__doc__.strip().split("Usage as a CLI", 1)[-1], file=sys.stderr)
        return 2
    try:
        port = int(argv[1])
    except ValueError:
        print(f"not a port number: {argv[1]}", file=sys.stderr)
        return 2
    if argv[0] == "pids":
        for holder in holders(port):
            print(holder.pid)
        return 0
    if argv[0] == "served":
        from tailnet_publish import serve_port_target  # inline to avoid circular import

        target = serve_port_target(port)
        if target is None:
            return 1
        print(target or "a handler this cannot read")
        return 0
    answer = verdict(port)
    print(answer.summary)
    return 0 if answer.free else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
