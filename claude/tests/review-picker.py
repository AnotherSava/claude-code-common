#!/usr/bin/env python3
"""Cases for `claude/scripts/review_picker.py`, the table `/review-manual` shows so the user can tick what gets fixed.

What the caller acts on is the exit status and the one JSON line, so most cases pin those: an answer comes back with
its ids and feedback, a closed page is never read as "fix nothing", and outside agterm the page asks to be copied.
`agtermctl` is replaced by a stub on PATH that answers the way the real one documents, since the real one would open
an overlay over the user's session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PICKER = os.path.join(ROOT, "claude", "scripts", "review_picker.py")

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def run(rows: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, PICKER, rows, *args], capture_output=True, text=True, env=env, timeout=30)


def printed(done: subprocess.CompletedProcess[str]) -> object:
    """The JSON line the picker printed, or its raw stdout when that is not JSON, so a broken case fails rather than crashes."""
    try:
        return json.loads(done.stdout)
    except ValueError:
        return done.stdout


def stub(bin_dir: str, stdout: str, status: int) -> None:
    """An agtermctl that prints what a blocking HTML overlay prints and exits with its status."""
    path = os.path.join(bin_dir, "agtermctl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"#!/bin/sh\ncat <<'EOF'\n{stdout}\nEOF\nexit {status}\n")
    os.chmod(path, 0o755)


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        rows = os.path.join(scratch, "review-findings.json")
        with open(rows, "w", encoding="utf-8") as handle:
            json.dump({"title": "Review", "rows": [{"id": "r1-1", "finding": "<script>alert(1)</script>", "rating": "rare, recoverable", "view": "Fix", "fix": True}, {"id": "r1-2", "finding": "plain", "rating": "theoretical", "view": "Drop", "fix": False, "wording": True}]}, handle)
        bin_dir = os.path.join(scratch, "bin")
        os.mkdir(bin_dir)
        base = {key: value for key, value in os.environ.items() if key != "AGTERM_SESSION_ID"}
        inside = {**base, "AGTERM_SESSION_ID": "test-session", "PATH": f"{bin_dir}{os.pathsep}{base.get('PATH', '')}"}

        done = run(rows, "--render-only", env=base)
        check("render-only exits 0", done.returncode, 0)
        page = open(done.stdout.strip(), encoding="utf-8").read()
        check("a finding's markup is escaped", ("<script>alert(1)" in page, "&lt;script&gt;alert(1)" in page), (False, True))
        check("only the recommended row is pre-ticked", page.count(" checked>"), 1)
        check("only the wording-only row is greyed", page.count('<tr class="wording">'), 1)

        check("outside agterm the page copies its answer instead of submitting", ("Copy answer" in page, "overlay.submit" in page, "overlay.close" in page), (True, False, False))
        # Outside agterm the picker publishes the page on the tailnet for real, which a test must not do from the
        # commit gate; that path was run by hand against a live node when it was written.
        print("  NOT COVERED publishing outside agterm (exit 4, or 3 when publishing fails)")

        # agterm is macOS-only, and a Windows PATH lookup matches only PATHEXT extensions, so the extensionless
        # stub is invisible there and the picker never gets past "not inside agterm".
        if os.name == "nt":
            print("  NOT COVERED the inside-agterm cases: agterm does not run on Windows")
        else:
            stub(bin_dir, "", 0)
            inside_page = open(run(rows, "--render-only", env=inside).stdout.strip(), encoding="utf-8").read()
            check("inside agterm the page submits the overlay", ("overlay.submit" in inside_page, "Copy answer" in inside_page), (True, False))

            answer = {"fix": ["r1-1"], "feedback": {"r1-1": "keep the old name"}}
            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": json.dumps(answer)}), 0)
            done = run(rows, env=inside)
            check("a submitted page exits 0", done.returncode, 0)
            check("the ids and feedback come back", printed(done), {"outcome": "submitted", **answer})

            empty = {"fix": [], "feedback": {}}
            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": json.dumps(empty)}), 0)
            done = run(rows, env=inside)
            check("nothing ticked is still an answer", (done.returncode, printed(done)), (0, {"outcome": "submitted", **empty}))

            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "dismissed"}), 2)
            done = run(rows, env=inside)
            check("a closed page exits 2, not as an empty answer", (done.returncode, printed(done)), (2, {"outcome": "dismissed"}))

            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": '["r1-1"]'}), 0)
            check("a value without fix and feedback is an error", run(rows, env=inside).returncode, 1)

            stub(bin_dir, "boom", 1)
            check("an agtermctl failure exits 1", run(rows, env=inside).returncode, 1)

        broken = os.path.join(scratch, "broken.json")
        with open(broken, "w", encoding="utf-8") as handle:
            json.dump({"rows": [{"finding": "no id"}]}, handle)
        check("a row without an id is refused", run(broken, "--render-only", env=base).returncode, 1)

    print(f"review picker tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
