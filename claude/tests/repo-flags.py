#!/usr/bin/env python3
"""Cases for `claude/skills/shared/repo_flags.py` and the release check that reads it.

A flag the reader gets wrong fails silently in the direction the repo asked to avoid: a misspelt key read as unset
brings back the offer it was written to stop. So the cases lean on refusals, and on the one consumer that is a
script rather than prose, `wrap-up/scripts/release_candidates.sh`, run for real against a scratch repo.

  unset        a repo with no file, and a key the file does not name, read as empty
  set          `set` writes a new key, replaces it in place, and keeps comments and other keys
  refusals     an unknown key, a value other than yes or no, a repeated key and a line that is not KEY=value
               each exit 2 naming the line, on `get` and before `set` writes anything
  ignored      `set` refuses, naming the rule, when git would never stage the file, and writes nothing
  release-off  RELEASES=no makes the release check report `off` and look at no tag
  release-ask  an unset RELEASES prints the `flag: RELEASES unset` line /wrap-up asks on, and RELEASES=yes leaves it out
  release-bad  a refused file stops the release check with exit 1 and the reader's message
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from git_scratch import check, find_bash, report, seal, sh, write

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLAGS = os.path.join(ROOT, "claude", "skills", "shared", "repo_flags.py")
RELEASE = os.path.join(ROOT, "claude", "skills", "wrap-up", "scripts", "release_candidates.sh")


def flags(root: str, *args: str) -> tuple[int, str, str]:
    done = subprocess.run([sys.executable, FLAGS, *args[:1], root, *args[1:]], capture_output=True, text=True, timeout=30)
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def contents(root: str) -> str:
    with open(os.path.join(root, ".claude", "repo-flags"), encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    bash = find_bash("repo-flags tests")
    if not bash:
        return 1
    with tempfile.TemporaryDirectory(prefix="repo-flags-test-") as scratch:
        seal(scratch)
        root = os.path.join(scratch, "plain")
        os.makedirs(root)
        check("no file reads as unset", flags(root, "get", "RELEASES"), (0, "", ""))

        check("set writes a new key", flags(root, "set", "RELEASES", "no")[0], 0)
        check("and get reads it back", flags(root, "get", "RELEASES"), (0, "no", ""))
        check("a key the file does not name reads as unset", flags(root, "get", "SCREENSHOTS"), (0, "", ""))

        write(root, ".claude/repo-flags", "# why: a fork\nRELEASES=no  # upstream tags\nSCREENSHOTS=yes\n")
        flags(root, "set", "RELEASES", "yes")
        check("set replaces the key in place and keeps the rest", contents(root), "# why: a fork\nRELEASES=yes\nSCREENSHOTS=yes\n")

        for label, text, needle in [
            ("an unknown key", "RELEASE=no\n", "unknown key RELEASE"),
            ("a value other than yes or no", "RELEASES=false\n", "neither yes nor no"),
            ("a repeated key", "RELEASES=no\nRELEASES=yes\n", "set a second time"),
            ("a line that is not KEY=value", "releases no\n", "is not KEY=value"),
        ]:
            write(root, ".claude/repo-flags", text)
            code, out, err = flags(root, "get", "SCREENSHOTS")
            check(f"{label} refuses get", (code, out, needle in err and ".claude/repo-flags:" in err), (2, "", True))
            check(f"{label} refuses set and writes nothing", (flags(root, "set", "SCREENSHOTS", "no")[0], contents(root)), (2, text))
        check("an unknown key argument is refused", flags(root, "get", "PUBLISH")[0], 2)

        hidden = os.path.join(scratch, "hidden")
        subprocess.run(["git", "init", "-q", hidden], check=True)
        write(hidden, ".gitignore", "!.claude/\n.claude/*\n!.claude/settings.json\n")
        code, out, err = flags(hidden, "set", "RELEASES", "no")
        written = os.path.exists(os.path.join(hidden, ".claude", "repo-flags"))
        check("set refuses a flags file git ignores, naming the rule, and writes nothing",
              (code, ".gitignore:2:.claude/*" in err, written), (2, True, False))
        write(hidden, ".gitignore", "!.claude/\n.claude/*\n!.claude/repo-flags\n")
        check("and writes once the allowlist names it", flags(hidden, "set", "RELEASES", "no")[0], 0)

        repo = os.path.join(scratch, "repo")
        subprocess.run(["git", "init", "-q", repo], check=True)
        write(repo, "app.py", "one\n")
        sh(repo, "add", "-A")
        sh(repo, "commit", "-qm", "first")
        sh(repo, "tag", "v1.0.0")
        write(repo, "app.py", "two\n")
        sh(repo, "commit", "-qam", "feat: something users see")

        def release() -> tuple[int, str]:
            done = subprocess.run([bash, RELEASE.replace(os.sep, "/")], cwd=repo, capture_output=True, text=True, timeout=60)
            return done.returncode, (done.stdout + done.stderr).strip()

        code, out = release()
        check("with no flag the release check counts the feat commit", (code, "1 feat/fix commits since" in out), (0, True))
        check("and reports the flag as unset", "flag: RELEASES unset" in out, True)
        write(repo, ".claude/repo-flags", "RELEASES=yes\n")
        code, out = release()
        check("RELEASES=yes counts the commit and leaves the unset line out",
              (code, "1 feat/fix commits since" in out, "flag: RELEASES unset" in out), (0, True, False))
        write(repo, ".claude/repo-flags", "RELEASES=no\n")
        check("RELEASES=no turns the release check off", release(), (0, "release: off (RELEASES=no in .claude/repo-flags)"))
        write(repo, ".claude/repo-flags", "RELEASES=nope\n")
        code, out = release()
        check("a refused file stops the release check", (code, "neither yes nor no" in out, "release: v1.0.0" in out), (1, True, False))

    return report("repo-flags tests")


if __name__ == "__main__":
    sys.exit(main())
