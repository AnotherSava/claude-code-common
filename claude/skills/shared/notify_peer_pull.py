#!/usr/bin/env python3
"""Ask the session working on this repo on the OTHER machine to pull what was just pushed.

These repos are worked from two machines, and a clone left behind the remote is how work gets
rebuilt that already exists upstream, or a later commit there fails to push. So once a push has
succeeded, the same project's session on the peer is asked to run `/pull`. Delivery, addressing and
receipts are `peer_relay.py`'s; this script only composes the request.

Every skill that pushes calls this, which is why it lives here rather than under one of them: a
release or a PR merge leaves the peer exactly as far behind as a commit does. The skill names itself
in the second argument, which the relay carries as the sender's label and the receiving session is
shown: a message from `/commit` arrives there headed `Sender's own description: the /commit skill,
after a push`.

Takes the upstream sha recorded before the push (`none` on a first push) to list what was pushed.
Prints one `peer-pull:` line per peer device, or one saying the other machine was unmeasured.
"""
from __future__ import annotations

import re
import subprocess
import sys

from peer_relay import PeerUnmeasured, current_project, describe, send_to_project


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def compose(before: str) -> str:
    slug = re.sub(r"\.git$", "", re.sub(r"^.*github\.com[:/]", "", git("remote", "get-url", "origin"))).rstrip("/")
    head = git("rev-parse", "HEAD")
    commits = git("log", "--format=- %h %s", f"{before}..{head}" if before != "none" else "-n20")
    return (
        f"I just pushed to {slug}, branch {git('rev-parse', '--abbrev-ref', 'HEAD')}; the remote is now at {head}. "
        f"Commits in this push:\n{commits}\n\n"
        "Your clone of this repo is behind by these commits. Please bring it up to date by invoking the "
        "`pull` skill (/pull) — it fetches, moves aside only the local edits that collide with the "
        "incoming files, fast-forwards, and restores them. No reply needed."
    )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notify_peer_pull.py <upstream-sha-before-push | none> <skill-name>", file=sys.stderr)
        return 2
    sender = f"the /{sys.argv[2]} skill, after a push"
    try:
        for target, receipt in send_to_project(current_project(), compose(sys.argv[1]), sender):
            print(f"peer-pull: {describe(target, receipt)}")
    except PeerUnmeasured as exc:
        print(f"peer-pull: NOT SENT — {exc}, so the other machine is unmeasured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
