#!/usr/bin/env python3
r"""
workflow-realism.py — warn when a workflow fixes what it reviews without rating realism.

A PreToolUse hook on the Workflow tool. An inline script with a stage that fixes findings
("fix these confirmed defects", "apply fixes for these findings") whose text mentions none of
`frequency`, `reached_by` or the saved `review-and-fix` workflow gets a reminder as
additionalContext. Any mention of those words silences it, whatever they are used for. It never
blocks: the workflow launches either way, and the reminder names the saved workflow so the next
one can run through it.

The fix verb must take findings, defects, issues or bugs as its object. Gate repair ("fix every
compile error and test failure") and fixes to findings the user already triaged ("fix each one in
those files") are not review loops, and a warning on them asks a session to abort a legitimate run.
The script is raw JS source, where a prompt reads `${CTX}\n\nFix these...`: the `n` of that escape
leaves no word boundary before the verb, so `\n`, `\r` and `\t` escapes are read as spaces.

The gate exists because a loop that verifies and fixes on its own shows its findings to nobody, so
`feedback_realism_before_hardening` never fires. Measured in tauri-dashboard on 2026-10-02: 10
review rounds confirmed 125 findings, 85 of them rated low, and coded every one.

A run by scriptPath is judged by that file. A run by name is not judged: a saved workflow is
reviewed when it is written, and `review-and-fix` is the one this points to. The script never
raises and exits 0 on every path.
"""
from __future__ import annotations

import json
import re
import sys

SAVED = "review-and-fix"

FIX_STAGE = re.compile(
    r"\b(?:fix|apply (?:the |these |all )?fix(?:es)? (?:for|to)) "
    r"(?:these |those |the |each |every |all (?:the |these |of the )?)?(?:confirmed |verified )?"
    r"(?:finding|defect|issue|bug)s?\b",
    re.IGNORECASE,
)
ESCAPE = re.compile(r"\\[nrt]")
REALISM = re.compile(r"\bfrequency\b|\breached_by\b|" + re.escape(SAVED))

REMINDER = (
    f"This workflow fixes what it reviews, but its script never rates realism — no `frequency`, no "
    f"`reached_by`, no call to the saved `{SAVED}` workflow. A loop that verifies and fixes on its own "
    f"shows its findings to nobody, so feedback_realism_before_hardening never fires: every confirmed "
    f"edge case gets code. Run review loops through the saved workflow instead — "
    f"Workflow({{name: \"{SAVED}\", args: {{scope, lenses: [{{key, prompt}}], context, gate}}}}) — which "
    f"makes every finding carry who reaches it, how often and what it costs, triages in code, caps at "
    f"two rounds and returns the triage table. If this one is already running, consider stopping it "
    f"and relaunching that way; otherwise present its findings as a triage with realism ratings, not "
    f"as \"all fixed\"."
)


def script_text(tool_input: dict) -> str | None:
    script = tool_input.get("script")
    if isinstance(script, str):
        return script
    path = tool_input.get("scriptPath")
    if isinstance(path, str):
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return None
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict) or tool_input.get("name") == SAVED:
        return 0
    text = script_text(tool_input)
    if text is None:
        return 0
    text = ESCAPE.sub(" ", text)
    if not FIX_STAGE.search(text) or REALISM.search(text):
        return 0
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": REMINDER},
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
