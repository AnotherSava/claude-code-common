#!/usr/bin/env python3
"""Cases for `claude/skills/shared/push.py`, the push every skill pushing the default branch makes.

Its costly failures are a push that goes out over a failing gate, and a report that leaves out what follows a push:
the bookmark's state, or a CI line where CI exists. The pushed-to URL cases call the parser directly on a sample of
git's porcelain output. Every other case runs against a real clone of a bare origin, sealed from this machine's git
config, with a stub gate and the dashboard pointed at a port nothing listens on, so no peer is ever messaged.
The fork case stubs `gh` on PATH, which Windows cannot run, so there it is reported NOT COVERED.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from git_scratch import check, commit, report, seal, sh, uncovered, write

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "shared", "push.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

from push import _pushed_to  # noqa: E402 — needs the sys.path line above

STUB_GATE = """#!/usr/bin/env bash
case "${GATE_MODE:-pass}" in fail) exit 3 ;; esac
exit 0
"""

def run(repo: str, mode: str = "pass") -> tuple[int, list[str]]:
    env = {**os.environ, "GATE_MODE": mode}
    done = subprocess.run([sys.executable, SCRIPT, "--caller", "yolo", "--repo", repo], capture_output=True, text=True, timeout=180, env=env)
    return done.returncode, [line for line in done.stdout.splitlines() if line.strip()]


def clone(scratch: str, name: str, push_first: bool = True) -> tuple[str, str]:
    origin = os.path.join(scratch, f"{name}.git")
    repo = os.path.join(scratch, name)
    subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
    subprocess.run(["git", "clone", "-q", origin, repo], check=True, capture_output=True)
    write(repo, ".claude/commit-checks.sh", STUB_GATE)
    commit(repo, "app.txt", "one\n")
    if push_first:
        sh(repo, "push", "-q", "-u", "origin", "HEAD")
    return origin, repo


def main() -> int:
    # Git prints an scp-style remote without its user, a form `gh --repo` answers with 404, so it must become ssh://.
    for to, want in (("github.com:Owner/repo.git", "ssh://github.com/Owner/repo.git"),
                     ("https://github.com/Owner/repo.git", "https://github.com/Owner/repo.git"),
                     ("/tmp/scratch/fork.git", "/tmp/scratch/fork.git"),
                     ("C:/work/fork.git", "C:/work/fork.git")):
        check(f"the pushed-to URL {to} reaches gh as {want}", _pushed_to(f"To {to}\n=\trefs/heads/main:refs/heads/main\t[up to date]\nDone\n"), want)

    scratch = tempfile.mkdtemp(prefix="push-test-")
    try:
        seal(scratch, "[push]\n\tdefault = current\n")
        os.environ.update({"TAURI_DASHBOARD_URL": "http://127.0.0.1:9"})

        origin, repo = clone(scratch, "gated")
        commit(repo, "app.txt", "two\n")
        before = sh(origin, "rev-parse", "main")
        code, lines = run(repo, "fail")
        check("a failing gate refuses", (code, any(line.startswith("NOT PUSHED") for line in lines)), (1, True))
        check("and nothing reaches origin", sh(origin, "rev-parse", "main"), before)

        code, lines = run(repo)
        check("a passing gate pushes", (code, sh(origin, "rev-parse", "main")), (0, sh(repo, "rev-parse", "HEAD")))
        check("the bookmark status is the last line", lines[-1].startswith("review bookmark:") if lines else False, True)
        check("the peer notice is reported", any(line.startswith("peer-pull:") for line in lines), True)
        check("a repo without workflows says nothing about CI", [line for line in lines if line.startswith("ci:")], [])
        code, lines = run(repo)
        check("a push that moves nothing asks no peer to pull", (code, [line for line in lines if line.startswith("peer-pull:")]), (0, ["peer-pull: not sent — the push moved nothing, so there is nothing to pull"]))

        origin, fresh = clone(scratch, "first", push_first=False)
        code, lines = run(fresh)
        check("a first push sets up tracking", (code, sh(fresh, "rev-parse", "--abbrev-ref", "@{upstream}")), (0, "origin/main"))
        check("and reports the remote as none before it", any(line.startswith("pushed: none..") for line in lines), True)

        origin, ci = clone(scratch, "ci")
        commit(ci, ".github/workflows/build.yml", "on: push\n")
        code, lines = run(ci)
        check("a repo with workflows gets a CI line", (code, any(line.startswith("ci:") for line in lines)), (0, True))

        # A fork: gh defaults to `upstream` when that remote exists, so the CI lookup has to name the remote pushed to.
        # Windows' CreateProcess resolves a bare `gh` to gh.exe only, so the extension-less stub cannot run there.
        if os.name == "nt":
            uncovered.append("the fork's gh argv: a PATH stub for `gh` cannot run on Windows")
        else:
            origin, fork = clone(scratch, "fork")
            subprocess.run(["git", "init", "-q", "--bare", os.path.join(scratch, "third-party.git")], check=True)
            sh(fork, "remote", "add", "upstream", os.path.join(scratch, "third-party.git"))
            commit(fork, ".github/workflows/build.yml", "on: push\n")
            stubs, argv = os.path.join(scratch, "bin"), os.path.join(scratch, "gh-argv")
            write(stubs, "gh", f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{argv}"\necho "[]"\n')
            os.chmod(os.path.join(stubs, "gh"), 0o755)
            saved_path = os.environ["PATH"]
            os.environ["PATH"] = stubs + os.pathsep + saved_path
            try:
                code, lines = run(fork)
            finally:
                os.environ["PATH"] = saved_path
            with open(argv) as f:
                args = f.read().split("\n")
            named = args[args.index("--repo") + 1] if "--repo" in args else None
            check("in a fork the CI lookup names the remote the push went to", (code, named), (0, origin))
            check("and so does the re-query it prints", any(f"--repo {origin}" in line for line in lines if line.startswith("ci:")), True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    return report("push tests")


if __name__ == "__main__":
    sys.exit(main())
