#!/usr/bin/env python3
"""PreToolUse backstop: when a tool call touches Doppler, inject the conventions —
and hard-block the value-dumping footguns.

The `/doppler` skill owns the conventions; the always-loaded CLAUDE.md pointer is
the primary, early trigger. This is the deterministic net under both: it injects
the gotchas inline so a wrong project/config gets corrected at the command/write
moment even if the pointer was glossed and the skill was never invoked.

On top of the reminder it DENIES a `doppler secrets set`/`delete` run that lacks
`--silent`: without it Doppler prints the full secrets table (every value) after
the operation, which leaks secrets into the transcript. The deny inspects only the
Bash `command`, so Write/Edit content that merely mentions the command still gets
the reminder rather than a block. A bare `-h`/`--help` is exempt — it prints usage,
never the table, and blocking it just costs a round trip.

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
    "verify against the `/doppler` skill (~/.claude/skills/doppler/SKILL.md) — don't guess, and "
    "invoke it outright for anything beyond a single command. Gotchas: "
    "`sava` is the WORKPLACE, not a project (run `doppler projects`; use a per-app project); "
    "default config is `dev`, not `prd`; set/delete secrets with "
    "`doppler secrets set KEY=\"value\" -p <proj> -c dev --silent` (always quote the value — "
    "unquoted metacharacters silently set nothing; `set` AND `delete` both print the full "
    "secrets table with values unless `--silent`); commit a `doppler.yaml`. When only the user "
    "holds the value, offer to pipe it in from their clipboard (`cat /dev/clipboard | tr -d '\\r'` "
    "into stdin) as well as handing them a command to run themselves."
)

# `doppler secrets set`/`delete` print the whole secrets table (every value) after the
# operation unless silenced — the classic transcript leak. Require --silent on both.
_SETDEL = re.compile(r"doppler\s+secrets\s+(?:set|delete)\b", re.IGNORECASE)

# `doppler secrets set --help` prints usage, not the secrets table, so --silent is beside the
# point there. Match the flag only as its own token, so a value that happens to contain
# `--help` (`doppler secrets set FLAG="--help"`) still gets the block.
_HELP = re.compile(r"(?:^|\s)-(?:h|-help)(?:\s|$)")

DENY_REASON = (
    "Add --silent to this `doppler secrets set/delete` command. Without it Doppler prints "
    "the FULL secrets table — every value — after the operation, leaking secrets into the "
    "transcript. Re-run the exact command with --silent appended."
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never break a tool call on a parse hiccup
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command")
    blob = "\n".join(
        v for k in ("command", "content", "new_string", "old_string", "file_path")
        for v in [tool_input.get(k)] if isinstance(v, str)
    )
    if not re.search(r"doppler", blob, re.IGNORECASE):
        return 0

    # Hard-block a real set/delete run that omits --silent (Bash command only), except when
    # it is only asking for usage.
    if (
        isinstance(command, str)
        and _SETDEL.search(command)
        and "--silent" not in command
        and not _HELP.search(command)
    ):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_REASON,
            },
        }))
        return 0

    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": REMINDER},
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
