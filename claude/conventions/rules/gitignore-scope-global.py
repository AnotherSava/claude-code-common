"""No committed .gitignore repeats a line that belongs in the global excludes file.

An ignore rule for a user-specific artifact — an IDE folder, an OS cache, a per-machine wrapper a
personal skill writes — belongs in the global excludes file, where one line covers every repo. A
copy of that same line inside a project's `.gitignore` buys nothing and costs: it puts a
machine-local detail in a file every contributor reads, and the two copies drift, so a repo that
kept `config/deploy.env` locally keeps enforcing a rule the global file may have moved on from.

The comparison is between two files read from disk, and the global one is located through
`git config --global core.excludesfile` rather than assumed to be `~/.gitignore`. That is not
fussiness: this machine's setting is the literal string `~/.gitignore`, which no `open()` resolves,
so a rule that skipped the lookup and skipped `expanduser` would find no global file and report
every repo as unanswerable.

Two shapes are reported, and everything else is left alone.

**A duplicate.** The global file carries an entry with the same body *and the same anchoring* — and
either the `.gitignore` sits at the repo root, or the pattern floats. Both clauses keep a real file
covered. The anchoring half is why `**/config/deploy.env` is never read as a copy of the global
file's `config/deploy.env`: one floats to every depth and the other is anchored to each repo's
root, so the global entry does not reach a `web/config/deploy.env` the project line hides. The
second clause is what keeps a nested file safe: `config/deploy.env` in `web/.gitignore` is anchored
to `web/`, which the global entry does not cover either. A floating pattern like `.DS_Store` has no
such difference.

**A bare `scripts/` line.** It supersedes the global file's root-anchored wrapper entries with a
pattern that floats, and it hides that repo's own committed scripts as well — one repo tracks
`scripts/package.ts` under exactly such a line.

Anchoring is deliberately out of scope. Both sides are re-read from disk on every run, so a later
change to the global excludes file is picked up here rather than frozen into whatever was true the
day a repo adopted.
"""

import os
from typing import NamedTuple

import _git


class Unanswerable(Exception):
    """One of the two sides could not be read, so nothing can be said about what they share.

    Raised rather than reported as a clean result for the reason every rule here raises: an
    unreadable `.gitignore` and a `.gitignore` holding no duplicate produce the same empty list, and
    only one of them is an answer. The global excludes file being unset is the same case seen from
    the other side — there is then no set to compare a project line against, so a repo full of
    duplicates would read as clean.
    """


# Entries the global file happens to carry that a project .gitignore is nonetheless right to keep.
# The project-gitignore rule in CLAUDE.md names `.env` files among what every contributor should
# ignore, so the project copy is the one that travels and the global entry is the redundant half.
# Reporting the project line would push a repo towards leaving anyone who clones it without this
# machine's global file free to stage a real `.env`, which is the opposite of the point.
PROJECT_OWNED = (".env",)

# The wider-than-global case, kept separate from the duplicates because its risk is different: a
# floating whole-dir rule hides files the global entries never claimed.
BARE_SCRIPTS = "scripts/"


class Target(NamedTuple):
    """One line that belongs in the global excludes file rather than in this repo, and why."""

    source: str  # repo-relative path of the .gitignore holding it
    line_no: int  # 1-based, matching what git check-ignore -v reports
    text: str  # the line verbatim
    reason: str


class Globals(NamedTuple):
    path: str
    entries: frozenset[tuple[str, bool]]  # (body, does it float) — see same_rule below


def read_lines(path: str, shown: str) -> list[str]:
    """A file's lines without their endings. Raises when it is there and will not read as text.

    The name to put in that message is passed in rather than taken from the path, so a repo file is
    named the way the finding names it — repo-relative — while the global excludes file, which is
    outside every repo, keeps the absolute path that is the only way to find it.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise Unanswerable(f"{shown} could not be read as UTF-8 text ({exc})") from exc


def normalise(entry: str) -> str:
    """A gitignore entry reduced to the body two rules have to share before anything else matches."""
    return entry[3:] if entry.startswith("**/") else entry


def floats(pattern: str) -> bool:
    """Does this pattern match at any depth, rather than being anchored to its base directory.

    A slash anywhere but the trailing position anchors a pattern to the directory holding the
    `.gitignore` (learnings/gitignore-anchoring-and-scope.md), which is why an anchored duplicate in
    a nested file is not the same rule as the global one and is not reported. A leading `**/` is the
    explicit spelling of the same freedom, so it floats however many slashes follow it.
    """
    body = pattern.rstrip("/")
    return True if body.startswith("**/") else "/" not in body


def same_rule(entry: str) -> tuple[str, bool]:
    """The identity two entries must share to be one rule: the same body, anchored the same way.

    The body alone is not enough, and the difference is a file rather than a nicety.
    `**/config/deploy.env` and `config/deploy.env` reduce to one body, and they hide different
    things: the first floats to every depth, the second is anchored to the root of each repo.
    Measured on a scratch repo carrying `**/config/deploy.env` at its root and a real
    `web/config/deploy.env` on disk — the global file's anchored entry never reaches that path, so
    treating the project line as a copy on a body match alone would have exposed it.
    """
    return normalise(entry), floats(entry)


def global_excludes(root: str) -> Globals:
    """The global excludes file and its entries. Raises when it cannot be located or read."""
    done = _git.git(root, "config", "--global", "core.excludesfile")
    if done.returncode != 0 or not done.stdout.strip():
        raise Unanswerable("git config --global core.excludesfile names no file, so there is no other "
                           "side to compare a project .gitignore against. Set it — on this setup it "
                           "points at a file symlinked from the dotfiles repo.")
    path = os.path.expanduser(done.stdout.strip())
    entries = {same_rule(line.strip()) for line in read_lines(path, path)
               if line.strip() and not line.lstrip().startswith("#")}
    return Globals(path, frozenset(entries - {same_rule(owned) for owned in PROJECT_OWNED}))


def tracked_ignore_files(root: str) -> list[str]:
    """Every `.gitignore` this repo commits, repo-relative. Raises when git would not say.

    Tracked rather than found on disk, because a virtualenv, a build directory and an IDE each write
    a `.gitignore` this repo neither owns nor should be judged on — the fleet holds nine such files
    under `.venv/`, `.next/` and `.idea/`. What git tracks is exactly what the repo owns.
    """
    done = _git.git(root, "ls-files", "-z", "--", "*.gitignore")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise _git.GitRefused(f"git ls-files exited {done.returncode} rather than naming the .gitignore "
                              f"files this repo commits{' — ' + detail[0] if detail else ''}")
    return [name for name in done.stdout.split("\0") if name]


def targets_in(root: str, source: str, known: Globals) -> list[Target]:
    """Every line in one committed .gitignore that belongs in the global excludes file instead."""
    at_root = "/" not in source
    found: list[Target] = []
    path = os.path.join(root, *source.split("/"))
    # git names what the index holds, and during a deletion that still includes a file the work tree
    # no longer has — the state every `git rm` leaves behind until the commit lands it. Such a file
    # contributes no lines, and treating its absence as unreadable would take this rule out of
    # measurement entirely whenever a committed .gitignore is on its way out. Absence is only ever
    # silent here: `global_excludes` reads its file through the same helper and still raises, because
    # a missing excludes file would leave nothing to compare against and every line looking fine.
    if not os.path.exists(path):
        return found
    for line_no, line in enumerate(read_lines(path, source), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text == BARE_SCRIPTS:
            found.append(Target(source, line_no, line, "floats over the global file's root-anchored "
                                                       "wrapper entries and hides committed scripts too"))
        elif same_rule(text) in known.entries and (at_root or floats(text)):
            found.append(Target(source, line_no, line, "duplicates an entry in the global excludes file, "
                                                       "and belongs there rather than here"))
    return found


def check(root: str) -> list[str]:
    """Every committed ignore line that belongs in the global excludes file, one line each."""
    known = global_excludes(root)
    return [f"{target.source}:{target.line_no}  {target.text.strip()}  — {target.reason}"
            for source in tracked_ignore_files(root) for target in targets_in(root, source, known)]
