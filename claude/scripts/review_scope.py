#!/usr/bin/env python3
"""The review bookmark: which part of a repo's history an adversarial review has already covered.

Small changes get pushed without a review, so a review scoped to the uncommitted diff never sees them. The
bookmark is the ref `refs/review/last`, shared through origin so both machines read the same one. It always
points at a real commit whose content a review covered. Every review then takes in everything between the
bookmark and the working tree, whoever pushed it and however.

Three moments act on it, and each belongs to a different caller:

- `plan`, called in-process by the `review-scope.py` PreToolUse hook when the `review-auto` workflow launches,
  brings the local bookmark up to date with origin's and works out what the review must cover. The `scope` command
  prints the same for a run by hand.
- `mark`, run by the workflow's last agent once a review finished with no gaps, records which tree it covered
  and from which base, and whether the workflow's polish ran over it. Nothing moves yet: the tree is usually
  uncommitted.
- `advance`, run by `/commit` after its commits, moves the bookmark to HEAD only when HEAD's tree is exactly the
  recorded one, so an edit made after the review leaves the bookmark where it was. `push` then publishes it.

Between `mark` and `advance`, `/commit`'s change_scope.py reads the record through `polished_since` to skip the
`/clean-code` and `/docs-relevance` passes the workflow already ran. `snapshot` and `revert` serve the workflow's
polish phase, which takes back what it cannot keep.

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

# The saved workflow whose runs this bookmark tracks. Both the review-scope.py and workflow-realism.py hooks match
# Workflow calls against it, and it must equal `meta.name` in claude/workflows/review-auto.js.
WORKFLOW = "review-auto"
REF = "refs/review/last"
FETCHED = "refs/review/origin"
RECORD = "review-scope-reviewed"
SCRATCH_INDEX = "review-scope-index"
REMOTE = "origin"
NETWORK_TIMEOUT = 20


def _git(repo: str, *args: str, env: dict | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout, env=env)


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


def worktree_tree(repo: str) -> str:
    """The tree of every file git does not ignore, tracked or not, written through a scratch index so the real one is
    untouched. Seeded from the real index, or a tracked file under an ignored directory would be left out, and copied
    with its mtime, or a same-size edit made in the real index's own tick enters the tree as its old content
    (learnings/git-snapshot-dirty-tree.md)."""
    scratch = _git_path(repo, SCRATCH_INDEX)
    real = _git_path(repo, "index")
    try:
        if os.path.exists(real):
            shutil.copy2(real, scratch)
        env = {**os.environ, "GIT_INDEX_FILE": scratch}
        added = _git(repo, "add", "-A", env=env, timeout=60)
        if added.returncode != 0:
            raise RuntimeError(f"git add -A into the scratch index failed: {added.stderr.strip()}")
        written = _git(repo, "write-tree", env=env)
        if written.returncode != 0:
            raise RuntimeError(f"git write-tree failed: {written.stderr.strip()}")
        return written.stdout.strip()
    finally:
        if os.path.exists(scratch):
            os.remove(scratch)


def _has_remote(repo: str) -> bool:
    return _git(repo, "remote", "get-url", REMOTE).returncode == 0


def _sync(repo: str) -> str:
    """Bring the local bookmark up to origin's when origin's is newer. Returns `ok`, `local-only` or a sentence saying
    why origin could not be read. A failure leaves the local bookmark as it was, which can only be older."""
    if not _has_remote(repo):
        return "local-only"
    try:
        listed = _git(repo, "ls-remote", REMOTE, REF, timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"`git ls-remote {REMOTE}` timed out"
    if listed.returncode != 0:
        return f"`git ls-remote {REMOTE}` failed: {listed.stderr.strip()}"
    if not listed.stdout.strip():
        return "ok"
    try:
        fetched = _git(repo, "fetch", "--no-tags", REMOTE, f"+{REF}:{FETCHED}", timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"fetching {REF} from {REMOTE} timed out"
    if fetched.returncode != 0:
        return f"fetching {REF} from {REMOTE} failed: {fetched.stderr.strip()}"
    remote = _resolve(repo, FETCHED)
    local = _resolve(repo, REF)
    if remote and (not local or (local != remote and _is_ancestor(repo, local, remote))):
        _git(repo, "update-ref", REF, remote)
    return "ok"


def plan(repo: str) -> dict:
    """What a review launched now must cover. `base` is the commit it diffs from; it is null when no base can be trusted
    (origin unreadable, or a bookmark HEAD does not descend from), and then the review must not be recorded."""
    status = _sync(repo)
    head = _resolve(repo, "HEAD")
    bookmark = _resolve(repo, REF)
    result = {"repo": repo, "head": head, "bookmark": bookmark, "sync": status, "base": None, "commits": [], "problem": None}
    if status not in ("ok", "local-only"):
        result["problem"] = f"Origin's review bookmark could not be read ({status}), so the commits it would add are unknown."
        return result
    if head is None:
        result["problem"] = "The repo has no commits yet."
        return result
    if bookmark and not _is_ancestor(repo, bookmark, head):
        result["problem"] = (f"The review bookmark {bookmark[:12]} is not an ancestor of HEAD, so history was rewritten "
                             f"after the last review and the unreviewed range is unknown.")
        return result
    result["base"] = bookmark or head
    if bookmark:
        log = _git(repo, "log", "--format=%h %s", f"{bookmark}..{head}").stdout.splitlines()
        result["commits"] = [line for line in log if line.strip()]
    return result


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
        handle.write(json.dumps({"base": base, "tree": tree, "polished": polished}) + "\n")
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
    never in it; the record then covers only part of what /commit is about to send, and nothing may be skipped on it.
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
    diff = _git(repo, "diff", "--raw", "-z", "--no-renames", "--no-abbrev", "--diff-filter=ACMT", record["tree"], worktree_tree(repo))
    if diff.returncode != 0:
        raise RuntimeError(f"git diff against the polished tree failed: {diff.stderr.strip()}")
    # `--raw -z` alternates a `:<old mode> <new mode> <old blob> <new blob> <status>` field with the path it describes.
    fields = diff.stdout.split("\0")
    changed = [path for meta, path in zip(fields[::2], fields[1::2]) if meta.split()[2] != meta.split()[3]]
    return {"tree": record["tree"], "changed": sorted(changed)}


def _repo_relative(repo: str, path: str) -> str | None:
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
        relative = _repo_relative(repo, path)
        if relative is None:
            skipped.append(f"{path} (outside the repo)")
        elif _git(repo, "cat-file", "-e", f"{tree}:{relative}").returncode == 0:
            done = _git(repo, "restore", f"--source={tree}", "--worktree", "--", relative)
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


def advance(repo: str) -> str:
    path = _git_path(repo, RECORD)
    record = _read_record(repo)
    if record is None:
        return "not advanced: no completed review is recorded"
    head = _resolve(repo, "HEAD")
    head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    if head_tree != record["tree"]:
        return "not advanced: HEAD's tree differs from the reviewed one, so something committed was never reviewed"
    if not _is_ancestor(repo, record["base"], head):
        return "not advanced: the review's base is no longer an ancestor of HEAD"
    current = _resolve(repo, REF)
    if current and not _is_ancestor(repo, current, head):
        return f"not advanced: the bookmark {current[:12]} is not an ancestor of HEAD"
    _git(repo, "update-ref", REF, head)
    os.remove(path)
    return f"advanced: {REF} -> {head[:12]}"


def push(repo: str) -> str:
    if not _has_remote(repo):
        return "not pushed: no origin remote"
    bookmark = _resolve(repo, REF)
    if bookmark is None:
        return "not pushed: no bookmark yet"
    # Pushing the ref uploads the commit it names, so it waits until a branch push has published that commit.
    if _git(repo, "rev-list", bookmark, "--not", "--remotes").stdout.strip():
        return "not pushed: the bookmarked commit is not on any remote branch yet"
    status = _sync(repo)
    if status != "ok":
        return f"not pushed: {status}"
    remote = _resolve(repo, FETCHED)
    if remote == bookmark:
        return "up to date"
    if remote and not _is_ancestor(repo, remote, bookmark):
        return f"not pushed: origin's bookmark {remote[:12]} is not an ancestor of the local one"
    done = _git(repo, "push", REMOTE, f"{REF}:{REF}", timeout=NETWORK_TIMEOUT)
    if done.returncode != 0:
        return f"not pushed: {done.stderr.strip()}"
    return f"pushed: {REF} -> {bookmark[:12]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["scope", "mark", "advance", "push", "snapshot", "revert"])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base")
    parser.add_argument("--tree")
    parser.add_argument("--polished", action="store_true")
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
        elif opts.command == "revert":
            if not opts.tree:
                parser.error("revert needs --tree")
            print(revert(repo, opts.tree, opts.paths))
        elif opts.command == "advance":
            print(advance(repo))
        else:
            print(push(repo))
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print(f"review_scope {opts.command} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
