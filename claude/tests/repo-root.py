#!/usr/bin/env python3
"""The shared repo-root resolver every deploy and publish target runs through.

That helper, `claude/skills/shared/repo-root.sh`, replaced two copies of `resolve_repo_dir`
differing only in their comments and in the one filename each hard-coded — one under the deploy
skill anchored on `config/deploy.env`, one under publish anchored on `config/publish.env` — plus an
inline git-top-level lookup in wrap-up's `ship_wrappers.sh`. The anchor became an argument, which
is what lets one function serve all three — and also what makes a caller passing the wrong anchor a
new way to fail that the separate copies made impossible.

Nothing else exercises it. `deploy-dev-server.py` drives one deploy for real and so covers one
caller's happy path from the root; the subdirectory walk, the anchor isolation and both fallbacks
were untested, while a defect in any of them reaches every deploy and publish on the machine.

What is asserted, against scratch trees built per case:

  from-root        a root holding the anchor resolves to itself
  from-subdir      the same root resolves from a subdirectory of it — the 2026-07-12 case, where
                   REPO_DIR came from $PWD, read a nonexistent web/config/deploy.env and fell back
                   to a default port
  nearest-wins     with a nested root, the nearest ancestor holding the anchor wins
  anchor-isolation a publish-only project asked for config/deploy.env does NOT resolve to it; this
                   is the guarantee the two separate copies gave structurally
  multi-anchor     asked for several, a root holding any one of them resolves
  git-fallback     with no anchor above it, a subdirectory of a git repo resolves to its top level
  pwd-fallback     with no anchor and no repo, the answer is $PWD

Paths are compared after realpath on both sides: on macOS the temp root is a symlink
(/var/folders -> /private/var/folders) and `git rev-parse --show-toplevel` resolves it while $PWD
does not, so a raw string comparison fails on a correct answer.

Usage:  python3 claude/tests/repo-root.py
Exit:   0 all hold, 1 one does not or a case could not be set up
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional

HELPER = pathlib.Path(__file__).resolve().parent.parent / "skills" / "shared" / "repo-root.sh"


def resolve(bash: str, cwd: pathlib.Path, anchors: List[str]) -> Optional[str]:
    """Run resolve_repo_dir with the given anchors from cwd; return its realpath, or None on error."""
    args = " ".join(anchors)
    # On Windows the answer comes back as an MSYS path (/c/Users/...), which realpath would read as
    # relative to the current drive; cygpath turns it into the native form the expectations use.
    script = 'source "%s"\nout="$(resolve_repo_dir %s)" || exit 1\nif command -v cygpath >/dev/null; then cygpath -w "$out"; else printf "%%s\\n" "$out"; fi\n' % (HELPER.as_posix(), args)
    proc = subprocess.run([bash, "-c", script], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return os.path.realpath(out) if out else None


def seed(root: pathlib.Path, files: List[str]) -> None:
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")


def git_init(path: pathlib.Path) -> bool:
    proc = subprocess.run(["git", "init", "-q", str(path)], capture_output=True, text=True)
    return proc.returncode == 0


def main() -> int:
    if not HELPER.is_file():
        print("repo-root tests: NOT COVERED — %s is missing" % HELPER)
        return 1
    # A bare "bash" handed to CreateProcess finds System32's WSL launcher before Git Bash on PATH;
    # spawning which()'s result never reaches System32. learnings/windows-spawning-bash.md.
    bash = shutil.which("bash")
    if not bash:
        print("repo-root tests: NOT COVERED — no bash on PATH")
        return 1

    failures = 0
    checked = 0
    uncovered = 0

    def check(name: str, got: Optional[str], want: Optional[str]) -> None:
        nonlocal failures, checked
        checked += 1
        if got == want:
            return
        failures += 1
        print("  FAIL %-16s got %r, want %r" % (name, got, want))

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)

        # from-root, from-subdir, nearest-wins — one tree carrying a nested second root.
        outer = base / "outer"
        inner = outer / "web"
        seed(outer, ["config/deploy.env"])
        (outer / "plain").mkdir(parents=True, exist_ok=True)
        check("from-root", resolve(bash, outer, ["config/deploy.env"]), os.path.realpath(str(outer)))
        check("from-subdir", resolve(bash, outer / "plain", ["config/deploy.env"]), os.path.realpath(str(outer)))
        # Probed one level below the inner root, so the case discriminates: asked from the inner
        # root itself, the $PWD fallback would return it too and a broken anchor match would pass.
        seed(inner, ["config/deploy.env"])
        inner_sub = inner / "src"
        inner_sub.mkdir(parents=True, exist_ok=True)
        check("nearest-wins", resolve(bash, inner_sub, ["config/deploy.env"]), os.path.realpath(str(inner)))

        # anchor-isolation and multi-anchor — a publish-only project.
        #
        # Isolation is probed from a SUBDIRECTORY, not from the root. Run at the root, the $PWD
        # fallback returns that same directory, so a correct refusal and a wrong match are the same
        # string and the case cannot fail. One level down they differ: refusing leaves $PWD, which
        # is the subdirectory, while matching the wrong anchor would name the root.
        pub = base / "publish-only"
        seed(pub, ["config/publish.env", "scripts/publish.sh"])
        pub_sub = pub / "web"
        pub_sub.mkdir(parents=True, exist_ok=True)
        check(
            "anchor-isolation",
            resolve(bash, pub_sub, ["config/deploy.env"]),
            os.path.realpath(str(pub_sub)),
        )
        check(
            "multi-anchor",
            resolve(bash, pub_sub, ["config/deploy.env", "config/publish.env"]),
            os.path.realpath(str(pub)),
        )

        # git-fallback — a repo with no anchor anywhere above the cwd.
        repo = base / "bare-repo"
        (repo / "sub").mkdir(parents=True, exist_ok=True)
        if git_init(repo):
            check("git-fallback", resolve(bash, repo / "sub", ["config/deploy.env"]), os.path.realpath(str(repo)))
        else:
            uncovered += 1
            print("  NOT COVERED git-fallback — git init failed in the scratch tree")

        # pwd-fallback — no anchor and no repository. Only meaningful where the scratch tree is
        # genuinely outside one, so the precondition is probed rather than assumed.
        lone = base / "lone"
        lone.mkdir(parents=True, exist_ok=True)
        probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(lone), capture_output=True, text=True
        )
        if probe.returncode != 0:
            check("pwd-fallback", resolve(bash, lone, ["config/deploy.env"]), os.path.realpath(str(lone)))
        else:
            uncovered += 1
            print("  NOT COVERED pwd-fallback — the scratch tree sits inside a git repository")

    tail = "" if uncovered == 0 else ", %d NOT COVERED" % uncovered
    if failures:
        print("repo-root tests: %d of %d case(s) failed%s" % (failures, checked, tail))
        return 1
    print("repo-root tests: %d case(s) behave%s" % (checked, tail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
