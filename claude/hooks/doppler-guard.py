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
# ANCHORED TO COMMAND POSITION, and that is a fix rather than a refinement. Matching the verb
# anywhere in the line blocked `grep "doppler secrets set" docs/`, a `sed` range over the same
# text, and this file's own test payloads — three times in twenty minutes while editing these
# very docs. So the class it blocked hardest was documenting and auditing the rule it enforces,
# which is both useless and the moment you can least afford a hard block. A real invocation is
# always in command position: line start, or after `;` `&&` `||` `|` or a newline, optionally
# behind env assignments (`FOO=bar doppler secrets set …`).
_SEGMENT_START = r"(?:^|[;\n]|&&|\|\||\|)"
_ASSIGNMENTS = r"(?:\s*[A-Za-z_][A-Za-z0-9_]*=\S*)*"
_SETDEL = re.compile(
    rf"{_SEGMENT_START}{_ASSIGNMENTS}\s*doppler\s+secrets\s+(?:set|delete)\b", re.IGNORECASE)

# Where the command segment containing a match ends — the next unquoted separator.
_SEGMENT_END = re.compile(r"[;\n]|&&|\|\||\|")

# `doppler secrets set --help` prints usage, not the secrets table, so --silent is beside the
# point there. Match the flag only as its own token, so a value that happens to contain
# `--help` (`doppler secrets set FLAG="--help"`) still gets the block.
_HELP = re.compile(r"(?:^|\s)-(?:h|-help)(?:\s|$)")


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def _mask_quoted(text: str) -> str:
    """Same-length copy with quoted spans and heredoc BODIES blanked, so indices still line up.

    Two ways a line can look like a command and not be one, and the anchor alone catches neither:

    - **Quoting.** `echo "a; doppler secrets set X=1"` has a separator and a verb inside a string
      literal; a naive split reads that as a real command.
    - **Heredoc bodies.** A newline is a segment separator, so every line of `cat <<EOF … EOF` is
      in command position — which makes writing documentation *about* these commands trip the
      block, and that is precisely how this file's own guidance gets written.

    Blanking both means only shell-significant characters can start a segment, while the return
    stays index-compatible with the original so the caller can slice the real text.

    Heredocs go FIRST, and that order is itself the fix rather than a preference: masking quotes
    first blanks the marker in the near-universal `<<'EOF'` form, so the heredoc is never found and
    its whole body stays live. Doing bodies first also means an apostrophe inside one — `don't` in
    a sentence being written to a file — cannot unbalance the quote scan that follows.
    """
    masked = text
    for match in _HEREDOC.finditer(text):
        body = masked.find("\n", match.end())
        if body == -1:
            continue
        marker, cursor = match.group(2), body + 1
        for line in masked[cursor:].split("\n"):
            if line.strip() == marker:
                break
            masked = masked[:cursor] + " " * len(line) + masked[cursor + len(line):]
            cursor += len(line) + 1

    out, quote = list(masked), None
    for i, ch in enumerate(masked):
        if quote is None and ch in "\"'":
            quote = ch
        elif quote is not None:
            out[i] = " "
            if ch == quote:
                quote, out[i] = None, ch
    return "".join(out)


def unsilenced_write(command: str) -> bool:
    """Does this command run `doppler secrets set/delete` without `--silent`?

    Judged PER SEGMENT. Checking `"--silent" not in command` over the whole line let a flag
    belonging to some *other* command exempt a genuinely unsafe write — `doppler secrets set A=b
    && echo done --silent` passed, and so did any compound whose later half happened to carry it.
    """
    masked = _mask_quoted(command)
    for match in _SETDEL.finditer(masked):
        end = _SEGMENT_END.search(masked, match.end())
        segment = command[match.start():end.start() if end else len(command)]
        if "--silent" not in segment and not _HELP.search(segment):
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
