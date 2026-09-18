"""This machine's memory cache for the repo is a link into the repo's committed `.claude/memory/`.

Claude Code writes project memory to a machine-local cache named after the repo's path. Nothing
version-controls it, so what one machine learned about a project is invisible from the other and
gone the day the cache is cleared. `claude/scripts/link-project-memory.sh` redirects that directory,
by a link, at a committed `.claude/memory/` inside the repo: the harness keeps reading and writing
the same path, the files live in git, and a clone carries them.

This is universal rather than versioned, and the difference is which question it answers. A version
asks *did this repo change shape*, once, and the answer never expires. The link is not like that: it
is per-machine, so a repo arrives on a second machine with the work genuinely not done, and it can
break years after anyone adopted anything — a cleared cache, a moved checkout, a Git Bash `ln -s`
that made a copy. There is no number that could be true of both machines at once, which is what the
per-repo machine record tried to be and why it is gone.

A repo with no `.claude/memory/` holds vacuously, and that is positive evidence read off the repo
rather than an absence inferred from this machine: the convention points the cache at a committed
directory, and with no such directory there is nothing to point at. Nothing here ever creates one —
whether a repo keeps project memory at all is not a machine's business.

Paths are compared with `os.path.samefile`, never as strings, and never with `os.path.islink`. On
Git Bash `ln -s` silently makes a copy, and a copy resolves to itself, so `realpath` returns a
sensible path and `isdir` calls it healthy while it mirrors nothing — different inodes is the only
signal. A Windows directory junction has answered `islink` False since Python 3.8, and machines
still hold caches wired by an older version of the script that made junctions, so keying on that
would report every one of them as broken. See `learnings/comparing-paths-symlinks-and-case.md`.

Detection only, and the remediation is `FIX`. Four states the script itself refuses to guess at —
a cache already linked somewhere else, a filename held by both sides, something that is not a
directory at either end, and the repo present under two spellings of its path — are questions for a
human, so this rule names what it found and never mutates anything.
"""

import os
import re

import _git  # the rules directory is on the path, and one git wrapper answers for every rule

REL = ".claude/memory"
FIX = "bash ~/.claude/scripts/link-project-memory.sh   # from inside the repo"

MANGLE_RE = re.compile(r"[^a-zA-Z0-9]")


def project_id(path: str) -> str:
    """The cache directory name the harness derives from a repo path.

    Mirrors `link-project-memory.sh`, which mirrors `gather-context.sh`: every non-alphanumeric
    character becomes one dash, so `:` `/` `\\` `.` and `_` each collapse and a Windows path reaches
    the same name whichever slash it was spelled with.
    """
    return MANGLE_RE.sub("-", path)


def claude_dir() -> str:
    """Where the harness keeps its state — `CLAUDE_CONFIG_DIR` when set, as every other script here.

    A machine that relocates it and a script assuming `~/.claude` disagree silently: the link gets
    made in a directory the harness never opens, so the machine looks wired and is not.
    """
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def toplevel(root: str) -> str:
    """The work tree root as git spells it, which is what the cache name is derived from.

    Raises rather than falling back to `root`: the cache directory is named after exactly this path,
    so a guessed answer does not produce a wrong finding — it produces a lookup in a directory the
    harness never opens, which is the one failure this rule exists to catch.
    """
    done = _git.git(root, "rev-parse", "--show-toplevel")
    found = (done.stdout or "").strip()
    if done.returncode != 0 or not found:
        raise _git.GitRefused(f"git would not say which directory is the top of the work tree at {root}, so "
                              f"which cache directory belongs to this repo is unknown")
    return found


def variants(parent: str, name: str) -> list[str]:
    """Sibling cache directories that differ from `name` only by case.

    Both `~/projects` and `~/Projects` open one directory on a filesystem that folds case, and the
    harness names the cache after the spelling the session was started from — so one repo can own
    two cache directories, and this machine has a real example. Naming the variant is the difference
    between a finding a human can act on and one that reads as a missing directory.
    """
    try:
        entries = os.listdir(parent)
    except OSError:
        return []
    return sorted(entry for entry in entries if entry != name and entry.casefold() == name.casefold())


def link_target(cache: str) -> str:
    """Where `cache` points, read off the link itself, or "" when it is not a link at all.

    Never `realpath` on a path that has already refused to resolve: `realpath` walks it, so it
    raises the same error a second time, from inside the handler that was explaining the first —
    which takes this rule out and has it reported as unmeasured rather than as the finding it is.
    `readlink` reads the reparse point without following it.
    """
    try:
        return os.readlink(cache)
    except OSError:
        return ""


def check(root: str) -> list[str]:
    """The one way this can be wrong, as one line — or nothing, when there is nothing to point at."""
    memory = os.path.join(root, *REL.split("/"))
    if not os.path.isdir(memory):
        return []
    parent = os.path.join(claude_dir(), "projects")
    name = project_id(toplevel(root))
    cache = os.path.join(parent, name, "memory")
    if os.path.lexists(cache):
        try:
            if os.path.samefile(cache, memory):
                return []
        except OSError as exc:
            # Windows refuses to follow a reparse point created without elevation — WinError 448,
            # and it refuses a symlink as readily as a junction — so this is a link that exists,
            # points at the right place, and cannot be walked by whoever has to walk it. Saying so
            # beats the dangling-link wording: the repair is to recreate it, not to re-point it.
            return [f"{cache} cannot be followed — {exc.strerror or exc}; it points at "
                    f"{link_target(cache) or 'nothing readable'}, so this machine's project memory "
                    f"is unreachable where it is refused"]
        return [f"{cache} is not {REL}/ — it resolves to {os.path.realpath(cache)}, so this session's "
                f"project memory is written outside the repo and never reaches git"]
    others = variants(parent, name)
    spelled = f"; the harness holds this repo under {', '.join(others)} instead" if others else ""
    return [f"{cache} does not exist, so nothing links this machine's memory cache into {REL}/{spelled}"]
