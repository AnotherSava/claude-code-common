"""A stand-in for `agtermctl`, for the suites that show a page over an agterm session: the stub on PATH, the
environments that put a process inside agterm and keep it outside, and the two replies a blocking overlay gives.

One module because claude/tests/review-picker.py and claude/tests/memos.py both drive
claude/scripts/review_picker.py through this stub. A reply changed in one copy and not the other would leave a suite
passing against a protocol the real tool no longer speaks.
"""

from __future__ import annotations

import json
import os
from typing import Optional

# agterm is macOS-only, and a Windows PATH lookup matches only PATHEXT extensions, so the extensionless stub is
# invisible there and the picker never gets past "not inside agterm". A suite prints this as its NOT COVERED reason.
UNAVAILABLE: Optional[str] = "agterm does not run on Windows" if os.name == "nt" else None


def outside() -> dict[str, str]:
    """This process's environment with no agterm session in it."""
    return {key: value for key, value in os.environ.items() if key != "AGTERM_SESSION_ID"}


def inside(bin_dir: str) -> dict[str, str]:
    """This process's environment as a session inside agterm, with the stub in `bin_dir` first on PATH."""
    base = outside()
    return {**base, "AGTERM_SESSION_ID": "test-session", "PATH": f"{bin_dir}{os.pathsep}{base.get('PATH', '')}"}


def stub(bin_dir: str, stdout: str, status: int) -> None:
    """An agtermctl that prints `stdout` and exits with `status` for every call it gets."""
    path = os.path.join(bin_dir, "agtermctl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"#!/bin/sh\ncat <<'EOF'\n{stdout}\nEOF\nexit {status}\n")
    os.chmod(path, 0o755)


def submitted(bin_dir: str, value: object) -> None:
    """Answer every overlay as a page whose Apply sent `value`: the JSON of it as a string, and exit 0."""
    stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": json.dumps(value)}), 0)


def dismissed(bin_dir: str) -> None:
    """Answer every overlay as a page closed without applying: exit 2."""
    stub(bin_dir, json.dumps({"pageID": "p", "outcome": "dismissed"}), 2)
