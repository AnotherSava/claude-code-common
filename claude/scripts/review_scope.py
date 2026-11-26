#!/usr/bin/env python3
"""The review bookmark: which part of a repo's history an adversarial review has already covered.

Small changes get pushed without a review, so a review scoped to the uncommitted diff never sees them. The
bookmark is the ref `refs/review/last`, shared through origin so both machines read the same one. It always
points at a real commit whose content a review covered. Every review then takes in everything between the
bookmark and the working tree, whoever pushed it and however.

Several moments act on it, and each belongs to a different caller:

- `plan`, called in-process by the `review-scope.py` PreToolUse hook when the `review-auto` workflow launches,
  brings the local bookmark up to date with origin's and works out what the review must cover. The `scope` command
  prints the same for a run by hand.
- `mark`, run by the workflow's last agent once a review finished with no gaps, records which tree it covered,
  from which base and on top of which HEAD, and whether the workflow's polish ran over it. Nothing moves yet: the tree is usually
  uncommitted.
- `layout`, run by `/yolo` and `/wrap-up` before they group commits (`shared/commit-grouping.md`), splits the change
  set at the recorded tree: what the review covered, which `shared/commit.py --reviewed` stages from the recorded tree itself so
  the reviewed commits hold exactly what was reviewed, and what changed after it, which goes in follow-up commits.
- `advance`, run by `/yolo`, `/wrap-up` and `/review-manual` after their commits, moves the bookmark to the newest
  commit since the review's base whose tree is exactly the recorded one, so an edit made after the review and committed with it leaves the bookmark where
  it was, while one committed after it does not hold it back. `push` then publishes it.

`forecast`, run just before every push, says where the bookmark will stand once the push is done, and `status`,
run after it and at the end of every skill that pushes, reports where it stands. Neither changes anything.

Between `mark` and `advance`, `/wrap-up`'s change_scope.py reads the record through `polished_since` to skip the
`/clean-code` and `/docs-relevance` passes the workflow already ran. `snapshot` and `revert` serve the workflow's
polish phase, which takes back what it cannot keep, and `pack` writes the diff each review round reads.

Every failure leaves the bookmark behind rather than ahead: a missed move costs a re-review, a wrong one hides
unreviewed code for good.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

# The saved workflow whose runs this bookmark tracks. Both the review-scope.py and workflow-realism.py hooks match
# Workflow calls against it, and it must equal `meta.name` in claude/workflows/review-auto.js.
WORKFLOW = "review-auto"
REF = "refs/review/last"
FETCHED = "refs/review/origin"
RECORD = "review-scope-reviewed"
SCRATCH_INDEX = "review-scope-index"
# Under the git dir, so a pack is never tracked and needs no ignore rule in any repo.
PACK_DIR = "review-pack"
# A pack is read only during the round that wrote it; one a day old belongs to no running review.
PACK_MAX_AGE = 86400
REMOTE = "origin"
NETWORK_TIMEOUT = 20


def _git(repo: str, *args: str, env: dict | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout, env=env)


def _git_paths(repo: str, *args: str, env: dict | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    """A git command whose pathspecs are literal, as every call in shared/commit.py is, since it stages through
    `stage_reviewed`: a path holding `*` or `[` (a Next route such as `app/[slug]/page.tsx`) names that file, never a
    pattern matching its siblings. Not the default for `_git`, because `check-ignore` refuses the flag outright."""
    return _git(repo, "--literal-pathspecs", *args, env=env, timeout=timeout)


def toplevel(path: str) -> str | None:
    try:
        done = _git(path, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def _resolve(repo: str, rev: str) -> str | None:
    done = _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return done.stdout.strip() if done.returncode == 0 else None


def _is_ancestor(repo: str, older: str, newer: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", older, newer).returncode == 0


def _git_path(repo: str, name: str) -> str:
    path = _git(repo, "rev-parse", "--git-path", name).stdout.strip()
    return path if os.path.isabs(path) else os.path.join(repo, path)


def _wants_exec(repo: str, path: str, tracked: bool) -> bool:
    """A git hook, or a new file whose first line is a shebang and whose disk copy is executable. A shebang alone is not
    enough: a library module may carry one and be deliberately `644`. A file HEAD already tracks keeps the mode it
    records, since under `core.filemode=false` `git add` preserves that mode and the disk has nothing better to offer.
    On Windows the disk carries no execute bit at all (`os.access(X_OK)` is true for any existing file), so there only a
    hook qualifies, and a new script takes its bit from `git add --chmod=+x`."""
    full = os.path.join(repo, path)
    if not os.path.isfile(full):
        return False
    if path.startswith("git/hooks/"):
        return True
    if tracked or os.name == "nt":
        return False
    with open(full, "rb") as handle:
        shebang = handle.read(2) == b"#!"
    return shebang and os.access(full, os.X_OK)


def index_modes(repo: str, paths: list[str] | None = None, env: dict | None = None) -> dict[str, str]:
    """The mode the index (`GIT_INDEX_FILE` in `env`, or the real one) holds for each file, every file when `paths` is
    None and those under `paths` otherwise. The one reader of index modes: `fix_modes` and shared/commit.py both go
    through it, so a change to how a mode is read reaches the reviewed tree and the commit alike."""
    if paths is not None and not paths:
        return {}
    listed = _git_paths(repo, "ls-files", "-s", "-z", *(() if paths is None else ("--", *paths)), env=env, timeout=60)
    if listed.returncode != 0:
        raise RuntimeError(f"git ls-files -s failed: {listed.stderr.strip()}")
    return {path: meta.split()[0] for meta, _, path in (e.partition("\t") for e in listed.stdout.split("\0") if e)}


def fix_modes(repo: str, paths: list[str], env: dict | None = None, keep_exec: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Give each of `paths` that the index (`GIT_INDEX_FILE` in `env`, or the real one) holds as `100644` its execute
    bit when `_wants_exec` says it is a script, because git records the mode and a hook committed `644` is silently never
    run, and on Windows `core.filemode=false` means the disk cannot carry the bit. A path in `keep_exec` gets it too:
    shared/commit.py passes the paths staged `+x` (`git add --chmod=+x`) before its index clear under
    `core.filemode=false`, where nothing on disk would restore the bit. Both shared/commit.py and `worktree_tree` call
    it, so a reviewed tree records the mode the reviewed commit will carry and `advance` finds it."""
    modes = index_modes(repo, env=env)
    in_head = _git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", env=env, timeout=60)
    tracked = set(in_head.stdout.split("\0")) if in_head.returncode == 0 else set()
    fixed = sorted(p for p in set(paths) if modes.get(p) == "100644" and (p in keep_exec or _wants_exec(repo, p, p in tracked)))
    if fixed:
        done = _git_paths(repo, "update-index", "--chmod=+x", "--", *fixed, env=env)
        if done.returncode != 0:
            raise RuntimeError(f"git update-index --chmod=+x failed: {done.stderr.strip()}")
    return fixed


def worktree_tree(repo: str) -> str:
    """The tree of every file git does not ignore, tracked or not, written through a scratch index so the real one is
    untouched. Seeded from the real index, or a tracked file under an ignored directory would be left out, and copied
    with its mtime, or a same-size edit made in the real index's own tick enters the tree as its old content
    (learnings/git-snapshot-dirty-tree.md). Every path that differs from HEAD gets the execute bit shared/commit.py
    would give it (`fix_modes`), or the commit of this tree would carry a mode the tree does not."""
    scratch = _git_path(repo, SCRATCH_INDEX)
    real = _git_path(repo, "index")
    try:
        if os.path.exists(real):
            shutil.copy2(real, scratch)
        env = {**os.environ, "GIT_INDEX_FILE": scratch}
        added = _git(repo, "add", "-A", env=env, timeout=60)
        if added.returncode != 0:
            raise RuntimeError(f"git add -A into the scratch index failed: {added.stderr.strip()}")
        has_head = _resolve(repo, "HEAD") is not None
        changed = _git(repo, *(("diff", "--cached", "--name-only", "-z", "--no-renames", "HEAD") if has_head else ("ls-files", "-z")), env=env, timeout=60)
        if changed.returncode != 0:
            raise RuntimeError(f"listing the scratch index's changes failed: {changed.stderr.strip()}")
        fix_modes(repo, [p for p in changed.stdout.split("\0") if p], env)
        written = _git(repo, "write-tree", env=env)
        if written.returncode != 0:
            raise RuntimeError(f"git write-tree failed: {written.stderr.strip()}")
        return written.stdout.strip()
    finally:
        if os.path.exists(scratch):
            os.remove(scratch)


def _has_remote(repo: str) -> bool:
    return _git(repo, "remote", "get-url", REMOTE).returncode == 0


def _origin_bookmark(repo: str) -> tuple[str | None, str | None]:
    """Read origin's bookmark without writing anything. Returns (sha, None), (None, None) when origin has no bookmark, or
    (None, a sentence saying why origin could not be read)."""
    try:
        listed = _git(repo, "ls-remote", REMOTE, REF, timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, f"`git ls-remote {REMOTE}` timed out"
    if listed.returncode != 0:
        return None, f"`git ls-remote {REMOTE}` failed: {listed.stderr.strip()}"
    return (listed.stdout.split()[0] if listed.stdout.strip() else None), None


def _sync(repo: str) -> str:
    """Bring the local bookmark up to origin's when origin's is newer. Returns `ok`, `local-only` or a sentence saying
    why origin could not be read. A failure leaves the local bookmark as it was, which can only be older."""
    if not _has_remote(repo):
        return "local-only"
    origin_sha, error = _origin_bookmark(repo)
    if error:
        return error
    if origin_sha is None:
        return "ok"
    try:
        fetched = _git(repo, "fetch", "--no-tags", REMOTE, f"+{REF}:{FETCHED}", timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"fetching {REF} from {REMOTE} timed out"
    if fetched.returncode != 0:
        return f"fetching {REF} from {REMOTE} failed: {fetched.stderr.strip()}"
    remote = _resolve(repo, FETCHED)
    if _supersedes(repo, _resolve(repo, REF), remote):
        _git(repo, "update-ref", REF, remote)
    return "ok"


def _supersedes(repo: str, local: str | None, remote: str | None) -> bool:
    """Whether origin's bookmark replaces the local one: it exists, and the local one is absent or older. `_sync`
    applies this and `_origin_view` predicts it, so the count `status` and `forecast` print is the one the next `plan`
    covers."""
    return bool(remote) and (not local or (local != remote and _is_ancestor(repo, local, remote)))


def _coverage(repo: str, sync: str, head: str | None, bookmark: str | None) -> tuple[str | None, list[str], str | None]:
    """The base a review diffs from, the commits it adds past the bookmark, and why there is no base when there is
    none. Both `plan` and `status` call this, so the line `status` prints cannot promise a coverage `plan` refuses."""
    if sync not in ("ok", "local-only"):
        return None, [], f"Origin's review bookmark could not be read ({sync}), so the commits it would add are unknown."
    if head is None:
        return None, [], "The repo has no commits yet."
    if bookmark and not _is_ancestor(repo, bookmark, head):
        return None, [], (f"The review bookmark {bookmark[:12]} is not an ancestor of HEAD, so history was rewritten "
                          f"after the last review and the unreviewed range is unknown.")
    if not bookmark:
        return head, [], None
    log = _git(repo, "log", "--format=%h %s", f"{bookmark}..{head}").stdout.splitlines()
    return bookmark, [line for line in log if line.strip()], None


def plan(repo: str) -> dict:
    """What a review launched now must cover. `base` is the commit it diffs from; it is null when no base can be trusted
    (origin unreadable, or a bookmark HEAD does not descend from), and then the review must not be recorded."""
    status = _sync(repo)
    head = _resolve(repo, "HEAD")
    bookmark = _resolve(repo, REF)
    base, commits, problem = _coverage(repo, status, head, bookmark)
    return {"repo": repo, "head": head, "bookmark": bookmark, "sync": status, "base": base, "commits": commits, "problem": problem}


def scope_text(found: dict) -> str:
    repo = found["repo"]
    if found["problem"]:
        return (f"\n\nReview bookmark: {found['problem']} Commits pushed without a review may be missing from this "
                f"scope; the user decides which base to review from.")
    if not found["commits"]:
        return ""
    base = found["base"][:12]
    listing = "\n".join(f"  {line}" for line in found["commits"])
    return (f"\n\nAlso in scope: everything since the last review, which these {len(found['commits'])} commit(s) added "
            f"without one:\n{listing}\nRead the whole range as one change: `git -C {repo} diff {base}` for tracked files "
            f"and `git -C {repo} ls-files --others --exclude-standard` for untracked ones. A file the uncommitted diff "
            f"does not touch is still in scope when that range does.")


def mark(repo: str, base: str, tree: str | None, polished: bool) -> str:
    if _resolve(repo, base) is None:
        raise RuntimeError(f"base {base} is not a commit in {repo}")
    tree = tree or worktree_tree(repo)
    with open(_git_path(repo, RECORD), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"base": base, "head": _resolve(repo, "HEAD"), "tree": tree, "polished": polished}) + "\n")
    return f"recorded: tree {tree[:12]} reviewed from {base[:12]}{', polished' if polished else ''}"


def _read_record(repo: str) -> dict | None:
    path = _git_path(repo, RECORD)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.loads(handle.read())


def polished_since(repo: str) -> dict | None:
    """The paths changed since the workflow polished a tree, or None when no polished review covers the change set.

    A review launched with no bookmark scopes from HEAD, so commits not yet on a remote that precede its base were
    never in it; the record then covers only part of what /wrap-up is about to send, and nothing may be skipped on it.
    Commits the bookmark already holds were reviewed by an earlier run. A deletion is left out of `changed`, since
    neither skipped pass can review a path that no longer exists, and so is a mode change with the content intact,
    which leaves nothing for either pass to read."""
    record = _read_record(repo)
    if not record or not record.get("polished"):
        return None
    before = ["rev-list", record["base"], "--not", "--remotes"] + ([REF] if _resolve(repo, REF) else [])
    listed = _git(repo, *before)
    if listed.returncode != 0 or listed.stdout.strip():
        return None
    # `--raw` gives each path a `:<old mode> <new mode> <old blob> <new blob> <status>` field.
    pairs = _diff_pairs(repo, "--raw", "--no-abbrev", "--diff-filter=ACMT", record["tree"], worktree_tree(repo))
    changed = [path for meta, path in pairs if meta.split()[2] != meta.split()[3]]
    return {"tree": record["tree"], "changed": sorted(changed)}


def _diff_pairs(repo: str, *args: str) -> list[tuple[str, str]]:
    """`(field, path)` for every path `git diff -z --no-renames <args>` reports, the field being whatever the format
    flag in `args` puts before each path."""
    diff = _git(repo, "diff", "-z", "--no-renames", *args)
    if diff.returncode != 0:
        raise RuntimeError(f"git diff {' '.join(args)} failed: {diff.stderr.strip()}")
    fields = diff.stdout.split("\0")
    return list(zip(fields[::2], fields[1::2]))


def repo_relative(repo: str, path: str) -> str | None:
    """The path relative to the repo root, or None when it lies outside it. The paths come from agents' reports,
    which name a file absolutely as often as not, and `<tree>:<path>` only resolves a relative one."""
    root = os.path.realpath(repo)
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
    relative = os.path.relpath(full, root)
    return None if relative == os.pardir or relative.startswith(os.pardir + os.sep) else relative.replace(os.sep, "/")


def revert(repo: str, tree: str, paths: list[str]) -> str:
    """Put each path back as `tree` holds it, deleting one the tree does not hold. The tree comes from `snapshot`, so
    it carries untracked files too, which `git stash create` would leave out. It leaves out ignored files, so the
    tree lacking an ignored path says nothing about it, and such a path is left alone, as is one outside the repo.
    The output names the whole tree id, which is the only way back to content a wrong deletion took."""
    restored, deleted, skipped = [], [], []
    for path in paths:
        relative = repo_relative(repo, path)
        if relative is None:
            skipped.append(f"{path} (outside the repo)")
        elif _git(repo, "cat-file", "-e", f"{tree}:{relative}").returncode == 0:
            done = _git_paths(repo, "restore", f"--source={tree}", "--worktree", "--", relative)
            if done.returncode != 0:
                raise RuntimeError(f"restoring {relative} from {tree} failed: {done.stderr.strip()}")
            restored.append(relative)
        elif _git(repo, "check-ignore", "-q", "--", relative).returncode == 0:
            skipped.append(f"{relative} (ignored, so the snapshot never held it)")
        elif os.path.lexists(os.path.join(repo, relative)):
            os.remove(os.path.join(repo, relative))
            deleted.append(relative)
    left = f"; left alone: {', '.join(skipped)}" if skipped else ""
    return f"reverted to {tree}: {len(restored)} restored, {len(deleted)} deleted{left}"


def pack(repo: str, base: str, tree: str | None) -> tuple[str, int]:
    """Write the stat and the full patch from `base` to `tree` (the working tree, untracked files included, when there
    is none) into one file under the git dir, and return its path. Every reviewer and verifier of a workflow round
    reads this one file instead of re-running the same diff commands one per turn. Packs older than `PACK_MAX_AGE`
    are removed; a younger one may be another run's current round. Also returns the lines the diff adds and removes,
    which the workflow reads to size the round's reviewers; a binary file counts as none."""
    target = tree or worktree_tree(repo)
    stat = _git(repo, "diff", "--stat=200", "--no-renames", base, target, timeout=60)
    patch = _git(repo, "diff", "--no-renames", base, target, timeout=60)
    numstat = _git(repo, "diff", "--numstat", "--no-renames", base, target, timeout=60)
    for done in (stat, patch, numstat):
        if done.returncode != 0:
            raise RuntimeError(f"git diff {base} {target} failed: {done.stderr.strip()}")
    folder = _git_path(repo, PACK_DIR)
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if time.time() - os.path.getmtime(os.path.join(folder, old)) > PACK_MAX_AGE:
            os.remove(os.path.join(folder, old))
    path = os.path.join(folder, f"{base[:12]}-{target[:12]}.diff")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"# git diff {base} {target}\n{stat.stdout}\n{patch.stdout}")
    changed = sum(int(n) for line in numstat.stdout.splitlines() for n in line.split("\t")[:2] if n.isdigit())
    return path, changed


def _reviewed_commit(repo: str, record: dict, head: str) -> str | None:
    """The newest commit on HEAD's first-parent line since the review's base whose tree is the reviewed one: the
    commit the reviewed change set ended at, with any follow-up commits after it. The base itself counts, for a
    review of a tree nothing changed since."""
    listed = _git(repo, "rev-list", "--first-parent", f"{record['base']}..{head}")
    if listed.returncode != 0:
        raise RuntimeError(f"git rev-list from the review's base failed: {listed.stderr.strip()}")
    for commit in listed.stdout.split() + [record["base"]]:
        if _git(repo, "rev-parse", f"{commit}^{{tree}}").stdout.strip() == record["tree"]:
            return commit
    return None


def _ancestry_refusal(repo: str, record: dict, head: str | None, reviewed: str | None) -> str | None:
    """Why the bookmark could not move to the commit holding the reviewed tree, or None. `reviewed` is that commit,
    or None while no commit holds it yet, when the one that will is a descendant of HEAD and HEAD stands in for it.
    Both `_advance_target` and `layout` call this, so `layout` cannot offer a split that `advance` then refuses on ancestry
    grounds; `advance` can still refuse when no commit ends at the reviewed tree, which `layout` cannot foresee."""
    if head is None or not _is_ancestor(repo, record["base"], head):
        return "the review's base is no longer an ancestor of HEAD"
    current = _resolve(repo, REF)
    if current and not _is_ancestor(repo, current, reviewed or head):
        return f"the bookmark {current[:12]} is not an ancestor of the reviewed commit"
    return None


def _advance_target(repo: str, record: dict, head: str | None) -> tuple[str | None, str | None]:
    """The commit `advance` would move the bookmark to for this record, or None with the reason it would refuse.
    Both `advance` and `status` call this, so the line `status` prints cannot promise an advance that refuses."""
    reviewed = _reviewed_commit(repo, record, head) if head else None
    refusal = _ancestry_refusal(repo, record, head, reviewed)
    if refusal:
        return None, refusal
    if reviewed is None:
        return None, "no commit since the review's base holds the reviewed tree: it is still uncommitted, or a commit left part of it out or added a change it does not hold"
    return reviewed, None


def advance(repo: str) -> str:
    path = _git_path(repo, RECORD)
    record = _read_record(repo)
    if record is None:
        return "not advanced: no completed review is recorded"
    head = _resolve(repo, "HEAD")
    reviewed, refusal = _advance_target(repo, record, head)
    if refusal:
        return f"not advanced: {refusal}"
    _git(repo, "update-ref", REF, reviewed)
    os.remove(path)
    after = _git(repo, "rev-list", "--count", f"{reviewed}..{head}").stdout.strip()
    return f"advanced: {REF} -> {reviewed[:12]}" + (f", with {after} follow-up commit(s) after it for the next review" if after != "0" else "")


def _changes(repo: str, old: str, new: str) -> list[tuple[str, str]]:
    """`(status, path)` for every path that differs between two trees, renames split into a delete and an add."""
    return _diff_pairs(repo, "--name-status", old, new)


def layout(repo: str) -> dict:
    """How /yolo and /wrap-up split the change set when a recorded review covers it: `reviewed` holds what HEAD lacks of the
    reviewed tree, staged from that tree so the commits end at exactly it; `after` holds what changed since the
    review, committed after them. A path can be in both, with its reviewed content first. `applies` is false, with
    the reason, wherever the record cannot be committed as reviewed, and the change set is then committed as usual."""
    record = _read_record(repo)
    if record is None:
        return {"applies": False, "why": "no completed review is recorded"}
    head = _resolve(repo, "HEAD")
    refusal = _ancestry_refusal(repo, record, head, None)
    if refusal:
        return {"applies": False, "why": refusal}
    if _reviewed_commit(repo, record, head):
        return {"applies": False, "why": "a commit since the review's base already holds the reviewed tree"}
    # `reviewed` is HEAD's diff to the reviewed tree, so a commit that reached HEAD after `mark` (a pull of the other
    # machine's work) would enter it as a change to undo, and committing it would revert that work.
    if record.get("head") != head:
        return {"applies": False, "why": "HEAD has moved since the review was recorded (or the record, written before HEAD was recorded, cannot say which HEAD it was taken on), so the reviewed tree is not known to sit on top of it"}
    return {"applies": True, "tree": record["tree"], "base": record["base"], "polished": bool(record.get("polished")),
            "reviewed": _changes(repo, "HEAD", record["tree"]), "after": _changes(repo, record["tree"], worktree_tree(repo))}


def layout_text(found: dict) -> str:
    if not found["applies"]:
        return f"reviewed tree: none to commit as reviewed — {found['why']}; commit the change set as usual"
    lines = [f"reviewed tree: {found['tree'][:12]} (from {found['base'][:12]}{', polished' if found['polished'] else ''})",
             "reviewed — the first commits, committed with `shared/commit.py --reviewed <paths>`, the last of them ending at exactly the reviewed tree:"]
    lines += [f"  {status} {path}" for status, path in found["reviewed"]] or ["  (none)"]
    lines.append("after the review — follow-up commits, staged from the working tree as usual:")
    lines += [f"  {status} {path}" for status, path in found["after"]] or ["  (none)"]
    return "\n".join(lines)


def stage_reviewed(repo: str, paths: list[str]) -> str:
    """Stage each path as the recorded review's tree holds it, removing from the index one the tree does not hold.
    The working tree is left alone, so a file edited after the review keeps that edit for its follow-up commit."""
    record = _read_record(repo)
    if record is None:
        raise RuntimeError("no completed review is recorded, so there is no reviewed tree to stage from")
    staged, removed = [], []
    for path in paths:
        relative = repo_relative(repo, path)
        if relative is None:
            raise RuntimeError(f"{path} lies outside the repo")
        if _git(repo, "cat-file", "-e", f"{record['tree']}:{relative}").returncode == 0:
            done = _git_paths(repo, "restore", f"--source={record['tree']}", "--staged", "--", relative)
            staged.append(relative)
        else:
            done = _git_paths(repo, "rm", "--cached", "-q", "--ignore-unmatch", "--", relative)
            removed.append(relative)
        if done.returncode != 0:
            raise RuntimeError(f"staging {relative} from the reviewed tree failed: {done.stderr.strip()}")
    return f"staged from reviewed tree {record['tree'][:12]}: {len(staged)} staged, {len(removed)} removed"


def _origin_branch_holding(repo: str, sha: str, sending: tuple[str, str] | None = None) -> str | None:
    """Why `sha` may still be on a branch at origin, or None when no branch there holds it. Read from origin itself,
    since a remote-tracking ref can lag a branch the other machine pushed; a tip this clone lacks counts as holding,
    because whether it descends from `sha` cannot be told without it. `sending` is a branch push not made yet, as
    (branch, commit): it replaces that branch's tip, since a force push drops what the old tip held."""
    try:
        listed = _git(repo, "ls-remote", "--heads", REMOTE, timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"`git ls-remote --heads {REMOTE}` timed out"
    if listed.returncode != 0:
        return f"`git ls-remote --heads {REMOTE}` failed: {listed.stderr.strip()}"
    current = {ref.removeprefix("refs/heads/"): tip for tip, ref in (line.split() for line in listed.stdout.splitlines())}
    tips = {**current, sending[0]: sending[1]} if sending else current
    for branch, tip in tips.items():
        if _resolve(repo, tip) is None:
            return f"origin's branch {branch} is at {tip[:12]}, which this clone has not fetched"
        if _is_ancestor(repo, sha, tip):
            return f"origin's branch {branch} still holds it" if current.get(branch) == tip else "the branch this push sends holds it"
    return None


def _unpublished(repo: str, sha: str, *sending: str) -> bool:
    """Whether `sha` holds commits no remote branch has, counting the revs in `sending` as pushed already. Pushing
    the ref uploads the commit it names, so `push` waits until a branch push has published that commit."""
    return bool(_git(repo, "rev-list", sha, "--not", "--remotes", *sending).stdout.strip())


def _replacement(repo: str, local: str, remote: str | None, sending: tuple[str, str] | None = None) -> tuple[bool, str | None]:
    """Whether replacing origin's bookmark `remote` by `local` rewinds it, so its push needs a lease, and why it must
    not be replaced at all, or None. Only a rewind can be refused, and only while an origin branch still holds
    `remote` once the branch push in `sending` is done. Both `push` and `forecast` call this, so the line printed
    before a push cannot promise a replacement `push` refuses."""
    if not remote or _is_ancestor(repo, remote, local):
        return False, None
    holder = _origin_branch_holding(repo, remote, sending)
    return True, (f"origin's bookmark {remote[:12]} is not an ancestor of the local one, and {holder}" if holder else None)


def push(repo: str) -> str:
    if not _has_remote(repo):
        return "not pushed: no origin remote"
    bookmark = _resolve(repo, REF)
    if bookmark is None:
        return "not pushed: no bookmark yet"
    if _unpublished(repo, bookmark):
        return "not pushed: the bookmarked commit is not on any remote branch yet"
    status = _sync(repo)
    if status != "ok":
        return f"not pushed: {status}"
    # `_sync` moves the local bookmark up to a newer one on origin, which then has nothing to push.
    bookmark = _resolve(repo, REF)
    remote = _resolve(repo, FETCHED)
    if remote == bookmark:
        return "up to date"
    rewinds, refusal = _replacement(repo, bookmark, remote)
    if refusal:
        return f"not pushed: {refusal}"
    # A rebased branch force-pushed past origin's bookmark leaves it naming history no origin branch holds any more,
    # so replacing it loses no review anyone can build on. The lease refuses if it moved since the fetch.
    lease = [f"--force-with-lease={REF}:{remote}"] if rewinds else []
    done = _git(repo, "push", *lease, REMOTE, f"{REF}:{REF}", timeout=NETWORK_TIMEOUT)
    if done.returncode != 0:
        return f"not pushed: {done.stderr.strip()}"
    return f"pushed: {REF} -> {bookmark[:12]}"


def _short(sha: str | None) -> str:
    return sha[:12] if sha else "none"


def status(repo: str) -> str:
    """One line for just after a push and the end of every report that pushes: where the bookmark stands locally and
    on origin, how many commits on HEAD the next review covers, and whether a recorded review is still waiting or why
    `advance` would refuse it. It reads origin with `ls-remote` and changes nothing, so it can follow a failed
    `advance` or `push` without disturbing either."""
    local = _resolve(repo, REF)
    parts = [f"local {_short(local)}"]
    bookmark, sync = local, "local-only"
    if not _has_remote(repo):
        parts.append("no origin remote")
    else:
        remote, error, bookmark, sync = _origin_view(repo, local)
        parts.append(f"origin unreadable: {error}" if error else f"origin {_short(remote)} ({'agree' if remote == local else 'differ'})")
    head = _resolve(repo, "HEAD")
    parts.append(_coverage_part(repo, sync, head, bookmark, "it" if bookmark == local else f"origin's {(bookmark or '')[:12]}"))
    parts += _record_part(repo, head)
    return "review bookmark: " + " · ".join(parts)


def _origin_view(repo: str, local: str | None) -> tuple[str | None, str | None, str | None, str]:
    """Origin's bookmark as `ls-remote` lists it, why origin could not be read (or None), the bookmark the next review
    counts from, and the sync state `_coverage` takes: `ok`, the read error, or a sentence saying origin's bookmark is
    not in this clone yet. The push's own `_sync`, or failing that the next `plan`'s, takes origin's bookmark when it
    supersedes the local one. `status` and `forecast` both call this on a repo with an origin remote, so the lines
    around a push count from the same bookmark."""
    remote, error = _origin_bookmark(repo)
    if error:
        return None, error, local, error
    if remote and _resolve(repo, remote) is None:
        return remote, None, local, f"origin's bookmark {remote[:12]} is not in this clone yet"
    return remote, None, (remote if _supersedes(repo, local, remote) else local), "ok"


def _coverage_part(repo: str, sync: str, head: str | None, bookmark: str | None, called: str) -> str:
    """What the next review covers from `bookmark`, named `called` in the sentence. `status` and `forecast` both end
    on it, so the line before a push and the line after it count the same way."""
    _, commits, problem = _coverage(repo, sync, head, bookmark)
    if problem:
        return f"the next review has no base to record: {problem}"
    if bookmark is None:
        return "no bookmark, so the next review starts from HEAD"
    return f"{len(commits)} commit(s) on HEAD past {called}, which the next review covers"


def _record_part(repo: str, head: str | None) -> list[str]:
    """A recorded review still waiting, and whether `advance` would take it, or nothing when none is recorded."""
    record = _read_record(repo)
    if not record:
        return []
    reviewed, refusal = _advance_target(repo, record, head)
    return [f"a recorded review of tree {record['tree'][:12]} cannot advance: {refusal}" if refusal else f"a recorded review ending at {reviewed[:12]} awaits `advance`"]


def forecast(repo: str, publish: bool) -> str:
    """One line for just before a push: where the bookmark will stand once the push is done. The branch push is taken
    to send HEAD to origin's branch of the same name, replacing its tip as a force push would. `publish` says the
    caller runs `push` after it, as shared/push.py does; without it origin's bookmark stays where it is. It reads
    origin with `ls-remote` and changes nothing, like `status`, which reports the same things after the push."""
    local = _resolve(repo, REF)
    head = _resolve(repo, "HEAD")
    after, sync = local, "local-only"
    if not _has_remote(repo):
        outcome = f"stays at {_short(local)}: no origin remote to publish it to"
    else:
        remote, error, after, sync = _origin_view(repo, local)
        if error:
            outcome = f"unknown, since origin could not be read: {error}"
        elif sync != "ok":
            outcome = f"{sync}, so whether it replaces local {_short(local)} is unknown"
        elif remote is None and local is None:
            outcome = "none on either side, so nothing is published"
        elif local == remote:
            outcome = f"stays at {_short(local)}, where local and origin already agree"
        elif after == remote:
            outcome = f"stays at origin's {_short(remote)}" + (f", which replaces the older local {_short(local)}" if local else "")
        elif not publish:
            outcome = f"origin stays at {_short(remote)}: this push does not publish the local {_short(local)}"
        elif _unpublished(repo, local, *([head] if head else [])):
            outcome = f"origin stays at {_short(remote)}: the bookmarked commit {_short(local)} is on no branch this push sends"
        else:
            branch = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
            _, refusal = _replacement(repo, local, remote, (branch, head) if branch and head else None)
            outcome = f"origin stays at {_short(remote)}: {refusal}" if refusal else f"origin moves to {_short(local)} (from {_short(remote)})"
    parts = [outcome, _coverage_part(repo, sync, head, after, _short(after))] + _record_part(repo, head)
    return "review bookmark after this push: " + " · ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["scope", "mark", "advance", "push", "status", "forecast", "snapshot", "pack", "revert", "layout", "stage-reviewed"])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base")
    parser.add_argument("--tree")
    parser.add_argument("--polished", action="store_true")
    parser.add_argument("--publish", action="store_true", help="forecast: the caller runs `push` after its branch push")
    parser.add_argument("paths", nargs="*")
    opts = parser.parse_args()
    repo = toplevel(opts.repo)
    if repo is None:
        print(f"{opts.repo} is not inside a git repository", file=sys.stderr)
        return 2
    try:
        if opts.command == "scope":
            found = plan(repo)
            print(json.dumps(found, indent=2))
            print(scope_text(found).strip() or "Nothing unreviewed beyond the uncommitted changes.")
        elif opts.command == "mark":
            if not opts.base:
                parser.error("mark needs --base")
            print(mark(repo, opts.base, opts.tree, opts.polished))
        elif opts.command == "snapshot":
            print(worktree_tree(repo))
        elif opts.command == "pack":
            if not opts.base:
                parser.error("pack needs --base")
            path, changed = pack(repo, opts.base, opts.tree)
            print(f"{path}\nchanged-lines: {changed}")
        elif opts.command == "revert":
            if not opts.tree:
                parser.error("revert needs --tree")
            print(revert(repo, opts.tree, opts.paths))
        elif opts.command == "advance":
            print(advance(repo))
        elif opts.command == "layout":
            print(layout_text(layout(repo)))
        elif opts.command == "stage-reviewed":
            if not opts.paths:
                parser.error("stage-reviewed needs the paths to stage")
            print(stage_reviewed(repo, opts.paths))
        elif opts.command == "status":
            print(status(repo))
        elif opts.command == "forecast":
            print(forecast(repo, opts.publish))
        else:
            print(push(repo))
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print(f"review_scope {opts.command} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
