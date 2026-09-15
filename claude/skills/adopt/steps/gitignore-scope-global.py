#!/usr/bin/env python3
"""v3 — delete the lines a project .gitignore duplicates from the global excludes file.

An ignore rule for a user-specific artifact — an IDE folder, an OS cache, a per-machine wrapper a
personal skill writes — belongs in the global excludes file, where one line covers every repo. A
copy of that same line inside a project's `.gitignore` buys nothing and costs: it puts a
machine-local detail in a file every contributor reads, and the two copies drift, so a repo that
kept `config/deploy.env` locally keeps enforcing a rule the global file may have moved on from.

The comparison is between two files read from disk, and the global one is located through
`git config --global core.excludesfile` rather than assumed to be `~/.gitignore`. That is not
fussiness: this machine's setting is the literal string `~/.gitignore`, which no `open()`
resolves, so a step that skipped the lookup and skipped `expanduser` would find no global file and
report every repo as unanswerable.

Two lines are deleted, and everything else is left alone.

**A duplicate.** The global file carries an entry with the same body *and the same anchoring* —
and either the `.gitignore` sits at the repo root, or the pattern floats. Both clauses keep a real
file covered. The anchoring half is why `**/config/deploy.env` is never read as a copy of the
global file's `config/deploy.env`: one floats to every depth and the other is anchored to each
repo's root, so the global entry does not reach a `web/config/deploy.env` the project line hides.
The second clause is what keeps a nested file safe: `config/deploy.env` in `web/.gitignore` is
anchored to `web/`, which the global entry does not cover either. A floating pattern like
`.DS_Store` has no such difference.

**A bare `scripts/` line.** It supersedes the global file's root-anchored wrapper entries with a
pattern that floats, and it hides that repo's own committed scripts as well — one repo tracks
`scripts/package.ts` under exactly such a line.

Anchoring is deliberately out of scope, and the prose says why.

    gitignore-scope-global.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    gitignore-scope-global.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, files intact
    gitignore-scope-global.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the per-path evidence
behind it. The note is one line and carries no tab, because it becomes a field in a TSV record.
"""

import os
import sys
from typing import NamedTuple

import _dispatch
import _gitignore
import _own_fixtures

# Emit UTF-8 whatever the console codepage is. This prints gitignore lines back verbatim, and a
# non-ASCII one through Windows' cp1252 default raises rather than prints, turning a healthy run
# into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Entries the global file happens to carry that a project .gitignore is nonetheless right to keep.
# CLAUDE.md's project-gitignore rule names `.env` files among what every contributor should ignore,
# so the project copy is the one that travels and the global entry is the redundant half. Deleting
# the project line would leave anyone cloning without this machine's global file free to stage a
# real `.env`, which is the opposite of what this step is for. Three repos in the fleet hold one.
PROJECT_OWNED = (".env",)

# The wider-than-global case, kept separate from the duplicates because its risk is different: a
# floating whole-dir rule hides files the global entries never claimed.
BARE_SCRIPTS = "scripts/"


class Target(NamedTuple):
    """One line this step would delete, and why."""

    source: str  # repo-relative path of the .gitignore holding it
    line_no: int  # 1-based, matching what git check-ignore -v reports
    text: str  # the line verbatim
    reason: str


class Globals(NamedTuple):
    path: str
    entries: frozenset[tuple[str, bool]]  # (body, does it float) — see same_rule below


def normalise(entry: str) -> str:
    """A gitignore entry reduced to the body two rules have to share before anything else matches."""
    return entry[3:] if entry.startswith("**/") else entry


def floats(pattern: str) -> bool:
    """Does this pattern match at any depth, rather than being anchored to its base directory.

    A slash anywhere but the trailing position anchors a pattern to the directory holding the
    `.gitignore` (learnings/gitignore-anchoring-and-scope.md), which is why an anchored duplicate
    in a nested file is not the same rule as the global one and is not deleted. A leading `**/`
    is the explicit spelling of the same freedom, so it floats however many slashes follow it.
    """
    body = pattern.rstrip("/")
    return True if body.startswith("**/") else "/" not in body


def same_rule(entry: str) -> tuple[str, bool]:
    """The identity two entries must share to be one rule: the same body, anchored the same way.

    The body alone is not enough, and the difference is a file rather than a nicety.
    `**/config/deploy.env` and `config/deploy.env` reduce to one body, and they hide different
    things: the first floats to every depth, the second is anchored to the root of each repo.
    Measured on a scratch repo carrying `**/config/deploy.env` at its root and a real
    `web/config/deploy.env` on disk — the global file's anchored entry never reaches that path,
    so deleting the project line on a body match alone exposed it.
    """
    return normalise(entry), floats(entry)


def global_excludes(root: str) -> Globals | None:
    """The global excludes file and its entries, or None when it cannot be located or read."""
    done = _gitignore.git(root, "config", "--global", "core.excludesfile")
    if done is None or done.returncode != 0 or not done.stdout.strip():
        return None
    path = os.path.expanduser(done.stdout.strip())
    lines = _gitignore.read_lines(path)
    if lines is None:
        return None
    entries = {same_rule(line.strip()) for line in lines
               if line.strip() and not line.lstrip().startswith("#")}
    return Globals(path, frozenset(entries - {same_rule(owned) for owned in PROJECT_OWNED}))


def tracked_ignore_files(root: str) -> list[str] | None:
    """Every `.gitignore` this repo commits, repo-relative, or None when git could not be asked.

    Tracked rather than found on disk, because a virtualenv, a build directory and an IDE each
    write a `.gitignore` this repo neither owns nor should rewrite — the fleet holds nine such
    files under `.venv/`, `.next/` and `.idea/`. What git tracks is exactly what the repo owns.
    """
    done = _gitignore.git(root, "ls-files", "-z", "--", "*.gitignore")
    if done is None or done.returncode != 0:
        return None
    # This skill's own fixture trees commit `.gitignore` files built to be deviations, and in this
    # dotfiles checkout `probe` exited 0 on a list where one real finding sat among five fixture
    # ones — a dry run that reads plausible and gets approved, which would then rewrite the trees
    # `selftest` gates on.
    return [name for name in done.stdout.split("\0")
            if name and not _own_fixtures.is_beneath(os.path.join(root, *name.split("/")))]


def targets_in(root: str, source: str, known: Globals) -> tuple[list[Target], str]:
    """Every deletable line in one .gitignore, or a reason this step will not read it."""
    lines = _gitignore.read_lines(os.path.join(root, *source.split("/")))
    if lines is None:
        return [], f"{source} could not be read as UTF-8 text"
    at_root = "/" not in source
    found: list[Target] = []
    for line_no, line in enumerate(lines, 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text == BARE_SCRIPTS:
            found.append(Target(source, line_no, line, "floats over the global file's root-anchored "
                                                       "wrapper entries and hides committed scripts too"))
        elif same_rule(text) in known.entries and (at_root or floats(text)):
            found.append(Target(source, line_no, line, "duplicates an entry in the global excludes file"))
    return found, ""


def all_targets(root: str, known: Globals) -> tuple[list[Target], list[str], str]:
    """Every deletable line in the repo, the files read to find them, or a reason git refused."""
    sources = tracked_ignore_files(root)
    if sources is None:
        return [], [], "git could not be asked which .gitignore files this repo commits"
    found: list[Target] = []
    for source in sources:
        targets, problem = targets_in(root, source, known)
        if problem:
            return [], sources, problem
        found.extend(targets)
    return found, sources, ""


def unanswerable() -> None:
    print("git config --global core.excludesfile names no file this step can read, so there is no "
          "other side to compare a project .gitignore against. Set it — on this setup it points at a "
          "file symlinked from the dotfiles repo — and re-run.")


def cmd_probe(root: str) -> int:
    known = global_excludes(root)
    if known is None:
        unanswerable()
        return 2
    targets, sources, problem = all_targets(root, known)
    if problem:
        print(problem)
        return 3
    if not targets:
        # Positive evidence from having read both sides (CD4): the project files were opened and
        # every line in them compared against the global set. "No .gitignore is committed here" is
        # the same answer reached with nothing to read, which is why the count is printed.
        print(f"{len(sources)} committed .gitignore file(s) read against {len(known.entries)} global "
              f"entries; no line duplicates one, and none is a bare {BARE_SCRIPTS} rule")
        return 1
    for target in targets:
        print(f"{target.source}:{target.line_no}  {target.text.strip()}  — {target.reason}")
    return 0


def cmd_verify(root: str) -> int:
    """Does any committed .gitignore still hold a line the global excludes file already carries.

    Both files are re-read from disk every time, so a later change to the global file is picked up
    by `audit` rather than being frozen into whatever was true the day the line was recorded.
    """
    known = global_excludes(root)
    if known is None:
        unanswerable()
        return 2
    targets, sources, problem = all_targets(root, known)
    if problem:
        print(f"{problem}, so whether anything duplicates the global excludes file is not a shape this "
              f"script can observe")
        return 2
    if not targets:
        print(f"{len(sources)} committed .gitignore file(s) hold no line duplicating any of the "
              f"{len(known.entries)} entries in the global excludes file, and no bare {BARE_SCRIPTS} rule")
        return 0
    for target in targets:
        print(f"{target.source}:{target.line_no}  {target.text.strip()}  — {target.reason}")
    print(f"{len(targets)} line(s) belong in the global excludes file rather than here")
    return 3


def hidden_by(root: str, targets: list[Target]) -> tuple[dict[tuple[str, int], list[str]], str]:
    """Which paths on disk each doomed line is currently the winning rule for.

    This is the set that decides whether a deletion is safe, and it is asked per path rather than
    per line: a count of "how many things were hidden before and after" passes the moment one path
    is freed while another is lost (learnings/git-stash-pull-safety.md).

    What the listing expands is what this guard can see, which is why `ignored_on_disk` asks for
    `--ignored=matching`. Under the default mode a directory whose whole contents are ignored
    arrives as one entry that matches no pattern, `check-ignore` attributes it to no rule, and a
    file hidden by a doomed line drops out of this set entirely — leaving a deletion that exposes
    it reported as having hidden nothing.
    """
    on_disk = _gitignore.ignored_on_disk(root)
    if on_disk is None:
        return {}, "git status --ignored could not be run, so what these lines hide was never measured"
    rules = _gitignore.rules_for(root, on_disk)
    if rules is None:
        return {}, "git check-ignore could not attribute the ignored paths to the rules behind them"
    wanted = {(target.source, target.line_no) for target in targets}
    out: dict[tuple[str, int], list[str]] = {key: [] for key in wanted}
    for path, rule in rules.items():
        key = (rule.source, rule.line_no)
        if key in wanted:
            out[key].append(path)
    return {key: sorted(paths) for key, paths in out.items()}, ""


def cmd_apply(root: str, dry_run: bool) -> int:
    known = global_excludes(root)
    if known is None:
        unanswerable()
        return 3
    targets, _, problem = all_targets(root, known)
    if problem:
        print(f"{problem} — nothing was changed")
        return 3
    if not targets:
        # A second apply reaches the same end state as the first. Exit 0 rather than 1, which means
        # "does not apply" everywhere else in this system, or a crash, which is what the idempotence
        # assertion exists to catch.
        print("already in the target shape: no committed .gitignore duplicates the global excludes file")
        return 0
    by_file: dict[str, list[Target]] = {}
    for target in targets:
        by_file.setdefault(target.source, []).append(target)
    written: dict[str, list[str]] = {}
    for source, group in by_file.items():
        lines = _gitignore.read_lines(os.path.join(root, *source.split("/")))
        if lines is None:
            print(f"REFUSED  {source} could not be read as UTF-8 text — nothing was changed")
            return 3
        escaped = _gitignore.escaped_lines(lines)
        if escaped:
            # Abort rather than skip (idempotence rule 6). A backslash changes what the line means —
            # `foo\ ` keeps a trailing space, `\#x` is a pattern — and the stripped copy compared
            # against the global file is then not the text anyone wrote.
            print(f"REFUSED  {source} holds {len(escaped)} line(s) carrying a backslash, whose meaning "
                  f"this step does not implement:")
            for line in escaped:
                print(f"  {line}")
            print("Nothing was changed. Decide those by hand — including any duplicate beside them, "
                  "which was left in place rather than deleted on a reading that may be wrong.")
            return 3
        for target in group:
            if not 0 < target.line_no <= len(lines) or lines[target.line_no - 1] != target.text:
                print(f"REFUSED  {source} line {target.line_no} changed under this step — nothing was changed")
                return 3
        kept, carried = _gitignore.without(lines, {target.line_no - 1 for target in group})
        for extra in carried:
            # Printed verbatim rather than counted: a comment describing only the deleted rules goes
            # with them, and a reader has to be able to see what text left the file.
            print(f"  carried with it  {source}:{extra + 1}  {lines[extra] or '(blank line)'}")
        written[source] = kept
    covered, problem = hidden_by(root, targets)
    if problem:
        print(f"REFUSED  {problem} — nothing was changed")
        return 3
    for target in targets:
        paths = covered[(target.source, target.line_no)]
        holds = f"currently the winning rule for {len(paths)} path(s): {', '.join(paths)}" if paths else \
            "the winning rule for nothing on disk today"
        print(f"{'would delete' if dry_run else 'deleting'}  {target.source}:{target.line_no} "
              f"{target.text.strip()} — {holds}")
    if dry_run:
        print(f"{len(targets)} line(s) would be deleted from {len(written)} committed .gitignore file(s)")
        return 0
    guarded = sorted({path for paths in covered.values() for path in paths})
    originals = {source: _gitignore.read_lines(os.path.join(root, *source.split("/"))) for source in written}
    try:
        for source, lines in written.items():
            _gitignore.write_lines(os.path.join(root, *source.split("/")), lines)
    except OSError as exc:
        _gitignore.restore(root, originals)
        print(f"could not write {getattr(exc, 'filename', '?')} ({exc}) — every .gitignore was put back as it was")
        return 3
    still = _gitignore.ignored(root, guarded)
    if still is None:
        _gitignore.restore(root, originals)
        print("git check-ignore could not be re-run to prove nothing was exposed — every .gitignore was "
              "put back as it was")
        return 3
    exposed = [path for path in guarded if path not in still]
    for path in guarded:
        print(f"{'EXPOSED       ' if path in exposed else 'ok            '}{path}")
    if exposed:
        _gitignore.restore(root, originals)
        print(f"{len(exposed)} path(s) would have become visible with those lines gone, which is a "
              f"per-file decision rather than a blind removal — every .gitignore was put back as it was")
        return 3
    names = ", ".join(sorted({target.text.strip() for target in targets}))
    covering = (f"each of the {len(guarded)} path(s) they hid asserted still ignored afterwards" if guarded
                else "none of them was the winning rule for anything on disk, so nothing could be exposed")
    print(f"{len(targets)} line(s) deleted from {len(written)} committed .gitignore file(s) ({names}); {covering}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
