#!/usr/bin/env python3
"""Say once per session how far this repo is from the conventions the dotfiles repo defines.

    python -S ~/.claude/hooks/conventions-check.py     # SessionStart hook, silent when current

Why this exists: a convention written in `claude/CLAUDE.md` is a claim about every repo on the
machine, and changing one leaves the others in the old shape with nothing anywhere saying so. The
one such change made by hand reached nine repos but was committed in only four of them, missed
`what-is-next` entirely — its backlog sat in a file `memos.py` cannot list, two days on — and left
the other five holding the work uncommitted. Afterwards "skipped deliberately" and "missed" were
indistinguishable, which is the state this notice exists to end.

**Being behind is a level, not an edge** — it stays true until someone runs `/adopt` — so sampling
it once per session catches it reliably, unlike the state checks warned about in
`feedback_sample_level_miss_edge`. Re-reporting after a `/clear` is correct for the same reason.

It compares two integers and asserts nothing: the record says how far this repo's migrations have
run, which is a claim about the moment `/adopt` wrote it. What has to hold *continuously* is not
this hook's to sample at all — it belongs to `check.py`, which every repo's commit gate runs.
Running the rules here would cost an order of magnitude more than the whole hook budget, and grows
with each rule added.

No subprocess at all, deliberately. It reads the two record files, one `listdir` of the versions
directory with a head-read of each frontmatter block, and this checkout's `.git/HEAD` for the short
sha — so the cost is the interpreter start plus about a dozen small reads. Record parsing and
version loading come from `engine.py` rather than being re-implemented here: two readers of one
format drift the day either gains a field, and the record is what every later decision believes.

Silence is reserved for three things and is never accidental: a repo that is current, a repo whose
origin belongs to someone else, and a repo carrying an `exempt` line. Everything else gets a
sentence, including the states where this hook cannot tell.
"""

import json
import os
import sys

# The versions and both record formats live in `claude/conventions/`; reach it the way
# `memos-surface.py` reaches `memos.py`. `abspath` rather than `realpath` so this works whether the
# hook was invoked through ~/.claude/hooks or straight out of the checkout.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conventions"))

try:
    import engine  # noqa: E402 — needs the sys.path line above
except BaseException:
    # The never-raise guard at the foot of this file cannot reach a module-level import: measured,
    # a syntax error in the engine made this hook print a traceback and exit 1 at every session
    # start. A hook that cannot read the version set has nothing trustworthy to say, so it says
    # nothing — and `check-install.py` is what reports an install this broken.
    engine = None

# Fifteen bullets at every session start is a wall nobody reads; five and a count is the whole gap.
MAX_BULLETS = 5


def _payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return {}
    # Valid JSON of the wrong shape reaches every caller as a dict-shaped thing that is not one.
    return payload if isinstance(payload, dict) else {}


def _say(message: str) -> None:
    """A systemMessage reaches the user's screen and never the transcript.

    Which is why `/adopt` re-derives the gap itself with `engine.py status` rather than trusting
    the model to have read this.
    """
    print(json.dumps({"systemMessage": message}))


def _repo_root(start: str) -> str | None:
    """The nearest ancestor holding a `.git`, or None. A worktree's `.git` is a file, not a dir."""
    current = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _render(pending: list, unwired: list, adopted: int, latest: int, sha: str) -> str:
    """The gap as the user reads it: the numbers, at most five bullets, and the one command."""
    if pending:
        count = f"{len(pending)} version{'' if len(pending) == 1 else 's'} behind"
        head = f"Conventions in this repo are {count} (at v{adopted}, latest is v{latest}, dotfiles at {sha})."
    else:
        count = f"{len(unwired)} machine-side version{'' if len(unwired) == 1 else 's'}"
        head = (f"Conventions in this repo are current (v{latest}, dotfiles at {sha}), "
                f"but {count} decided here {'is' if len(unwired) == 1 else 'are'} not wired on this machine.")
    # One list, sorted by version before it is truncated: an unwired machine version appended after
    # the `... N more` line reads as out of order, and it is the line most likely to be cut.
    lines = [(version.number, f"  - v{version.number:<3} {version.title}") for version in pending]
    lines += [(version.number, f"  - v{version.number:<3} {version.title} — decided in this repo, not wired on this machine")
              for version in unwired]
    lines.sort()
    bullets = [text for _, text in lines[:MAX_BULLETS]]
    if len(lines) > MAX_BULLETS:
        bullets.append(f"  - ... {len(lines) - MAX_BULLETS} more")
    return "\n".join([head, *bullets, "Run /adopt to catch up."])


def main() -> int:
    # An unrecognised argv[1] is a no-op, so a stale command string in settings.json cannot
    # resurrect a mode that was removed.
    if len(sys.argv) > 1 or engine is None:
        return 0

    payload = _payload()
    start = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    root = _repo_root(start)
    if root is None:
        # Three real project directories have no `.git` at all, one of them with its own `.claude/`
        # and CLAUDE.md. Under silence they would sit outside this system with no line anywhere
        # saying so; a scratch directory, which has neither, still says nothing.
        if os.path.isdir(os.path.join(start, ".claude")) or os.path.isfile(os.path.join(start, "CLAUDE.md")):
            _say("Conventions cannot be recorded here: this is not a git repo.")
        return 0

    # Whose repos adopt these conventions is `engine.is_third_party`, not a copy here: the two
    # disagreed, and this hook was silent in the `agterm` clone while `/adopt` offered to walk
    # thirteen versions there.
    if engine.is_third_party(root) is not None:
        return 0

    record = engine.read_record(root)
    if record.error:
        _say(engine.parse_error_message(record))
        return 0
    if record.exempt:
        return 0

    try:
        versions = engine.load_versions()
    except BaseException as exc:
        # A half-written README is the normal state while a version is being authored, and an
        # unguarded raise here reaches the foot-of-file guard, which turns it into silence in
        # every repo on the machine — the one failure mode this notice cannot afford, since
        # nothing else looks at the version set until someone runs `engine.py` by hand.
        _say(f"The convention versions in the dotfiles repo could not be read ({exc}). "
             f"Whether this repo is behind is unknown until that is fixed.")
        return 0
    if not versions:
        return 0
    latest, sha = versions[-1].number, engine.dotfiles_sha()
    if not record.present:
        _say(f"No convention record in this repo (latest is v{latest}, dotfiles at {sha}). "
             f"Run /adopt to record where this repo stands.")
        return 0

    if record.number > latest:
        # This checkout is the behind one. Offering /adopt here would walk a version set older than
        # the record it is reading, so the offer is withheld rather than qualified.
        _say(f"This repo records v{record.number}; the newest version in this dotfiles checkout is v{latest} ({sha}). "
             f"Pull the dotfiles repo before running /adopt.")
        return 0

    # The underscore forms take the pair this hook has already read; `pending(root)` and
    # `unwired(root)` would re-open both record files and re-read every version's frontmatter once
    # more each. Which versions are outstanding is still decided in the engine either way — this
    # hook asks the question, it does not answer it.
    pending = engine._pending(versions, record)
    unwired = engine._unwired(versions, record)
    if pending or unwired:
        _say(_render(pending, unwired, record.number, latest, sha))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Never disrupt Claude Code, whatever went wrong here.
        raise SystemExit(0)
