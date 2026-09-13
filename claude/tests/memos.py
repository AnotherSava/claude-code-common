#!/usr/bin/env python3
"""Pin the behaviour of claude/skills/memo/memos.py.

Two silent data-loss bugs shipped here within a day of each other, and neither announced itself:
a close that moved the wrong memo, and a write that landed on an existing file. Both exited 0 and
printed a plausible line. What they have in common is that the filesystem, not this code, decides
which names collide — so the cases worth pinning are the ones where a string comparison and a
directory entry disagree.

  numbering        A number indexes the live newest-first listing, so closing one renumbers the
                   rest. Every identifier in one command is resolved against a single snapshot
                   taken before anything moves; two separate commands are not, and cannot be.
  case folding     NTFS and APFS resolve `Case-Test.md`, `case-test.md` and `Case-Test.MD` to one
                   file. The slug test, the selector and the `.md` extension test all fold, or a
                   generated name reopens a memo that already exists.
  the undo hint    `_move` re-derives the slug against the destination, so the one a memo arrives
                   with is not always the one it ends up under. The hint must name the latter.

The extension case is the one a regression would reach first: `_move` builds its `taken` set from
the destination directory alone, which is only correct while `_load` can see every file in there.
Closing onto an existing mixed-case twin and expecting `-2` is what holds that together.

Memo files are written with explicit `created:` stamps rather than through `add`, because the
stored resolution is one second and the ordering cases would otherwise need a sleep between them.
Commands run as subprocesses against a throwaway git repo, which is how the helper resolves a root.

Pure Python plus `git init`. No network.

Usage:  python claude/tests/memos.py
Exit:   0 all cases behave, 1 at least one does not
"""

import contextlib
import importlib.util
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMOS_PATH = os.path.join(REPO, "claude", "skills", "memo", "memos.py")

# Loaded by path rather than through `sys.path`, as claude/tests/ingress-lint.py loads its target.
# `memos-surface.py` imports `open_memos` from this module instead of re-parsing the tree, so that
# function's contract is this file's to pin alongside the CLI.
_spec = importlib.util.spec_from_file_location("memos", MEMOS_PATH)
memos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(memos)

FAILURES = []


def check(name: str, got, want=True) -> None:
    if got != want:
        FAILURES.append(f"{name}\n    want: {want!r}\n    got:  {got!r}")


class Backlog:
    """A throwaway repo holding a `.claude/memos/` tree, driven through the real CLI."""

    def __init__(self, stack) -> None:
        self.root = stack.enter_context(tempfile.TemporaryDirectory())
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.open_dir = os.path.join(self.root, ".claude", "memos")
        self.done_dir = os.path.join(self.open_dir, "done")
        os.makedirs(self.done_dir)

    def write(self, name: str, title: str, created: str = "2026-09-01 10:00:00", done: bool = False,
              body: str = "PRECIOUS BODY") -> None:
        """Place a memo file directly, so its stamp — and so the listing order — is chosen, not raced."""
        path = os.path.join(self.done_dir if done else self.open_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"---\ncreated: {created}\n---\n\n# {title}\n\n{body}\n")

    def fill(self, count: int, prefix: str = "Memo") -> None:
        """`count` memos, newest first when listed — number n is `<prefix> n`."""
        for i in range(1, count + 1):
            self.write(f"{prefix.lower()}-{i}.md", f"{prefix} {i}", created=f"2026-09-0{i} 10:00:00")

    def run(self, *args: str) -> tuple[int, str, str]:
        proc = subprocess.run([sys.executable, "-S", MEMOS_PATH, *args], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def names(self, done: bool = False) -> list[str]:
        directory = self.done_dir if done else self.open_dir
        return sorted(n for n in os.listdir(directory) if os.path.isfile(os.path.join(directory, n)))

    def titles(self, done: bool = False) -> list[str]:
        out = []
        for name in self.names(done):
            with open(os.path.join(self.done_dir if done else self.open_dir, name), encoding="utf-8") as fh:
                out.extend(line[2:].strip() for line in fh if line.startswith("# "))
        return sorted(out)

    def body(self, name: str, done: bool = False) -> str:
        with open(os.path.join(self.done_dir if done else self.open_dir, name), encoding="utf-8") as fh:
            return fh.read()


def main() -> int:
    with contextlib.ExitStack() as stack:
        # --- one snapshot per command: a close renumbers everything below it ---------------------------
        b = Backlog(stack)
        b.fill(5)
        rc, out, err = b.run("done", "2", "4")
        check("a batch closes what the listing showed", (rc, b.titles(done=True)), (0, ["Memo 2", "Memo 4"]))
        check("and leaves the rest open", b.titles(), ["Memo 1", "Memo 3", "Memo 5"])

        b = Backlog(stack)
        b.fill(5)
        b.run("done", "2")
        rc, out, err = b.run("done", "4")
        # Two commands cannot share a snapshot — pinned so the docs that say so stay honest.
        check("two separate commands resolve against different listings",
              b.titles(done=True), ["Memo 1", "Memo 4"])

        b = Backlog(stack)
        b.fill(3)
        rc, out, err = b.run("done", "1", "1")
        check("the same memo named twice is closed once", (rc, len(b.names(done=True))), (0, 1))
        b = Backlog(stack)
        b.fill(3)
        rc, out, err = b.run("done", "1", "memo-3")
        check("a number and its slug are one memo", (rc, len(b.names(done=True))), (0, 1))

        b = Backlog(stack)
        b.fill(3)
        rc, out, err = b.run("done", "1", "9")
        check("a bad identifier anywhere in a batch moves nothing", (rc, b.names(done=True)), (1, []))
        check("and says which", "no open memo 9" in err)

        # --- case folding: the filesystem decides what collides -----------------------------------------
        b = Backlog(stack)
        b.write("Case-Test.md", "Hand-made stem")
        rc, out, err = b.run("add", "--title", "Case test", "new body")
        check("a stem-case twin is not overwritten by add", "PRECIOUS BODY" in b.body("Case-Test.md"))
        check("the new memo took a free slug", b.names(), ["Case-Test.md", "case-test-2.md"])

        b = Backlog(stack)
        b.write("Case-Test.MD", "Hand-made extension")
        check("an uppercase extension is counted", b.run("count")[1], "1 open · 0 done")
        check("and listed", "Hand-made extension" in b.run("list")[1])
        check("and reachable by slug", "Hand-made extension" in b.run("show", "case-test")[1])
        rc, out, err = b.run("add", "--title", "Case test", "new body")
        check("an extension-case twin is not overwritten by add", "PRECIOUS BODY" in b.body("Case-Test.MD"))
        check("the new memo took a free slug", b.names(), ["Case-Test.MD", "case-test-2.md"])

        # `_move` derives `taken` from the destination only, so this is the case that holds the
        # `.md` extension test in `_load` in place: hide that file and `os.replace` lands on it.
        b = Backlog(stack)
        b.write("Case-Test.MD", "Case test", done=True)
        b.write("open-one.md", "Case test", body="the open one")
        rc, out, err = b.run("done", "1")
        check("closing onto a mixed-case twin in done/ does not overwrite it",
              (rc, "PRECIOUS BODY" in b.body("Case-Test.MD", done=True)), (0, True))
        check("the closed memo took a free slug", b.names(done=True), ["Case-Test.MD", "case-test-2.md"])
        check("and the undo hint names that slug", out.splitlines()[1].endswith("case-test-2"))

        # --- the selector: exact case, then folded, then substring --------------------------------------
        b = Backlog(stack)
        b.write("Alpha.md", "Upper alpha")
        b.write("beta.md", "Lower beta", created="2026-09-02 10:00:00")
        check("an exact-case slug resolves", b.run("path", "Alpha")[1].endswith("Alpha.md"))
        check("a folded slug reaches the same memo", b.run("path", "alpha")[1].endswith("Alpha.md"))
        check("an uppercase key reaches a lowercase slug", "Lower beta" in b.run("show", "BETA")[1])
        rc, out, err = b.run("show", "nothing-like-this")
        check("an unmatched key errors", (rc, "no open memo matching" in err), (1, True))

        # --- commands that act on one memo refuse extras rather than obeying half ------------------------
        b = Backlog(stack)
        b.fill(3)
        for cmd in ("show", "path"):
            rc, out, err = b.run(cmd, "1", "2")
            check(f"`{cmd}` refuses two identifiers", (rc, "not several" in err), (1, True))
        check("`show` still takes one", "Memo 3" in b.run("show", "1")[1])

        # --- drop and reopen take a batch through the same resolver -------------------------------------
        b = Backlog(stack)
        b.fill(5)
        rc, out, err = b.run("drop", "2", "4")
        check("a drop batch removes what the listing showed", b.titles(), ["Memo 1", "Memo 3", "Memo 5"])

        b = Backlog(stack)
        b.fill(3)
        b.run("done", "1", "2", "3")
        rc, out, err = b.run("reopen", "1", "3")
        check("a reopen batch restores two", (rc, len(b.names())), (0, 2))
        check("and prints the slug each landed under", out.count("slug:"), 2)

        # --- the undo hint names where the memo went, not where it came from ----------------------------
        b = Backlog(stack)
        b.write("fix-the-widget.md", "Fix the widget!")
        b.write("fix-the-widget-2.md", "Fix  the   WIDGET???", created="2026-09-02 10:00:00")
        rc, out, err = b.run("done", "1")
        closed, hint = out.splitlines()[0].removeprefix("done: "), out.splitlines()[1].rsplit(" ", 1)[-1]
        check("the printed undo reopens the memo that was closed",
              b.run("reopen", hint)[1].splitlines()[0], f"reopened: {closed}")

        b = Backlog(stack)
        b.write("original-title-here.md", "Completely different wording now")
        rc, out, err = b.run("done", "1")
        hint = out.splitlines()[1].rsplit(" ", 1)[-1]
        check("the undo survives a title edited in place after creation",
              b.run("reopen", hint)[0], 0)

        # --- the shapes the rest of the toolchain depends on --------------------------------------------
        b = Backlog(stack)
        check("an empty backlog says so", b.run("list")[1], "(no open memos)")
        check("count reads both directories", b.run("count")[1], "0 open · 0 done")
        rc, out, err = b.run("done")
        check("an identifier is required", (rc, "number or slug is required" in err), (1, True))

        b = Backlog(stack)
        b.fill(2)
        b.run("done", "1")
        check("prune empties done/", (b.run("prune")[1].splitlines()[0], b.names(done=True)),
              ("pruned 1 done memo", []))

        b = Backlog(stack)
        b.write("visible.md", "Open one")
        b.write("hidden.MD", "Open two, uppercase extension", created="2026-09-02 10:00:00")
        b.write("closed.md", "Closed one", done=True)
        check("open_memos returns only the open half, newest first",
              [m.title for m in memos.open_memos(b.root)],
              ["Open two, uppercase extension", "Open one"])

    if FAILURES:
        print(f"memos tests: {len(FAILURES)} case(s) failed\n")
        for failure in FAILURES:
            print(f"  {failure}\n")
        return 1
    print("memos tests: all cases behave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
