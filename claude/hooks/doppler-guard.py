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

from _shell import command_argv, commands, nested_scripts, tool_name

REMINDER = (
    "Doppler is involved here. Before writing a project/config or running the command, "
    "verify against the `/doppler` skill (~/.claude/skills/doppler/SKILL.md) — don't guess, and "
    "invoke it outright for anything beyond a single command. Gotchas: "
    "`sava` is the WORKPLACE, not a project (run `doppler projects`); "
    "DO NOT create a project per app — the free plan caps projects at 10 and all are taken, so a NEW "
    "app gets a CONFIG in an existing shard (`prd_<app>` / `dev_<app>`, env-slug prefix required); "
    "in a SHARD a branch config INHERITS ITS ROOT'S SECRETS INCLUDING VALUES, so shard roots stay empty "
    "and you name the full config — but the projects that predate the shards keep real values in their "
    "own `dev`/`prd`, where a bare `-c prd` is correct, so read the coordinate off the project "
    "(`doppler configs -p <proj>`) rather than deriving it from the rule; "
    "set/delete secrets with "
    "`doppler secrets set KEY=\"value\" -p <proj> -c <config> --silent` (always quote the value — "
    "unquoted metacharacters silently set nothing; `set` AND `delete` both print the full "
    "secrets table with values unless `--silent`); commit a `doppler.yaml`. When only the user "
    "holds the value, offer to pipe it in from their clipboard (`cat /dev/clipboard | tr -d '\\r'` "
    "into stdin) as well as handing them a command to run themselves."
)

# `doppler secrets set`/`delete` print the whole secrets table (every value) after the
# operation unless silenced — the classic transcript leak. Require --silent on both.
#
# JUDGED IN COMMAND POSITION, and that is a fix rather than a refinement. Matching the verb
# anywhere in the line blocked `grep "doppler secrets set" docs/`, a `sed` range over the same
# text, and this file's own test payloads — three times in twenty minutes while editing these
# very docs. So the class it blocked hardest was documenting and auditing the rule it enforces,
# which is both useless and the moment you can least afford a hard block. `_shell` tokenizes the
# command the way bash does and yields each simple command it would run — inside loops,
# subshells and `$( … )` too — and never one made of quoted text, a comment or a heredoc body.


def unsilenced_write(command: str, depth: int = 0) -> bool:
    """Does this command run `doppler secrets set/delete` without `--silent`?

    Judged PER COMMAND. Checking `"--silent" not in command` over the whole line let a flag
    belonging to some *other* command exempt a genuinely unsafe write — `doppler secrets set A=b
    && echo done --silent` passed, and so did any compound whose later half happened to carry it.
    `--help` prints usage rather than the table, so it is exempt, but only as a word of its own:
    `doppler secrets set FLAG="--help"` still sets a secret. A command sent to another shell —
    over ssh, through `bash -c`, on a heredoc — is judged the same way.
    """
    for found in commands(command):
        argv = command_argv(found.argv)
        if depth < 3 and any(unsilenced_write(script, depth + 1) for script in nested_scripts(argv, found.stdin)):
            return True
        if len(argv) < 3 or tool_name(argv[0]) != "doppler":
            continue
        if argv[1].lower() != "secrets" or argv[2].lower() not in ("set", "delete"):
            continue
        silent = any(a == "--silent" or a.startswith("--silent=") for a in argv)
        if not silent and not any(a in ("-h", "--help") for a in argv):
            return True
    return False

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
    if not isinstance(data, dict):
        return 0  # valid JSON of the wrong shape is still nothing to act on
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0  # a malformed payload is nothing to act on, and must not raise
    command = tool_input.get("command")
    blob = "\n".join(
        v for k in ("command", "content", "new_string", "old_string", "file_path")
        for v in [tool_input.get(k)] if isinstance(v, str)
    )
    if not re.search(r"doppler", blob, re.IGNORECASE):
        return 0

    # Hard-block a real set/delete run that omits --silent (Bash command only), except when
    # it is only asking for usage.
    if isinstance(command, str) and unsilenced_write(command):
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
