#!/usr/bin/env python3
"""Cases for `claude/hooks/workflow-realism.py`.

The hook is a backstop with two ways to fail. Silent on a loop that fixes without rating realism,
it lets the next 125-finding run through; noisy on a workflow that only reviews, or on one already
going through the saved `review-and-fix` workflow, it teaches the reader to skip it. Each case runs
the real hook as a subprocess with a Workflow payload, exactly as PreToolUse delivers one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, "claude", "hooks", "workflow-realism.py")
SAVED = os.path.join(ROOT, "claude", "workflows", "review-and-fix.js")

failures: list[str] = []

FIXING = "const r = await agent('review'); await agent(`Fix these confirmed defects: ${r}`)"
# The shape real prompts take in script source: a literal backslash-n right before the verb.
AFTER_ESCAPE = "const r = await agent('review'); await agent(`${CTX}\\n\\nFix these confirmed defects:\\n${r}`)"
APPLYING = "await agent(`${CTX}\\n\\nApply fixes for these confirmed defects in the working tree`)"
GATE_REPAIR = "await agent(`${CTX}\\n\\nImplement the plan. Fix every compile error, analyzer warning and test failure until the gate exits 0.`)"
APPROVED = "await agent(`The user approved these seven findings; fix each one in those files.`)"
FIXING_WITH_REALISM = FIXING + "\nconst SCHEMA = {properties: {frequency: {}, reached_by: {}}}"
CALLING_SAVED = FIXING + "\nawait workflow('review-and-fix', {scope: 'x', lenses: []})"
REVIEW_ONLY = "await agent('Review the diff; include a suggested_fix for each finding')"


def run(stdin: str) -> tuple[int, str, str]:
    done = subprocess.run([sys.executable, "-S", HOOK], input=stdin, capture_output=True, text=True, timeout=30)
    return done.returncode, done.stdout, done.stderr


def warns(label: str, tool_input: object, want: bool) -> None:
    code, out, err = run(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Workflow", "tool_input": tool_input}))
    if code != 0 or err:
        failures.append(f"  FAIL {label}: exit {code}, stderr {err!r}")
        return
    got = bool(out.strip())
    if got != want:
        failures.append(f"  FAIL {label}: warned={got}, want {want} ({out[:120]!r})")
        return
    if want:
        context = json.loads(out)["hookSpecificOutput"]
        if context.get("hookEventName") != "PreToolUse" or "review-and-fix" not in context.get("additionalContext", ""):
            failures.append(f"  FAIL {label}: the warning does not name the saved workflow: {out[:200]!r}")
        if "permissionDecision" in context:
            failures.append(f"  FAIL {label}: the warning makes a permission decision, so it is no longer non-blocking")


def main() -> None:
    warns("an inline loop that fixes findings warns", {"script": FIXING}, True)
    warns("a fix verb right after a \\n escape in the source warns", {"script": AFTER_ESCAPE}, True)
    warns("'apply fixes for these defects' counts as a fix stage", {"script": APPLYING}, True)
    warns("fixing gate failures is not a review loop", {"script": GATE_REPAIR}, False)
    warns("fixing items named without findings or defects is left alone", {"script": APPROVED}, False)
    warns("a loop whose findings carry frequency and reached_by is left alone", {"script": FIXING_WITH_REALISM}, False)
    warns("a loop that calls the saved workflow is left alone", {"script": CALLING_SAVED}, False)
    warns("a review that only suggests fixes is left alone", {"script": REVIEW_ONLY}, False)
    warns("running the saved workflow by name is left alone", {"name": "review-and-fix", "args": {}}, False)
    warns("the saved workflow's own script passes its own gate", {"script": open(SAVED, encoding="utf-8").read()}, False)

    scratch = tempfile.mkdtemp(prefix="workflow-realism-test-")
    try:
        path = os.path.join(scratch, "loop.js")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(FIXING)
        warns("a scriptPath run is judged by the file it names", {"scriptPath": path}, True)
        warns("a scriptPath that does not exist is left alone", {"scriptPath": os.path.join(scratch, "missing.js")}, False)
    finally:
        for name in os.listdir(scratch):
            os.remove(os.path.join(scratch, name))
        os.rmdir(scratch)

    for label, stdin in (("empty stdin", ""), ("non-JSON stdin", "not json"), ("a JSON list", "[]"), ("no tool_input", "{}")):
        code, out, err = run(stdin)
        if (code, out, err) != (0, "", ""):
            failures.append(f"  FAIL {label} must exit 0 silently: exit {code}, out {out!r}, err {err!r}")

    for line in failures:
        print(line)
    print(f"workflow-realism tests: {'all cases behave' if not failures else f'{len(failures)} failure(s)'}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
