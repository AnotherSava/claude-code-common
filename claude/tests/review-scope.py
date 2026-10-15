#!/usr/bin/env python3
"""Cases for `claude/scripts/review_scope.py` and the `claude/hooks/review-scope.py` hook that calls it.

The bookmark has one failure that matters: moving past code no review saw, which then never gets reviewed. Every
other failure leaves it behind and costs a second look. So most cases here try to make it move when it must not:
an edit after the review, a partial commit, rewritten history, an origin that cannot be read. Each runs against
real repos — a bare origin and two clones standing for the two machines — sealed from this machine's git config.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "claude", "scripts"))
HOOK = os.path.join(ROOT, "claude", "hooks", "review-scope.py")

import review_scope  # noqa: E402 — needs the sys.path line above

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def sh(repo: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def write(repo: str, name: str, text: str) -> None:
    with open(os.path.join(repo, name), "w", encoding="utf-8") as handle:
        handle.write(text)


def commit(repo: str, name: str, text: str) -> str:
    write(repo, name, text)
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", f"edit {name}")
    return sh(repo, "rev-parse", "HEAD")


def bookmark(repo: str) -> str | None:
    return review_scope._resolve(repo, review_scope.REF)


def review(repo: str) -> dict:
    """What a complete review does to the record: plan at launch, mark the tree it covered."""
    found = review_scope.plan(repo)
    review_scope.mark(repo, found["base"], review_scope.worktree_tree(repo), False)
    return found


def hook(payload: dict) -> dict | None:
    done = subprocess.run([sys.executable, "-S", HOOK], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    check("the hook exits 0", done.returncode, 0)
    return json.loads(done.stdout) if done.stdout.strip() else None


def main() -> int:
    # Both hooks match calls by this name, so a workflow renamed without it would leave every review unwidened.
    with open(os.path.join(ROOT, "claude", "workflows", f"{review_scope.WORKFLOW}.js"), encoding="utf-8") as handle:
        name = re.search(r"^\s*name:\s*'([^']+)'", handle.read(), re.MULTILINE)
    check("the saved workflow's meta.name is the name the hooks match", name and name.group(1), review_scope.WORKFLOW)

    scratch = tempfile.mkdtemp(prefix="review-scope-test-")
    os.environ.update({"GIT_CONFIG_GLOBAL": os.path.join(scratch, "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"})
    with open(os.environ["GIT_CONFIG_GLOBAL"], "w", encoding="utf-8") as handle:
        handle.write("[user]\n\tname = t\n\temail = t@example.invalid\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
    try:
        origin, a, b = (os.path.join(scratch, n) for n in ("origin.git", "a", "b"))
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
        subprocess.run(["git", "clone", "-q", origin, a], check=True, capture_output=True)
        first = commit(a, "app.txt", "one\n")
        sh(a, "push", "-q", "-u", "origin", "main")

        found = review_scope.plan(a)
        check("with no bookmark anywhere the base is HEAD", (found["base"], found["commits"], found["problem"]), (first, [], None))
        check("and nothing is added to the scope", review_scope.scope_text(found), "")

        # A same-size edit whose stat matches the index entry is caught only through racy-git detection, which compares
        # the entry's mtime with the index file's; pinning both to one instant makes the race happen on every run. The
        # file is backdated before it is committed, or git marks the entry racy at commit time and re-hashes it anyway.
        racy = os.path.join(scratch, "racy")
        subprocess.run(["git", "init", "-q", racy], check=True)
        app, index = os.path.join(racy, "app.txt"), os.path.join(racy, ".git", "index")
        past = (os.stat(scratch).st_mtime_ns // 10**9 - 60) * 10**9
        write(racy, "app.txt", "one\n")
        os.utime(app, ns=(past, past))
        sh(racy, "add", "-A")
        sh(racy, "commit", "-qm", "edit app.txt")
        write(racy, "app.txt", "two\n")
        os.utime(app, ns=(past, past))
        os.utime(index, ns=(past, past))
        check("a same-size edit in the index's own tick enters the reviewed tree", sh(racy, "rev-parse", f"{review_scope.worktree_tree(racy)}:app.txt"), sh(racy, "hash-object", "app.txt"))

        write(a, "app.txt", "two\n")
        write(a, "new.txt", "untracked\n")
        review(a)
        sh(a, "add", "app.txt")
        sh(a, "commit", "-qm", "partial")
        check("a commit leaving out a reviewed file does not advance", review_scope.advance(a).startswith("not advanced: HEAD's tree differs"), True)
        sh(a, "add", "new.txt")
        sh(a, "commit", "-qm", "rest")
        reviewed = sh(a, "rev-parse", "HEAD")
        check("committing exactly the reviewed tree, untracked file included, advances", review_scope.advance(a), f"advanced: {review_scope.REF} -> {reviewed[:12]}")
        check("and consumes the record", review_scope.advance(a), "not advanced: no completed review is recorded")

        check("the bookmark is not pushed before its commit is", review_scope.push(a), "not pushed: the bookmarked commit is not on any remote branch yet")
        sh(a, "push", "-q")
        check("once the commit is on origin it is", review_scope.push(a), f"pushed: {review_scope.REF} -> {reviewed[:12]}")
        check("a second push is a no-op", review_scope.push(a), "up to date")

        write(a, "app.txt", "three\n")
        review(a)
        write(a, "app.txt", "three, edited after the review\n")
        sh(a, "commit", "-qam", "edited")
        check("an edit made after the review keeps the bookmark back", (review_scope.advance(a).startswith("not advanced"), bookmark(a)), (True, reviewed))
        sh(a, "push", "-q")

        # The other machine: it has never seen the bookmark, pushes two commits with no review, and its next review
        # must cover them along with the unreviewed commit from the first machine.
        subprocess.run(["git", "clone", "-q", origin, b], check=True, capture_output=True)
        check("a fresh clone has no local bookmark", bookmark(b), None)
        commit(b, "app.txt", "four\n")
        commit(b, "other.txt", "five\n")
        sh(b, "push", "-q")
        found = review_scope.plan(b)
        check("planning fetches origin's bookmark as the base", found["base"], reviewed)
        check("and lists every commit after it, from both machines", [line.split(" ", 1)[1] for line in found["commits"]], ["edit other.txt", "edit app.txt", "edited"])
        text = review_scope.scope_text(found)
        check("the scope names the range to diff", f"diff {reviewed[:12]}" in text and "3 commit(s)" in text, True)

        review(b)
        check("a review of a clean tree advances on the commit it sits on", review_scope.advance(b).startswith("advanced"), True)
        check("and pushes", review_scope.push(b).startswith("pushed"), True)
        sh(a, "pull", "-q")
        check("the first machine picks it up at its next plan", review_scope.plan(a)["base"], sh(b, "rev-parse", "HEAD"))
        check("an older local bookmark never overwrites origin's newer one", review_scope.push(a), "up to date")

        # History rewritten past the bookmark: the unreviewed range is unknown, so no base is offered.
        sh(a, "reset", "-q", "--hard", first)
        commit(a, "app.txt", "rewritten\n")
        found = review_scope.plan(a)
        check("a bookmark HEAD does not descend from gives no base", (found["base"], "not an ancestor of HEAD" in (found["problem"] or "")), (None, True))
        check("and the scope says so", "the user decides which base" in review_scope.scope_text(found), True)

        sh(b, "remote", "set-url", "origin", os.path.join(scratch, "gone.git"))
        found = review_scope.plan(b)
        check("an unreadable origin gives no base, since its bookmark may be newer", (found["base"], "could not be read" in (found["problem"] or "")), (None, True))

        # The hook, fed the payload PreToolUse delivers.
        sh(b, "remote", "set-url", "origin", origin)
        sh(b, "fetch", "-q")
        sh(b, "reset", "-q", "--hard", "origin/main")
        published = bookmark(b)
        sh(b, "checkout", "-q", "-b", "side", first)
        side = commit(b, "side.txt", "unrelated\n")
        sh(b, "push", "-q", "origin", "side")
        sh(b, "checkout", "-q", "main")
        sh(b, "update-ref", review_scope.REF, side)
        check("a local bookmark unrelated to origin's is never pushed over it", review_scope.push(b), f"not pushed: origin's bookmark {published[:12]} is not an ancestor of the local one")
        sh(b, "update-ref", review_scope.REF, published)
        commit(b, "late.txt", "unreviewed\n")
        payload = {"tool_name": "Workflow", "cwd": scratch, "tool_input": {"name": "review-auto", "args": {"scope": "the uncommitted diff", "lenses": [], "repo": b}}}
        out = hook(payload)
        updated = (out or {}).get("hookSpecificOutput", {}).get("updatedInput", {})
        args = updated.get("args", {})
        check("the hook keeps the rest of the call", (updated.get("name"), args.get("lenses")), ("review-auto", []))
        check("and appends the unreviewed commit to the scope", args.get("scope", "").startswith("the uncommitted diff\n\nAlso in scope") and "edit late.txt" in args.get("scope", ""), True)
        check("and passes the base and the tree at launch", (args.get("review_bookmark") or {}).get("tree"), review_scope.worktree_tree(b))
        check("and tells the model", "1 commit(s) since the last review" in out["hookSpecificOutput"].get("additionalContext", ""), True)

        os.environ["CLAUDE_PROJECT_DIR"] = b
        out = hook({**payload, "tool_input": {"name": "review-auto", "args": json.dumps({"scope": "s", "lenses": [], "review_bookmark": {"base": "forged"}})}})
        args = out["hookSpecificOutput"]["updatedInput"]["args"]
        check("args sent as a JSON string are read, and the project directory stands in for a missing repo", os.path.realpath(args["review_bookmark"]["repo"]), os.path.realpath(b))
        check("a review_bookmark the caller wrote is replaced", args["review_bookmark"]["base"] != "forged", True)

        os.environ["CLAUDE_PROJECT_DIR"] = a
        out = hook({**payload, "tool_input": {"name": "review-auto", "args": {"scope": "s", "lenses": []}}})
        check("with no trustworthy base the hook passes no bookmark", "review_bookmark" in out["hookSpecificOutput"]["updatedInput"]["args"], False)
        check("and asks for one", "ask which base" in out["hookSpecificOutput"]["additionalContext"], True)

        check("another workflow passes through", hook({**payload, "tool_input": {"name": "other", "args": {"scope": "s"}}}), None)
        check("an inline script passes through", hook({**payload, "tool_input": {"script": "export const meta = {}"}}), None)
        os.environ["CLAUDE_PROJECT_DIR"] = scratch
        check("a directory outside git passes through", hook({**payload, "tool_input": {"name": "review-auto", "args": {"scope": "s", "lenses": []}}}), None)
        broken = os.path.join(scratch, "broken")
        subprocess.run(["git", "init", "-q", broken], check=True)
        commit(broken, "f.txt", "x\n")
        sh(broken, "update-ref", review_scope.REF, review_scope._resolve(broken, "HEAD"))
        with open(os.path.join(sh(broken, "rev-parse", "--absolute-git-dir"), "index"), "w", encoding="utf-8") as handle:
            handle.write("not an index")
        out = hook({**payload, "tool_input": {"name": "review-auto", "args": {"scope": "s", "lenses": [], "repo": broken, "review_bookmark": {"base": "forged"}}}})
        context = (out or {}).get("hookSpecificOutput", {})
        check("a hook that fails says so", "review-scope hook failed" in context.get("additionalContext", ""), True)
        check("and strips a bookmark the caller wrote, so the review cannot be recorded", "review_bookmark" in context.get("updatedInput", {}).get("args", {"review_bookmark": 1}), False)
        check("garbage on stdin exits quietly", subprocess.run([sys.executable, "-S", HOOK], input="not json", capture_output=True, text=True, timeout=30).stdout, "")

        # The polish record /commit reads to skip its own clean-up passes. Skipping on a record that does not cover
        # the change set leaves code nobody cleaned, so most cases try to make `polished_since` answer when it must not.
        p_origin, p = os.path.join(scratch, "p-origin.git"), os.path.join(scratch, "p")
        subprocess.run(["git", "init", "-q", "--bare", p_origin], check=True)
        subprocess.run(["git", "clone", "-q", p_origin, p], check=True, capture_output=True)
        commit(p, "app.py", "one\n")
        sh(p, "push", "-q", "-u", "origin", "main")
        write(p, "app.py", "two\n")
        found = review_scope.plan(p)
        review_scope.mark(p, found["base"], None, False)
        check("an unpolished record skips nothing", review_scope.polished_since(p), None)
        tree = review_scope.worktree_tree(p)
        review_scope.mark(p, found["base"], None, True)
        check("a polished record over the tree as it stands reports nothing changed since", review_scope.polished_since(p), {"tree": tree, "changed": []})
        write(p, "memo.md", "written after the polish\n")
        check("a file written after the polish is named, untracked or not", review_scope.polished_since(p)["changed"], ["memo.md"])
        os.remove(os.path.join(p, "memo.md"))
        os.remove(os.path.join(p, "app.py"))
        check("a deletion since the polish is left out", review_scope.polished_since(p)["changed"], [])
        write(p, "app.py", "two\n")
        sh(p, "commit", "-qam", "polished")
        check("committing the polished tree keeps it covered", review_scope.polished_since(p)["changed"], [])

        # A review launched with no bookmark scopes from HEAD, so an unpushed commit before its base was never in it.
        commit(p, "early.py", "unreviewed\n")
        found = review_scope.plan(p)
        review_scope.mark(p, found["base"], None, True)
        check("an unpushed commit the review never covered skips nothing", review_scope.polished_since(p), None)
        sh(p, "update-ref", review_scope.REF, sh(p, "rev-parse", "HEAD"))
        check("but one the bookmark holds was reviewed earlier", review_scope.polished_since(p), {"tree": review_scope.worktree_tree(p), "changed": []})

        before = review_scope.worktree_tree(p)
        write(p, "app.py", "polished badly\n")
        write(p, "helper.py", "created by the polish\n")
        write(p, "early.py", "kept\n")
        check("revert names what it did", review_scope.revert(p, before, ["app.py", "helper.py"]), f"reverted to {before}: 1 restored, 1 deleted")
        with open(os.path.join(p, "app.py"), encoding="utf-8") as handle:
            check("a reverted file holds the snapshot's content", handle.read(), "two\n")
        check("a file the snapshot did not hold is removed", os.path.exists(os.path.join(p, "helper.py")), False)
        with open(os.path.join(p, "early.py"), encoding="utf-8") as handle:
            check("a path not named is left alone", handle.read(), "kept\n")

        # Agents name a file absolutely as often as not, and the snapshot never holds an ignored one.
        write(p, ".gitignore", ".env\n")
        write(p, ".env", "secret\n")
        before = review_scope.worktree_tree(p)
        write(p, "app.py", "polished badly\n")
        outside = os.path.join(scratch, "outside.py")
        write(scratch, "outside.py", "not the repo's\n")
        got = review_scope.revert(p, before, [os.path.join(p, "app.py"), ".env", outside])
        check("an absolute path is restored, and an ignored or outside one left alone", got, f"reverted to {before}: 1 restored, 0 deleted; left alone: .env (ignored, so the snapshot never held it), {outside} (outside the repo)")
        with open(os.path.join(p, "app.py"), encoding="utf-8") as handle:
            check("an absolutely named file holds the snapshot's content", handle.read(), "two\n")
        check("the ignored file and the outside one survive", [os.path.exists(os.path.join(p, ".env")), os.path.exists(outside)], [True, True])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    for line in failures:
        print(line)
    print(f"review-scope tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
