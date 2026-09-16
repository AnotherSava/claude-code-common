#!/usr/bin/env python3
"""The authoring gate for the conventions: what has to hold before the fleet runs any of this.

    python claude/conventions/tests.py

Run from this repo's `.claude/commit-checks.sh`, because a defect here ships outward rather than
staying put: a version whose README is missing a section is a migration `/adopt` walks in every
repo, and a rule that returns a clean list for a tree it should have refused stands in front of
every one of those repos' commits saying nothing.

Three things are asserted, and the third is the one worth the seconds it takes.

**The version set.** Every folder parses, the numbers are unique and contiguous from 1, the folder
name and the number agree, and every README carries the four mandatory sections in order. Then the
wiring between the two halves: a name in a `rules:` field with no file behind it, and a rule file no
version names, are each a rule nobody runs.

**Every rule against a tree built here.** A conforming tree and a violating one per rule, each built
in a temp directory by the test itself and removed afterwards — `git init` where the rule asks git
what it hides. Committed fixture trees are deliberately absent: a tree that is deliberately broken
has to be excluded from every other check in this repo by name, and the exclusion is what goes
stale. Both halves are needed. A rule that returns `[]` for everything passes the conforming tree,
and a rule that flags everything passes the violating one.

**That a rule which could not look raises.** Each rule is also pointed at a tree where its question
has no answer — outside a work tree for the ones that ask git, holding a file that will not read for
the ones that do not — and it has to raise there rather than return an empty list. That empty list
is what the checker would print as a pass.

An assertion this run could not reach prints as NOT COVERED and is counted nowhere: a gate that
cannot tell "checked and clean" from "never ran" turns an open problem into a closed-looking one.

Exit codes: 0 every assertion held · 1 one failed, or the version set would not load.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

# Set before the first local import. A compiled copy left beside a rule outlives the source it was
# built from, and this gate runs inside the dotfiles checkout, which it must leave exactly as it
# found it (learnings/python-stale-bytecode-cache.md).
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)

import check  # noqa: E402 — needs the sys.path line above
import engine  # noqa: E402 — likewise

RULES_DIR = os.path.join(HERE, "rules")
# The four mandatory `##` sections of a version README, in the order they are written in.
SECTIONS = ("What changed", "Migrating an existing repo", "When it does not apply", "Continuing rule")
GIT_TIMEOUT = 60


class Tree(NamedTuple):
    """One temp tree a rule is pointed at."""

    files: dict[str, bytes | str]  # repo-relative, forward slashes
    dirs: tuple[str, ...] = ()     # directories with nothing in them the rule still has to see
    repo: bool = True              # git init here — false is how a rule's git call is made unanswerable
    committed: bool = False        # add and commit, for a rule that asks git what this repo tracks


class Case(NamedTuple):
    """A rule, a tree it must pass, a tree it must fail, and a tree it must refuse to judge."""

    rule: str
    conforming: Tree
    violating: Tree
    unanswerable: Tree
    why: str  # what the third tree takes away, in the words the assertion is printed with


# One case per rule. Each tree is the smallest shape that reaches the rule's own question: a
# conforming one that must come back empty, a violating one that must not, and one where the answer
# cannot be established at all. The last is a directory outside any work tree wherever the rule asks
# git something, since that is the failure the checker reports as unmeasured; where a rule asks git
# nothing, it is a file that is there and will not read, which is the same fact by the other route.
CASES = (
    Case(
        "gitignore-unhides-committed",
        Tree({".gitignore": "/dist/\n/tmp/\n", ".claude/settings.json": "{}\n",
              ".claude/memos/one.md": "a memo\n", ".claude/memory/MEMORY.md": "# Memory index\n"}),
        Tree({".gitignore": ".claude/memos/\n", ".claude/memos/one.md": "a memo\n"}),
        Tree({".gitignore": "/dist/\n"}, repo=False),
        "it is outside a work tree, so git will not say what is hidden here",
    ),
    Case(
        "gitignore-scope-global",
        Tree({".gitignore": "/dist/\n/node_modules/\n"}, committed=True),
        Tree({".gitignore": ".idea/\n"}, committed=True),
        Tree({".gitignore": ".idea/\n"}, repo=False),
        "it is outside a work tree, so git will not say which .gitignore files this repo commits",
    ),
    Case(
        "memory-file-shape",
        Tree({".claude/memory/project_thing.md": "---\ntitle: A thing\n---\n\nThe thing.\n",
              ".claude/memory/MEMORY.md": "# Memory index\n\n- [A thing](project_thing.md) — what it says\n"}),
        Tree({".claude/memory/project_thing.md": "# no frontmatter block\n"}),
        # Not valid UTF-8 in either direction, so the file is there and its opening line is unknown.
        Tree({".claude/memory/project_thing.md": b"\xff\xfe\x00\x41 not text\n"}),
        "a memory file is there and will not read as text",
    ),
    Case(
        "transcrypt-eol",
        Tree({".gitattributes": "config/publish.env filter=crypt diff=crypt merge=crypt text=auto eol=lf\n"}),
        Tree({".gitattributes": "config/publish.env filter=crypt diff=crypt merge=crypt\n"}),
        Tree({".gitattributes": "config/publish.env filter=crypt diff=crypt merge=crypt text=auto eol=lf\n"},
             repo=False),
        "it is outside a work tree, so git will not say what these rules resolve to",
    ),
    Case(
        "node-engines",
        Tree({"package.json": '{"name": "x", "engines": {"node": ">=24"}}\n', ".nvmrc": "24\n"}),
        Tree({"package.json": '{"name": "x"}\n', ".nvmrc": "24\n"}),
        Tree({"package.json": '{"name": "x", "engines": {"node": ">=24"}}\n', ".nvmrc": "24\n"}, repo=False),
        "it is outside a work tree, so git will not say which manifests it hides",
    ),
    Case(
        "engine-strict",
        Tree({"package.json": '{"name": "x", "engines": {"node": ">=24"}}\n', ".npmrc": "engine-strict=true\n"}),
        Tree({"package.json": '{"name": "x", "engines": {"node": ">=24"}}\n'}),
        Tree({"package.json": '{"name": "x", "engines": {"node": ">=24"}}\n', ".npmrc": "engine-strict=true\n"},
             repo=False),
        "it is outside a work tree, so git will not say which manifests it hides",
    ),
    Case(
        "package-manager-pin",
        Tree({"package.json": '{"name": "x", "packageManager": "npm@11.17.0"}\n'}),
        Tree({"package.json": '{"name": "x"}\n'}),
        Tree({"package.json": '{"name": "x", "packageManager": "npm@11.17.0"}\n'}, repo=False),
        "it is outside a work tree, so git will not say which manifests it hides",
    ),
    Case(
        "docs-theme-pinned",
        Tree({"docs/_config.yml": "title: Docs\nremote_theme: just-the-docs/just-the-docs@v0.10.1\n"
                                 "plugins:\n  - jekyll-remote-theme\n",
              "docs/index.md": "# Docs\n", "docs/pages/one.md": "# One\n"}),
        Tree({"docs/_config.yml": "title: Docs\nremote_theme: just-the-docs/just-the-docs\n"
                                 "plugins:\n  - jekyll-remote-theme\n",
              "docs/index.md": "# Docs\n", "docs/pages/one.md": "# One\n"}),
        Tree({"docs/_config.yml": b"title: \xff\xfe not text\n", "docs/index.md": "# Docs\n",
              "docs/pages/one.md": "# One\n"}),
        "the config is there and will not read as text",
    ),
    Case(
        "cotenant-service-names",
        Tree({"compose.yml": "name: scheduler\nservices:\n  scheduler-app:\n"
                             "    container_name: scheduler-app\n    image: scheduler:latest\n"}),
        Tree({"compose.yml": "name: scheduler\nservices:\n  app:\n    image: scheduler:latest\n"}),
        # No top-level `name:`, so the prefix every service should carry has no value to check
        # against — the rule refuses rather than judging the keys against a project name it guessed.
        Tree({"compose.yml": "services:\n  scheduler-app:\n    container_name: scheduler-app\n"}),
        "the compose file names no project, so there is no prefix to check a service key against",
    ),
)


# ---------------------------------------------------------------- printing


def indent(text: str) -> str:
    return "\n".join(f"        {line}" for line in text.splitlines())


class Gate:
    """Every assertion this run made, and every one it could not reach."""

    def __init__(self) -> None:
        self.results: list[bool] = []
        self.uncovered: list[str] = []

    def ok(self, passed: bool, label: str, detail: str = "") -> bool:
        self.results.append(passed)
        print(f"  {'ok  ' if passed else 'FAIL'}  {label}")
        if not passed and detail:
            print(indent(detail))
        return passed

    def not_covered(self, label: str, why: str) -> None:
        """An assertion that did not run, counted nowhere.

        Adding an `ok` here would be the failure this whole file exists to prevent, one level up: a
        gate that cannot tell a rule it exercised from one it never reached reports the second as
        the first, and the problem closes without anybody looking at it.
        """
        self.uncovered.append(label)
        print(f"  ----  {label} NOT COVERED: {why}")


# ---------------------------------------------------------------- scratch trees


def run_git(root: str, argv: list[str]) -> tuple[int, str]:
    """One git command in a scratch tree. A failure to start git comes back as a code, not a raise.

    The flags are what makes a scratch repo this test's own rather than this machine's: no signing
    key, an identity that does not depend on the global config `sandbox_git` has already taken away,
    and a hooks path pointing at nothing, so the user's own pre-commit hook cannot reach into a tree
    built here.
    """
    command = ["git", "-C", root, "-c", "commit.gpgsign=false", "-c", "user.name=conventions tests",
               "-c", "user.email=tests@localhost", "-c", f"core.hooksPath={os.path.join(root, 'no-hooks')}",
               *argv]
    try:
        done = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace",
                              timeout=GIT_TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return 1, f"git {argv[0]} could not be run ({exc})"
    return done.returncode, (done.stderr or done.stdout or "").strip()


def write_file(root: str, rel: str, body: bytes | str) -> None:
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    if isinstance(body, bytes):
        with open(path, "wb") as handle:
            handle.write(body)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)


def build(base: str, name: str, tree: Tree) -> tuple[str, str]:
    """Write one tree under `base`. -> (its path, "" or why it could not be built)"""
    root = os.path.join(base, name)
    os.makedirs(root, exist_ok=True)
    for rel, body in tree.files.items():
        write_file(root, rel, body)
    for rel in tree.dirs:
        os.makedirs(os.path.join(root, *rel.split("/")), exist_ok=True)
    if not tree.repo:
        return root, ""
    steps = [["init", "-q", "-b", "main"]]
    if tree.committed:
        steps += [["add", "-A"], ["commit", "-q", "--no-verify", "-m", "tree"]]
    for argv in steps:
        code, output = run_git(root, argv)
        if code != 0:
            return root, f"git {argv[0]} exited {code}: {output}"
    return root, ""


def remove_tree(path: str) -> None:
    """Remove a scratch tree, including the read-only files `git init` leaves in it.

    Loose objects are written mode 444, which on Windows is the read-only attribute and makes the
    delete refuse; `ignore_errors=True` alone would then leave a whole `.git` in the temp directory
    once per tree per run, silently.
    """
    for base, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(base, name), 0o700)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def sandbox_git(base: str) -> dict[str, str | None]:
    """Point git's global and system config at this run's own files. -> what was there before.

    Two rules read a machine rather than a repo — `gitignore-scope-global` compares against the
    global excludes file, and every `check-ignore` call consults it — so without this the answers
    depend on whose machine the gate runs on, and the one repo whose `.gitignore` happens to repeat a
    line of the user's own global file would decide whether this passes. The global file written here
    carries two entries, which is what the violating tree for that rule is built to duplicate.
    """
    config, excludes = os.path.join(base, "gitconfig"), os.path.join(base, "global-excludes")
    # Forward slashes: a backslash opens an escape inside a git config value, so a Windows path
    # written literally here resolves to a file name nothing on disk has.
    with open(config, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("[core]\n\texcludesfile = " + excludes.replace("\\", "/") + "\n")
    with open(excludes, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(".idea/\nThumbs.db\n")
    before = {name: os.environ.get(name) for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
    os.environ["GIT_CONFIG_GLOBAL"] = config
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    return before


def restore_env(before: dict[str, str | None]) -> None:
    for name, value in before.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


# ---------------------------------------------------------------- the version set


def headings(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return [line.strip()[3:].strip() for line in handle if line.startswith("## ")]


def in_order(present: list[str], wanted: tuple[str, ...]) -> bool:
    """Do all of `wanted` appear in `present`, in this order, allowing anything between them."""
    rest = list(present)
    for heading in wanted:
        if heading not in rest:
            return False
        rest = rest[rest.index(heading) + 1:]
    return True


def version_shape(gate: Gate, versions: list[engine.Version]) -> None:
    """Every version folder parses, and its name, its number and its prose agree."""
    print("\nthe version set")
    numbers = [version.number for version in versions]
    gate.ok(bool(versions), f"the versions directory holds at least one version (found {len(versions)})")
    gate.ok(numbers == sorted(set(numbers)) == list(range(1, len(numbers) + 1)),
            f"version numbers are unique and contiguous from 1 (found {numbers})")
    for version in versions:
        name = os.path.basename(version.folder)
        gate.ok(name == f"{version.number:03d}-{version.slug}",
                f"v{version.number} {version.slug}: the folder name is its number zero-padded and its slug",
                f"the folder is named {name}")
        try:
            present = headings(version.readme)
        except (OSError, UnicodeDecodeError) as exc:
            gate.ok(False, f"v{version.number} {version.slug}: README.md carries the four sections", str(exc))
            continue
        missing = [heading for heading in SECTIONS if heading not in present]
        gate.ok(not missing and in_order(present, SECTIONS),
                f"v{version.number} {version.slug}: README.md carries the four sections, in order",
                f"missing: {', '.join(missing)}" if missing else f"out of order: {', '.join(present)}")


def rule_wiring(gate: Gate, versions: list[engine.Version]) -> None:
    """A rule and the version that introduced it each know about the other.

    Both directions, because each one alone is a rule nobody runs: a name in a `rules:` field with no
    file behind it is a version the checker cannot honour, and a file no version names is a rule no
    repo is ever entitled to — dead code wearing the shape of an enforcement.
    """
    print("\nrules and the versions that introduce them")
    try:
        files = {name[:-3] for name in os.listdir(RULES_DIR)
                 if name.endswith(".py") and not name.startswith("_")}
    except OSError as exc:
        gate.ok(False, "the rules directory lists", str(exc))
        return
    named = {name: version.number for version in versions for name in version.rules}
    for name in sorted(named):
        gate.ok(name in files, f"{name} is named by v{named[name]} and rules/{name}.py exists")
    for name in sorted(files - set(named)):
        gate.ok(False, f"rules/{name}.py is named by some version",
                "no version declares it under `rules:`, so no repo ever runs it and the checker "
                "cannot say which adopted number would entitle one to")
    introduced = check.rule_versions()
    gate.ok(introduced == named,
            "the checker derives the same rule-to-version mapping from the same frontmatter",
            f"the checker reads {introduced}, the version set says {named}")


# ---------------------------------------------------------------- the rules


def rule_behaviour(gate: Gate, base: str, outside_repo: bool) -> None:
    """Each rule against a conforming tree, a violating one, and one it cannot judge at all."""
    print("\nevery rule against a tree built here")
    introduced = check.rule_versions()
    covered = {case.rule for case in CASES}
    for name in sorted(introduced):
        if name not in covered:
            gate.not_covered(f"{name} is exercised against a tree",
                             "no case in this file builds a tree for it, so nothing here has run it")
    for case in CASES:
        if case.rule not in introduced:
            gate.ok(False, f"{case.rule} is a rule some version introduces",
                    "this file builds trees for a rule the version set does not name")
            continue
        for label, tree, expect in (("conforming", case.conforming, True), ("violating", case.violating, False)):
            root, failure = build(base, f"{case.rule}-{label}", tree)
            if failure:
                gate.ok(False, f"{case.rule}: the {label} tree is built", failure)
                continue
            try:
                found = check.run(case.rule, root)
            except Exception as exc:
                gate.ok(False, f"{case.rule} answers on the {label} tree", f"{type(exc).__name__}: {exc}")
                continue
            if expect:
                gate.ok(not found, f"{case.rule} returns [] on a tree that conforms",
                        "reported instead:\n" + "\n".join(found))
            else:
                gate.ok(bool(found), f"{case.rule} reports a tree that does not conform",
                        "returned [], and a rule that cannot tell a broken tree from a sound one "
                        "passes every repo it will ever run in")
        if not tree_answerable(case, outside_repo):
            gate.not_covered(f"{case.rule} raises rather than passing when {case.why}",
                             "this run's temp directory sits inside a git work tree, so a tree built "
                             "there is not outside one")
            continue
        root, failure = build(base, f"{case.rule}-unanswerable", case.unanswerable)
        if failure:
            gate.ok(False, f"{case.rule}: the unanswerable tree is built", failure)
            continue
        try:
            found = check.run(case.rule, root)
        except Exception:
            gate.ok(True, f"{case.rule} raises rather than passing when {case.why}")
            continue
        gate.ok(False, f"{case.rule} raises rather than passing when {case.why}",
                f"returned {found!r} instead, and the checker prints an empty list as a rule that held")


def tree_answerable(case: Case, outside_repo: bool) -> bool:
    """Whether this run can build the tree that takes the rule's answer away.

    A case whose unanswerable tree is a plain directory only works where the temp directory is not
    itself inside a checkout — a `git init`-less tree under one answers with that repo's rules.
    """
    return outside_repo or case.unanswerable.repo


# ---------------------------------------------------------------- the record


def record_line(root: str) -> str:
    with open(os.path.join(root, ".claude", "conventions"), encoding="utf-8-sig") as handle:
        return handle.read()


def refuses(root: str, number: int) -> str:
    """The sentence `write_record` refuses with, or "" when it wrote instead."""
    try:
        engine.write_record(root, number)
    except (engine.RecordError, engine.VersionError) as exc:
        return str(exc)
    return ""


def walk_to(root: str, number: int) -> str:
    """Advance a scratch repo's record to `number`. -> "" or the first refusal on the way.

    One version at a time, because that is the only way the engine will move it: a test that wrote
    the end number directly would be asserting against a path `/adopt` never takes.
    """
    for step in range(1, number + 1):
        refused = refuses(root, step)
        if refused:
            return refused
    return ""


def record_round_trip(gate: Gate, base: str, versions: list[engine.Version]) -> None:
    """The record is written, read back, and refuses every number that would make it a lie."""
    print("\nthe record")
    newest = versions[-1].number
    root, failure = build(base, "record", Tree({"README.md": "a repo\n"}))
    if failure:
        gate.ok(False, "a scratch repo for the record is built", failure)
        return
    gate.ok(engine.read_record(root).present is False and engine.adopted(root) == 0,
            "a repo with no record file reads as never asked, at 0")
    gate.ok(bool(refuses(root, 2)), "it refuses to skip from 0 to 2")
    gate.ok(bool(refuses(root, newest + 1)), f"it refuses v{newest + 1}, above the newest version here")
    gate.ok(not refuses(root, 1), "it writes v1")
    gate.ok(engine.adopted(root) == 1, "and reads v1 back")
    gate.ok(record_line(root).endswith("\n1\n"), "the file ends with its one content line and a newline",
            repr(record_line(root)))
    gate.ok(bool(refuses(root, 1)), "it refuses to write v1 again")
    gate.ok(not refuses(root, 2) and engine.adopted(root) == 2, "it writes v2")
    gate.ok(bool(refuses(root, 1)), "and then refuses to lower the number back to v1")

    machine = next((version for version in versions if version.scope == "machine"), None)
    if machine is None:
        gate.not_covered("a machine-scoped version writes the local record too",
                         "no version in this checkout declares scope: machine")
    else:
        walked, failure = build(base, "record-machine", Tree({"README.md": "a repo\n"}))
        refused = "" if failure else walk_to(walked, machine.number)
        local = os.path.join(walked, ".claude", "conventions.local")
        gate.ok(not failure and not refused and os.path.isfile(local),
                f"walking to v{machine.number} ({machine.slug}, scope machine) writes the local record too",
                failure or refused or f"{local} was not written")
        gate.ok(engine.read_record(walked).local == machine.number,
                f"and the local record reads v{machine.number}")

    exempt, failure = build(base, "record-exempt", Tree(
        {".claude/conventions": "# a comment\nexempt a clone of someone else's project\n"}))
    if failure:
        gate.ok(False, "a scratch repo for the exempt record is built", failure)
    else:
        record = engine.read_record(exempt)
        gate.ok(record.exempt == "a clone of someone else's project" and engine.pending(exempt) == [],
                "an exempt record is read as its reason, and nothing is pending there", repr(record))

    broken, failure = build(base, "record-broken", Tree({".claude/conventions": "# a comment\nbanana\n"}))
    if failure:
        gate.ok(False, "a scratch repo for the unreadable record is built", failure)
        return
    gate.ok(bool(engine.read_record(broken).error), "a record line that is neither a number nor exempt is an error")
    try:
        engine.adopted(broken)
        gate.ok(False, "reading it raises rather than answering 0",
                "0 would send a walk back to the first version in a repo that may have run all of them")
    except engine.RecordError:
        gate.ok(True, "reading it raises rather than answering 0")


def behind_for_cases(gate: Gate, base: str, versions: list[engine.Version]) -> None:
    """The `behind_for` answer waves a tool through wherever this system does not govern the repo."""
    print("\nbehind_for")
    tools = sorted({tool for version in versions for tool in version.affects})
    if not tools:
        # Every answer below would be None whatever the repo, since a tool no version names is one
        # nothing can be behind for — so the four cases would pass without distinguishing anything.
        gate.not_covered("behind_for answers None where this system does not govern the repo, and a "
                         "pair of numbers where it does",
                         "no version declares an `affects:` tool, so there is nothing to be behind for")
        return
    tool = tools[0]
    plain = os.path.join(base, "behind-nonrepo")
    os.makedirs(plain, exist_ok=True)
    gate.ok(engine.behind_for(plain, tool) is None, "None for a directory that is not a git repo")

    other, failure = build(base, "behind-third-party", Tree({"README.md": "someone else's\n"}))
    code, output = run_git(other, ["remote", "add", "origin", "https://github.com/someone-else/thing.git"])
    if failure or code != 0:
        gate.ok(False, "a scratch repo with a third-party origin is built", failure or output)
    else:
        gate.ok(engine.is_third_party(other) == "someone-else", "a third-party origin is read as its owner",
                repr(engine.is_third_party(other)))
        gate.ok(engine.behind_for(other, tool) is None, "None for a repo whose origin belongs to someone else")

    exempt, failure = build(base, "behind-exempt", Tree(
        {".claude/conventions": "exempt a clone of someone else's project\n"}))
    if failure:
        gate.ok(False, "a scratch repo with an exempt record is built", failure)
    else:
        gate.ok(engine.behind_for(exempt, tool) is None, "None for an exempt record")

    required = max(version.number for version in versions if tool in version.affects)
    behind, failure = build(base, "behind-repo", Tree({"README.md": "a repo\n"}))
    if failure:
        gate.ok(False, "a scratch repo for the positive answer is built", failure)
        return
    answer = engine.behind_for(behind, tool)
    gate.ok(answer is not None and answer[:2] == (0, required),
            f"(0, v{required}, title) for a repo at 0 whose stored {tool} data v{required} reshapes", repr(answer))
    refused = walk_to(behind, required)
    gate.ok(not refused and engine.behind_for(behind, tool) is None,
            f"and None once that repo has adopted v{required}", refused)


# ---------------------------------------------------------------- dispatch


def report(gate: Gate) -> int:
    failed = gate.results.count(False)
    # The tally is the last line because this repo's commit gate prints that line alone on a pass.
    # What did not run is named in it too: the detail above scrolls past, and a NOT COVERED line
    # nobody sees is the silence this file is written to avoid.
    trailing = f", {len(gate.uncovered)} not covered" if gate.uncovered else ""
    print(f"\n{len(gate.results)} assertion(s), {failed} failed{trailing}.")
    return 1 if failed else 0


def main() -> int:
    print(f"conventions: claude/conventions (dotfiles at {engine.dotfiles_sha()})")
    gate = Gate()
    try:
        versions = engine.load_versions()
    except engine.VersionError as exc:
        gate.ok(False, "the version set loads", str(exc))
        return report(gate)
    base = tempfile.mkdtemp(prefix="conventions-tests-")
    before = sandbox_git(base)
    try:
        # Asked once, of the temp directory itself: a rule whose git call is meant to go unanswered
        # is pointed at a plain directory, and a plain directory inside somebody's checkout is
        # answered by that checkout's rules rather than refused.
        outside_repo = run_git(base, ["rev-parse", "--show-toplevel"])[0] != 0
        version_shape(gate, versions)
        rule_wiring(gate, versions)
        rule_behaviour(gate, base, outside_repo)
        record_round_trip(gate, base, versions)
        behind_for_cases(gate, base, versions)
    finally:
        restore_env(before)
        remove_tree(base)
    return report(gate)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # A crash here means the gate did not finish, which must not read as a pass: the traceback
        # goes to stderr through the interpreter's own hook and the exit code is the failing one.
        sys.excepthook(*sys.exc_info())
        raise SystemExit(1)
