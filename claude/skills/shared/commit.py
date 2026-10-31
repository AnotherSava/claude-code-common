#!/usr/bin/env python3
"""Make one commit holding exactly the given paths, after the checks every commit owes, or refuse and say why.

The one place a commit is made. `/yolo`, `/wrap-up`, `/release`, `/pr-create`, `/review-manual` and `/adopt` all
call it, so a check added here reaches every local commit they make, and none of them can skip one by committing on its
own. `/github-create` is the exception: its one commit, the LICENSE seed, is made server-side through the Contents API
and passes none of these checks.

Each call:

1. clears the index, so a path staged earlier by someone else cannot ride along — `git commit` writes the whole index;
2. stages the paths, a directory standing for every file under it as `git status --short` lists a new one: from the
   working tree, or with `--reviewed` from the tree a completed review recorded, so the commit holds what the review
   read whatever happened to the disk copy since;
3. gives a script its execute bit in the index, because git records the mode and a hook committed `644` is silently
   never run: a new one the disk marks executable (never on Windows, where every file reads as executable), a
   `git/hooks/` file always, and, under `core.filemode=false` (Windows, where the disk cannot carry the bit), a named
   path staged `+x` before the call (`git add --chmod=+x`), which the clearing would otherwise discard;
4. refuses unless the index holds exactly the paths given — a path with no change is a caller's mistake, not a no-op,
   and a change that is only the execute bit step 3 set counts as a change;
5. checks the message with `check-commit-message.py`;
6. scans the lines the index adds with `scan-commit-confidentiality.py --staged`; a blocking finding refuses, and the
   review findings are printed under a header telling the caller to read them before it pushes — in the output, so
   every caller gets the instruction without each skill restating it;
7. commits, signed unless `commit.gpgsign` is explicitly false, and confirms the commit holds those paths.

It never pushes; that is `push.py`'s, so a skill can commit without publishing.

Exit codes: 0 committed, 1 refused by a check (the index is cleared again, the working tree untouched; a `+x` staged
before the call is cleared with it, and the refusal names the paths to stage it on again, along with any new path step 3
marked itself, which a retry marks again), 2 could not run.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "scripts")
sys.path.insert(0, SCRIPTS)
from review_scope import fix_modes, index_modes, repo_relative, stage_reviewed

MESSAGE_CHECK = os.path.join(SCRIPTS, "check-commit-message.py")
SCANNER = os.path.join(SCRIPTS, "scan-commit-confidentiality.py")


class Refused(Exception):
    """A check said no. Carries what to show the caller."""


def _staged_exec(repo: str, paths: list[str]) -> set[str]:
    """The paths among `paths` the index holds as 100755, under `core.filemode=false`, where the index is the only
    holder of a `git add --chmod=+x`; empty elsewhere, where the disk is the authority and staging reads it again."""
    if _git(repo, "config", "--bool", "core.filemode", check=False).stdout.strip() != "false":
        return set()
    return {p for p, m in index_modes(repo, paths).items() if m == "100755"}


def _empty_index(repo: str, check: bool = True) -> None:
    # `git reset` needs a HEAD to reset to; a repo with no commits yet has none.
    has_head = _git(repo, "rev-parse", "-q", "--verify", "HEAD", check=False).returncode == 0
    _git(repo, *(("reset", "-q") if has_head else ("read-tree", "--empty")), check=check)


def _clear_index(repo: str) -> str:
    """Clear the index after a refusal, and return a note naming each path whose staged execute bit the clear threw
    away, with the command that stages it again; empty when none was."""
    # Best effort, so a failure here never hides the refusal. Compared across the clear because a path already 100755
    # in HEAD keeps its bit. Read from the index as the refusal left it, so it also names a bit `fix_modes` set itself.
    before = _staged_exec(repo, _staged(repo))
    _empty_index(repo, check=False)
    dropped = sorted(before - _staged_exec(repo, sorted(before)))
    if not dropped:
        return ""
    return f"\nclearing the index drops the execute bit staged on {', '.join(dropped)}; stage it again before retrying: git add --chmod=+x -- {' '.join(shlex.quote(p) for p in dropped)}"


def _git(repo: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    # Literal pathspecs: a path holding `*` or `[` names that file, never a pattern matching others.
    done = subprocess.run(["git", "--literal-pathspecs", "-C", repo, *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done


def _staged(repo: str) -> list[str]:
    # `ls-files` in a repo with no commits yet, where there is no HEAD to diff the index against.
    if _git(repo, "rev-parse", "-q", "--verify", "HEAD", check=False).returncode != 0:
        out = _git(repo, "ls-files", "-z").stdout
    else:
        out = _git(repo, "diff", "--cached", "--name-only", "-z", "--no-renames").stdout
    return sorted(p for p in out.split("\0") if p)


def _signs(repo: str) -> bool:
    return _git(repo, "config", "--get", "commit.gpgsign", check=False).stdout.strip().lower() != "false"


def commit(repo: str, paths: list[str], message_file: str, reviewed: bool = False, from_files: dict[str, str] | None = None) -> str:
    """Stage, check and commit. `from_files` maps a path to a file whose content it is committed with — a redacted copy
    of the reviewed version, per the confidentiality-fix rule in `commit-grouping.md` — staged as a blob without
    touching the disk copy."""
    from_files = from_files or {}
    relative = []
    for path in paths + list(from_files):
        rel = repo_relative(repo, path)
        if rel is None:
            raise Refused(f"{path} lies outside the repo")
        relative.append(rel)
    wanted = sorted(set(relative))
    from_rel = {repo_relative(repo, p): f for p, f in from_files.items()}
    plain = [p for p in wanted if p not in from_rel]

    marked_exec = _staged_exec(repo, plain)
    _empty_index(repo)
    if _staged(repo):
        raise RuntimeError("the index is not empty after `git reset` — another git process holds it; retry")

    if reviewed:
        print(stage_reviewed(repo, plain))
    elif plain:
        _git(repo, "add", "-A", "--", *plain)
    for path, source in from_rel.items():
        mode = index_modes(repo, [path]).get(path, "100644")
        blob = _git(repo, "hash-object", "-w", "--", source).stdout.strip()
        _git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}")

    staged = _staged(repo)
    # `git status --short` names a new directory once (`?? dir/`), and callers build their path lists from it, so a
    # directory stands for every file under it that `git add` staged; one with none staged is still a path unchanged.
    dirs = [p for p in plain if os.path.isdir(os.path.join(repo, p))]
    if dirs:
        inside = {s for s in staged for d in dirs if s.startswith(d + "/")}
        covered = {d for d in dirs if any(s.startswith(d + "/") for s in inside)}
        wanted = sorted((set(wanted) - covered) | inside)
        plain = sorted((set(plain) - covered) | inside)
    fixed = fix_modes(repo, plain, keep_exec=marked_exec)
    # Counted again after the mode fix, or a change that is only an execute bit reads as no change at all.
    staged = _staged(repo)
    unchanged = [p for p in wanted if p not in staged]
    stray = [p for p in staged if p not in wanted]
    if unchanged or stray:
        raise Refused("the index does not hold exactly the paths given"
                      + (f"; no change to commit in: {', '.join(unchanged)}" if unchanged else "")
                      + (f"; staged but not given: {', '.join(stray)}" if stray else ""))

    checked = subprocess.run([sys.executable, MESSAGE_CHECK, "--file", message_file], capture_output=True, text=True)
    if checked.returncode != 0:
        raise Refused("the message fails check-commit-message.py:\n" + checked.stdout.strip())

    scanned = subprocess.run([sys.executable, SCANNER, "--staged", "--repo", repo], capture_output=True, text=True)
    if scanned.returncode == 2:
        raise RuntimeError("the privacy scan could not run:\n" + scanned.stdout.strip())
    if scanned.returncode == 1:
        raise Refused("the privacy scan found something that must not be published:\n" + scanned.stdout.strip())
    review = [line for line in scanned.stdout.splitlines() if line.startswith("  ") and ":" in line and "allow=" not in line]

    args = ["commit", "-q", "-F", message_file] + (["-S"] if _signs(repo) else [])
    _git(repo, *args)
    held = sorted(p for p in _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--no-renames", "--root", "HEAD").stdout.split("\0") if p)
    if held != wanted:
        raise RuntimeError(f"the commit holds {held}, not the paths given {wanted}")

    sha = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    subject = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    lines = [f"committed {sha} {subject}: {len(wanted)} path(s)"]
    if fixed:
        lines.append(f"  execute bit set in the index: {', '.join(fixed)}")
    if review:
        lines.append(f"  privacy scan, {len(review)} review finding(s), none blocking — read each before pushing; one that is a real leak comes back out with `/reset` and is re-committed without it:")
        lines += review
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="repo-relative or absolute paths the commit holds")
    parser.add_argument("--message-file", "-F", required=True)
    parser.add_argument("--reviewed", action="store_true", help="stage the paths from the recorded review's tree")
    parser.add_argument("--from-file", action="append", default=[], metavar="PATH=FILE", help="commit PATH with FILE's content, leaving the disk copy alone")
    parser.add_argument("--repo", default=".")
    opts = parser.parse_args()
    from_files = {}
    for pair in opts.from_file:
        path, sep, source = pair.partition("=")
        if not sep:
            parser.error(f"--from-file wants PATH=FILE, got {pair}")
        from_files[path] = os.path.abspath(source)
    if not opts.paths and not from_files:
        parser.error("give the paths the commit holds")
    repo = _git(os.path.abspath(opts.repo), "rev-parse", "--show-toplevel").stdout.strip()
    try:
        print(commit(repo, opts.paths, os.path.abspath(opts.message_file), opts.reviewed, from_files))
        return 0
    except Refused as refusal:
        print(f"NOT COMMITTED: {refusal}{_clear_index(repo)}")
        return 1
    except RuntimeError as error:
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
