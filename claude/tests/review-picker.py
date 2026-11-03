#!/usr/bin/env python3
"""Cases for `claude/scripts/review_picker.py`, the page `/review-manual` and `/wrap-up` show so the user can change
what should not go as recommended.

What the caller acts on is the exit status and the one JSON line, so most cases pin those: an answer comes back with
every row's choice, its notes and its flags, a closed page is never read as "take the recommendations", and outside
agterm the page asks to be copied.
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
            json.dump({"title": "Review", "status": {"text": "moves <past>", "ok": False, "detail": "2 wait"}, "flags": [{"id": "push", "label": "Push", "value": True}], "blocks": [
                {"kind": "table", "heading": "Triage", "columns": ["#", "Verdict"], "rows": [["1", "<b>fixed</b>"]]},
                {"kind": "triage", "heading": "Review", "rows": [
                    {"id": "r2-1", "finding": "rows dropped", "lens": "correctness", "file": "a/b.py", "frequency": "plausible", "cost": "recoverable", "disposition": "fix", "outcome": "applied"},
                    {"id": "polish-edit-5", "finding": "reworded", "lens": "docs-relevance", "file": "c.md", "disposition": "polish", "outcome": None, "why": None}]},
                {"kind": "choices", "heading": "Findings", "note_choice": "fix", "columns": [{"key": "finding", "label": "Finding"}], "rows": [
                    {"id": "r1-1", "finding": "<script>alert(1)</script>", "choices": ["fix", "leave"], "choice": "fix"},
                    {"id": "r1-2", "finding": "plain", "choices": ["fix", "leave"], "choice": "leave", "dim": True}]},
                {"kind": "text", "heading": "Commits", "text": "feat: <x>\n\nbody"},
                {"kind": "list", "heading": "Plan", "items": [{"text": "feat(a): <one>", "note": "whole file"}, {"rule": "review <bookmark>"}, {"text": "fix(b): two"}]},
                {"kind": "prose", "text": "Push to <origin>.\n\nBookmark moves."}]}, handle)
        bin_dir = os.path.join(scratch, "bin")
        os.mkdir(bin_dir)
        base = {key: value for key, value in os.environ.items() if key != "AGTERM_SESSION_ID"}
        inside = {**base, "AGTERM_SESSION_ID": "test-session", "PATH": f"{bin_dir}{os.pathsep}{base.get('PATH', '')}"}

        done = run(rows, "--render-only", env=base)
        check("render-only exits 0", done.returncode, 0)
        page = open(done.stdout.strip(), encoding="utf-8").read()
        check("a finding's markup is escaped", ("<script>alert(1)" in page, "&lt;script&gt;alert(1)" in page), (False, True))
        check("read-only blocks are escaped too", ("<b>fixed</b>" in page, "feat: &lt;x&gt;" in page), (False, True))
        check("a rule item is a green labelled entry, escaped", '<li class="rule"><span>review &lt;bookmark&gt;</span></li>' in page, True)
        check("the status sits in the title row, red when not ok, escaped", ('<span class="bad">moves &lt;past&gt;</span><div>2 wait</div></div></header>' in page), True)
        check("a list block shows each item in monospace, a note only where given", (page.count("<li><code>"), "<code>feat(a): &lt;one&gt;</code>" in page, page.count('<span class="note">')), (2, True, 1))
        check("a prose block is escaped paragraphs, outside the preformatted block", (page.count('<p class="prose">'), "Push to &lt;origin&gt;." in page), (2, True))
        check("each row preselects its recommendation and nothing else", (page.count('value="fix" checked>'), page.count('value="leave" checked>'), page.count(" checked>")), (1, 1, 3))
        check("only the dim row is greyed", page.count('class="item dim"'), 1)
        check("rows are numbered by position, with the full id and file on hover", (">2</b>" in page, 'title="polish-edit-5 · c.md"' in page), (True, True))
        check("only an applied outcome turns the disposition green", page.count('class="disp applied"'), 1)
        check("an absent or null triage field prints nothing", ("None" in page, "<span class=\"meta\"></span>" not in page.split("polish-edit-5")[-1]), (False, False))
        check("a note selects the block's note_choice", page.count('data-note-choice="fix"'), 2)

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

            answer = {"choices": {"r1-1": "fix", "r1-2": "fix"}, "notes": {"r1-2": "keep the old name"}, "flags": {"push": False}}
            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": json.dumps(answer)}), 0)
            done = run(rows, env=inside)
            check("a submitted page exits 0", done.returncode, 0)
            check("the choices, notes and flags come back", printed(done), {"outcome": "submitted", **answer})

            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "dismissed"}), 2)
            done = run(rows, env=inside)
            check("a closed page exits 2, not as an empty answer", (done.returncode, printed(done)), (2, {"outcome": "dismissed"}))

            stub(bin_dir, json.dumps({"pageID": "p", "outcome": "submitted", "value": '["r1-1"]'}), 0)
            check("a value without choices, notes and flags is an error", run(rows, env=inside).returncode, 1)

            stub(bin_dir, "boom", 1)
            check("an agtermctl failure exits 1", run(rows, env=inside).returncode, 1)

        broken = os.path.join(scratch, "broken.json")
        with open(broken, "w", encoding="utf-8") as handle:
            json.dump({"blocks": [{"kind": "choices", "rows": [{"finding": "no id", "choices": ["fix"], "choice": "fix"}]}]}, handle)
        check("a row without an id is refused", run(broken, "--render-only", env=base).returncode, 1)
        for label, block in (("a recommendation outside the row's choices", {"kind": "choices", "rows": [{"id": "a", "choices": ["fix"], "choice": "drop"}]}),
                             ("an id used twice", {"kind": "choices", "rows": [{"id": "a", "choices": ["x"], "choice": "x"}, {"id": "a", "choices": ["x"], "choice": "x"}]}),
                             ("a note_choice some row lacks", {"kind": "choices", "note_choice": "fix", "rows": [{"id": "a", "choices": ["save", "skip"], "choice": "save"}]}),
                             ("an unknown block kind", {"kind": "chart"}),
                             ("a choices block with string columns", {"kind": "choices", "columns": ["finding"], "rows": [{"id": "a", "choices": ["x"], "choice": "x"}]}),
                             ("a table with object columns", {"kind": "table", "columns": [{"key": "a"}], "rows": []}),
                             ("a table with object rows", {"kind": "table", "rows": [{"id": "r1-1", "finding": "x"}]})):
            with open(broken, "w", encoding="utf-8") as handle:
                json.dump({"blocks": [block]}, handle)
            # A crash also exits 1, so a refusal is told apart by the absence of a traceback.
            done = run(broken, "--render-only", env=base)
            check(f"{label} is refused", (done.returncode, "Traceback" in done.stderr), (1, False))

    print(f"review picker tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
