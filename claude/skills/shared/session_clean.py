#!/usr/bin/env python3
"""Tell the local dashboard that the turn just finished left nothing worth coming back to.

The dashboard carries a CLEAN row state meaning exactly that, and sets it only on positive
evidence. It can see that a turn was started by a relayed peer message, because the frame it
wrote into that session's inbox carries a preamble it minted itself, but never what the message
asked for — the body is stored nowhere. So a pull that changed nothing and a pull that turned
into an afternoon of work are identical from there. This says which one happened. `/pull`
step 10 is the only caller.

Silence is the conservative reading on the receiving side: no post means not clean. Every
failure here is therefore swallowed and the exit status is always 0 — no dashboard running, an
older one without the route, a timeout. Nothing retries: a second attempt only widens the window
in which the turn is still running while the signal claims it ended.

The signal is revocable, and the dashboard owns that half: it drops a claim whose turn never
settled the moment another prompt arrives. That covers the case the design was built around,
where a second relayed message joins a turn already in flight and real work follows a pull that
had already finished cleanly.

The receiving side is `POST /api/session-clean`, and it weighs this against two facts it holds
itself — that a relayed message began the turn, and what the row was before it. So report what
this run did and nothing about the circumstances; `docs/pages/development/classification.md` in
the dashboard repo carries the rule.

This is a stopgap with a known retirement. Claude Code's `UserPromptSubmit` schema already
declares a `source` field whose `system` value marks machine-injected turns; two un-wired
builders are why it never arrives (anthropics/claude-code#94675). Once it does, the dashboard
learns relay-vs-typed without a minted preamble to recognise, and this file is deleted whole.

    session_clean.py        # posts, prints nothing, always exits 0
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from peer_relay import current_project, dashboard_url

ROUTE = "/api/session-clean"
TIMEOUT_SECONDS = 2.0


def _payload() -> dict[str, str]:
    """What identifies this session to the dashboard.

    `session_id` is the identity; a cwd alone cannot separate two sessions open on one repo,
    which is the case the relay already refuses as `ambiguous_target`. The other two are what
    the dashboard keys rows by today, sent so the route can resolve on whichever it prefers.
    """
    return {
        "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
        "cwd": os.getcwd(),
        "project": current_project(),
    }


def main() -> int:
    request = urllib.request.Request(dashboard_url() + ROUTE,
                                     data=json.dumps(_payload()).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS).close()
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
