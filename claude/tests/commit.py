#!/usr/bin/env python3
"""Cases for `claude/skills/shared/commit.py`, the one place a commit is made.

Its costly failures are a commit holding something it should not — a path someone else staged, a value the privacy
scan exists to stop, content the review never read — and a refusal that leaves the index half staged. Each case runs
the script for real against a scratch repo sealed from this machine's git config.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from git_scratch import check, failures, seal, sh, write

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "shared", "commit.py")
sys.path.insert(0, os.path.join(ROOT, "claude", "scripts"))
import review_scope  # noqa: E402

def run(repo: str, message: str, *args: str) -> tuple[int, str]:
    msg = os.path.join(os.path.dirname(repo), "msg.txt")
    write(os.path.dirname(repo), "msg.txt", message)
    done = subprocess.run([sys.executable, SCRIPT, "-F", msg, "--repo", repo, *args], capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout


def mode(repo: str, path: str) -> str:
    """The index mode of a path, or empty when the index does not hold it."""
    return (sh(repo, "ls-files", "-s", "--", path).split() or [""])[0]


def held(repo: str) -> list[str]:
    return sorted(sh(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "HEAD").split())


def fresh(scratch: str, name: str) -> str:
    repo = os.path.join(scratch, name)
    subprocess.run(["git", "init", "-q", repo], check=True)
    write(repo, "app.txt", "one\n")
    write(repo, "notes.txt", "notes\n")
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", "start")
    return repo


def main() -> int:
    scratch = tempfile.mkdtemp(prefix="commit-test-")
    try:
        seal(scratch)

        repo = fresh(scratch, "plain")
        write(repo, "app.txt", "two\n")
        write(repo, "notes.txt", "staged by someone else\n")
        sh(repo, "add", "notes.txt")
        code, out = run(repo, "feat: change the app\n", "app.txt")
        check("a clean commit succeeds", code, 0)
        check("and holds only the path given, not one staged earlier", held(repo), ["app.txt"])
        check("the earlier staged edit stays in the working tree", sh(repo, "status", "--short"), "M notes.txt")

        head = sh(repo, "rev-parse", "HEAD")
        code, out = run(repo, "feat: nothing here\n", "app.txt")
        check("a path with no change is refused", (code, "no change to commit in: app.txt" in out), (1, True))
        check("and makes no commit", sh(repo, "rev-parse", "HEAD"), head)

        code, out = run(repo, "Feat: Capitalised and far too long for any subject line to be allowed.\n", "notes.txt")
        check("a message failing the checker is refused", (code, "check-commit-message.py" in out), (1, True))
        check("and the refusal leaves nothing staged", sh(repo, "diff", "--cached", "--name-only"), "")

        write(repo, "deploy.txt", "reach the box at 100.64.12.7\n")
        code, out = run(repo, "docs: add deploy notes\n", "deploy.txt")
        check("a blocking privacy finding is refused", (code, "ipv4" in out), (1, True))
        fingerprint = out.split("allow=")[1].split()[0] if "allow=" in out else ""
        write(repo, ".claude/confidentiality-allow", f"{fingerprint}  # documentation address, not a machine\n")
        code, out = run(repo, "docs: add deploy notes\n", "deploy.txt", ".claude/confidentiality-allow")
        check("the same commit passes once its fingerprint is allowed", code, 0)

        write(repo, "readme.txt", "keep the api token in the secret manager\n")
        code, out = run(repo, "docs: add a readme\n", "readme.txt")
        check("a review finding commits and is printed", (code, "review finding" in out), (0, True))

        write(repo, "hook.sh", "#!/usr/bin/env bash\necho hi\n")
        os.chmod(os.path.join(repo, "hook.sh"), 0o755)
        sh(repo, "config", "core.filemode", "false")
        code, out = run(repo, "feat: add a hook\n", "hook.sh")
        if os.name != "nt":  # Windows has no execute bit to read, so a new script there stays 644 by design
            check("an executable script commits as 755 even where core.filemode is false", mode(repo, "hook.sh"), "100755")
        write(repo, "lib.py", "#!/usr/bin/env python3\n# a library, deliberately not executable\n")
        os.chmod(os.path.join(repo, "lib.py"), 0o644)
        run(repo, "feat: add a library\n", "lib.py")
        check("a shebang'd file not executable on disk keeps 644", mode(repo, "lib.py"), "100644")
        write(repo, "lib.py", "#!/usr/bin/env python3\n# a library, edited\n")
        os.chmod(os.path.join(repo, "lib.py"), 0o755)
        run(repo, "fix: edit the library\n", "lib.py")
        check("a tracked 644 file keeps its mode whatever the disk says", mode(repo, "lib.py"), "100644")
        write(repo, "tool.sh", "#!/usr/bin/env bash\necho tool\n")
        os.chmod(os.path.join(repo, "tool.sh"), 0o644)
        sh(repo, "add", "--chmod=+x", "tool.sh")
        run(repo, "feat: add a tool\n", "tool.sh")
        check("a path staged +x before the call keeps it where core.filemode is false", mode(repo, "tool.sh"), "100755")
        sh(repo, "add", "--chmod=+x", "lib.py")
        code, out = run(repo, "fix: make the library executable\n", "lib.py")
        check("a tracked file staged +x commits as a mode-only change", (code, mode(repo, "lib.py")), (0, "100755"))
        write(repo, "retry.sh", "#!/usr/bin/env bash\necho retry\n")
        os.chmod(os.path.join(repo, "retry.sh"), 0o644)
        sh(repo, "add", "--chmod=+x", "retry.sh")
        code, out = run(repo, "bad message.\n", "retry.sh")
        check("a refusal names the +x it cleared and how to stage it again", (code, "git add --chmod=+x -- retry.sh" in out), (1, True))
        sh(repo, "add", "--chmod=+x", "retry.sh")
        code, out = run(repo, "bad message.\n", "retry.sh", os.path.join(scratch, "outside.txt"))
        check("a refusal before staging still names the +x it cleared", (code, "git add --chmod=+x -- retry.sh" in out), (1, True))
        write(repo, "tool.sh", "#!/usr/bin/env bash\necho tool, edited\n")
        code, out = run(repo, "bad message.\n", "tool.sh")
        check("a refusal says nothing of a bit HEAD already holds", (code, "execute bit" in out, mode(repo, "tool.sh")), (1, False, "100755"))
        sh(repo, "config", "core.filemode", "true")

        write(repo, "app.txt", "redacted reviewed version\n")
        redacted = os.path.join(scratch, "redacted.txt")
        write(scratch, "redacted.txt", "the version to commit\n")
        code, out = run(repo, "fix: commit a prepared version\n", f"--from-file=app.txt={redacted}")
        check("--from-file commits that file's content", sh(repo, "show", "HEAD:app.txt"), "the version to commit")
        check("and leaves the disk copy alone", open(os.path.join(repo, "app.txt"), encoding="utf-8").read(), "redacted reviewed version\n")

        reviewed = fresh(scratch, "reviewed")
        write(reviewed, "app.txt", "what the review read\n")
        tree = review_scope.worktree_tree(reviewed)
        review_scope.mark(reviewed, sh(reviewed, "rev-parse", "HEAD"), tree, False)
        write(reviewed, "app.txt", "edited after the review\n")
        code, out = run(reviewed, "feat: commit what was reviewed\n", "--reviewed", "app.txt")
        check("--reviewed commits the reviewed content", (code, sh(reviewed, "show", "HEAD:app.txt")), (0, "what the review read"))
        check("and leaves the later edit on disk for its follow-up", open(os.path.join(reviewed, "app.txt"), encoding="utf-8").read(), "edited after the review\n")

        empty = os.path.join(scratch, "empty")
        subprocess.run(["git", "init", "-q", empty], check=True)
        write(empty, "first.txt", "the very first file\n")
        code, out = run(empty, "chore: start the repo\n", "first.txt")
        check("a repo with no commits gets its root commit", (code, held(empty)), (0, ["first.txt"]))

        globbed = fresh(scratch, "globbed")
        write(globbed, "a[1].txt", "bracketed\n")
        write(globbed, "a1.txt", "plain\n")
        code, out = run(globbed, "feat: add the bracketed file\n", "a[1].txt")
        check("a path with glob characters names only that file", (code, held(globbed)), (0, ["a[1].txt"]))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print("\n".join(failures))
        print(f"commit tests: {len(failures)} failure(s)")
        return 1
    print("commit tests: all cases behave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
