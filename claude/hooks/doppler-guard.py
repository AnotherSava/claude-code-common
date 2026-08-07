#!/usr/bin/env python3
"""PreToolUse backstop: when a tool call touches Doppler, inject the conventions.

The always-loaded CLAUDE.md pointer is the primary, early trigger; this is the
deterministic net under it. It injects the gotchas so a wrong project/config gets
corrected at the command/write moment even if the pointer was glossed.

Registered in settings.json under `"matcher": "^(Bash|Write|Edit)$"` — a hook
matcher scopes by tool *name* only, so the argument-level filtering happens below:
any Bash command, or Write/Edit content/path, that mentions Doppler *anywhere*
matches (not just a leading `doppler ...` verb). Silent (exit 0, no output) when
Doppler isn't involved.
"""
import json
import re
import sys

REMINDER = (
    "Doppler is involved here. Before writing a project/config or running the command, "
    "verify against ~/.claude/memory/feedback_doppler_secrets.md — don't guess. Gotchas: "
    "`sava` is the WORKPLACE, not a project (run `doppler projects`; use a per-app project); "
    "default config is `dev`, not `prd`; set secrets with "
    "`doppler secrets set KEY=\"value\" -p <proj> -c dev --silent` (always quote the value — "
    "unquoted metacharacters silently set nothing); commit a `doppler.yaml`."
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never break a tool call on a parse hiccup
    tool_input = data.get("tool_input") or {}
    blob = "\n".join(
        v for k in ("command", "content", "new_string", "old_string", "file_path")
        for v in [tool_input.get(k)] if isinstance(v, str)
    )
    if not re.search(r"doppler", blob, re.IGNORECASE):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": REMINDER},
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
