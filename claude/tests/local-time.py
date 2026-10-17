#!/usr/bin/env python3
"""Cases for `claude/hooks/local-time.py`.

The hook fails two ways. Silent on a UTC stamp, it leaves the model to quote the stored zone, which is the
slip it exists for; firing on a stamp already in local time, or on something only shaped like a date, it
teaches the model to skim the reminder. Each case runs the real hook as a subprocess with a PostToolUse
payload under a pinned zone, so which stamps count as local holds on either machine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, "claude", "hooks", "local-time.py")
# POSIX form, which Windows' C runtime also honours; an IANA name would not be read there.
ENV = {**os.environ, "TZ": "PST8PDT"}

failures: list[str] = []


def run(stdin: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-S", HOOK], input=stdin, capture_output=True, text=True, encoding="utf-8", env=ENV, timeout=10)
    return proc.returncode, proc.stdout


def fires(payload: dict) -> bool | None:
    code, out = run(json.dumps(payload))
    if code != 0:
        return None
    if not out.strip():
        return False
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    return "(PDT, UTC-07:00)" in context


def expect(name: str, tool_response: object, want: bool) -> None:
    got = fires({"tool_name": "Bash", "tool_response": tool_response})
    if got is not want:
        failures.append(f"{name}: expected {'a reminder' if want else 'silence'}, got {got!r}")
    print(f"{'ok ' if got is want else 'FAIL'} {name}")


def bash(stdout: str) -> dict:
    return {"stdout": stdout, "stderr": ""}


expect("iso Z with millis", bash('{"timestamp":"2026-10-16T22:38:25.347Z"}'), True)
expect("git iso offset", bash("Date: 2026-10-16 12:45:41 +0000"), True)
expect("UTC word", bash("started 2026-10-16 12:45:41 UTC"), True)
expect("minute precision", bash("at 2026-10-16T12:45Z"), True)
expect("other zone", bash("2026-10-16T12:00:00+02:00"), True)
expect("git default format", bash("Date:   Thu Oct 16 12:45:41 2026 +0000"), True)
expect("git default single-digit day", bash("Date:   Fri Oct 2 12:45:41 2026 +0000"), True)
expect("HTTP date header", bash("date: Thu, 16 Oct 2026 12:45:41 GMT"), True)
expect("Read payload shape", {"type": "text", "file": {"content": "2026-10-16T12:45:41Z"}}, True)
expect("stderr is scanned", {"stdout": "", "stderr": "error at 2026-10-16T12:45:41Z"}, True)
expect("local stamp after a foreign one", bash("2026-10-16T05:45:41-07:00 then 2026-10-16T12:45:41Z"), True)
expect("local summer stamp is silent", bash("2026-10-16T05:45:41-07:00"), False)
expect("local winter stamp is silent", bash("2026-01-10T04:00:00-08:00"), False)
expect("summer offset in winter fires", bash("2026-01-10T04:00:00-07:00"), True)
expect("local git date is silent", bash("Date:   Thu Oct 16 05:45:41 2026 -0700"), False)
expect("impossible date is silent", bash("2026-13-40T99:00Z"), False)
expect("zone-less stamp is silent", bash("2026-10-16 12:45:41 done"), False)
expect("stamp only in an edit diff is silent", {"stdout": "edited", "stderr": "", "bashEditDiff": {"files": [{"filePath": "x.py", "hunks": [{"lines": ["+ts = '2026-10-16T12:45:41Z'"]}]}]}}, False)
expect("no stamp is silent", bash("plain output"), False)

for name, stdin in [("garbage stdin", "not json"), ("non-dict payload", "[1, 2]")]:
    code, out = run(stdin)
    if code != 0 or out.strip():
        failures.append(f"{name}: exit {code}, stdout {out!r}")
    print(f"{'ok ' if not any(f.startswith(name) for f in failures) else 'FAIL'} {name}")

for failure in failures:
    print(f"  {failure}")
print(f"local-time tests: {len(failures)} failure(s)" if failures else "local-time tests: all cases behave")
sys.exit(1 if failures else 0)
