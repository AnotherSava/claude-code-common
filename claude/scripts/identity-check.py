#!/usr/bin/env python3
"""Assert that every public hostname on this box serves the application it is supposed to.

The failure this catches returns HTTP 200. A commercial storefront once served a co-tenant's application for
41 hours because docker compose publishes a service's name as a DNS alias on every network it joins, two
projects both had a service called "app", and the proxy — attached to both bridges — resolved the wrong one. Uptime monitoring, container healthchecks and `caddy validate` were all green the entire time. Only
an identity assertion can see it.

So this checks two things per target, and the second is the one that matters:

    the host's own marker is PRESENT   — it is up and serving its own app
    every other host's marker is ABSENT — it is not serving somebody else's

The reject set is derived from the manifest rather than written out, so adding a co-tenant is a single entry
and every existing target learns to reject it in the same edit.

Runs anywhere with python 3 and outbound HTTPS — a workstation, CI, or a timer. Prefer running it OFF the box:
an on-box checker shares fate with the thing it is checking. Stdlib only, no dependencies.

This lives in the dotfiles `scripts/` dir, NOT in any one project: three repos call it, and forking a copy per
repo is how two copies start drifting. Tenants resolve it as
`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/identity-check.py`. The MANIFEST is the opposite — it is per-host
data (which hostnames this box serves, and what each must prove), so it stays with the host and is passed in.

Usage:  identity-check.py <manifest.json>
Exit:   0 all correct, 1 at least one host is wrong or unreachable, 2 the manifest is unusable
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

TIMEOUT = 20
UA = "identity-check/1 (+co-tenant routing assertion)"
MAX_BYTES = 512 * 1024  # markers live in <head>; no reason to pull a whole page


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        raw = resp.read(MAX_BYTES)
        return resp.status, raw.decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    # Required, not defaulted: the old default was "beside this file", which silently stopped meaning anything
    # once the checker moved out of the project that owned the manifest. A missing argument must say so.
    if not argv:
        print("usage: identity-check.py <manifest.json>", file=sys.stderr)
        print("       the manifest is per-host data and lives with the host, not with this script", file=sys.stderr)
        return 2
    manifest_path = argv[0]
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        targets = manifest["targets"]
        if len(targets) < 1:
            raise ValueError("no targets")
    except Exception as exc:
        print(f"unusable manifest {manifest_path}: {exc}", file=sys.stderr)
        return 2

    # A manifest may declare hostnames it CANNOT assert, with reasons. Printing the checked ones and silently
    # dropping these makes "all N host(s) serve their own application" read as complete when it is partial —
    # which breaks the one rule this tool exists to enforce: NOT COVERED must never look like covered and fine.
    uncovered = manifest.get("_not_yet_covered")
    uncovered = uncovered if isinstance(uncovered, dict) else {}

    markers = {t["name"]: t["expect"] for t in targets}
    failures: list[str] = []

    for target in targets:
        name, url, expect = target["name"], target["url"], target["expect"]
        others = {n: m for n, m in markers.items() if n != name and m != expect}

        try:
            status, body = fetch(url)
        except urllib.error.HTTPError as exc:
            failures.append(f"{name}: {url} returned HTTP {exc.code}")
            print(f"  FAIL {name:<22} HTTP {exc.code}")
            continue
        except Exception as exc:
            failures.append(f"{name}: {url} unreachable — {type(exc).__name__}: {exc}")
            print(f"  FAIL {name:<22} unreachable ({type(exc).__name__})")
            continue

        problems = []
        if status != 200:
            problems.append(f"HTTP {status}")
        if expect not in body:
            problems.append(f"own marker {expect!r} ABSENT")
        impostors = [n for n, m in others.items() if m in body]
        for impostor in impostors:
            problems.append(f"serving {impostor!r} instead — its marker {others[impostor]!r} is present")

        if problems:
            failures.append(f"{name} ({url}): " + "; ".join(problems))
            print(f"  FAIL {name:<22} {'; '.join(problems)}")
        else:
            print(f"  ok   {name:<22} HTTP {status}, own marker present, {len(others)} impostor(s) ruled out")

    for host in sorted(uncovered):
        why = uncovered[host]
        reason = " ".join(why) if isinstance(why, list) else str(why)
        reason = " ".join(reason.split())
        print(f"  ----  {host:<22} NOT COVERED")
        print(f"        {reason[:100]}{'...' if len(reason) > 100 else ''}")

    if failures:
        print(f"\nIDENTITY CHECK FAILED — {len(failures)} of {len(targets)} checked host(s) wrong:")
        for f in failures:
            print(f"  - {f}")
        if uncovered:
            print(f"  ...and {len(uncovered)} further host(s) were NOT CHECKED at all (above).")
        return 1

    if uncovered:
        total = len(targets) + len(uncovered)
        print(f"\nOK — the {len(targets)} CHECKED host(s) serve their own application.")
        print(f"   But {len(uncovered)} of {total} declared host(s) were NOT CHECKED. Not covered is not the same")
        print(f"   as fine — nothing here says anything about them.")
        return 0

    print(f"\nOK — all {len(targets)} host(s) serve their own application.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
