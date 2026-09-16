#!/usr/bin/env python3
"""The continuous checker: every convention rule this repo has taken on, re-derived now.

    python ~/.claude/conventions/check.py <repo-root>

What a repo's `.claude/commit-checks.sh` runs. A version is a migration — it ran, or it did not,
and the repo's record says how far — while a rule is a property that has to hold *continuously*,
which is why it lives here rather than inside a version folder: a version is frozen the moment a
repo runs it, and a check improves for every repo at once.

Which rules run is read off the repo's adopted integer, never off the tree: a rule introduced by
v12 does not run in a repo at v11, so a repo takes on stricter checking by adopting and never
because someone edited a shared file. The mapping from a rule to the version that introduced it is
derived from the version folders' `rules:` frontmatter, so nothing states it twice.

A rule that cannot establish its answer — git refusing, a file that will not read — raises, and
that arrives here as **unmeasured**: the rule is named, the exception with it, and the exit code is
non-zero. A rule that could not look must never read as a rule that passed, which is the whole
reason the rules raise rather than returning an empty list.

Exit codes, the same three the engine uses: 0 every rule held · 1 a rule was violated or went
unmeasured · 2 the tool refuses and a human must fix something (a bad invocation, an unreadable
record, a version set that will not load).
"""

import importlib
import os
import sys
import traceback

# A compiled copy left beside a rule outlives the source it was built from, and a stale one reports
# on code that no longer exists (learnings/python-stale-bytecode-cache.md). This runs in every repo
# on the machine, so it must leave nothing in the dotfiles checkout at all.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.realpath(__file__))
RULES_DIR = os.path.join(HERE, "rules")
# The engine owns the version set and the record. A rule sits beside its siblings and imports the
# shared helpers by bare name, so the rules directory goes on the path too — appended rather than
# inserted, so a rule file can never shadow a standard-library module for anything above it.
sys.path.insert(0, HERE)
sys.path.append(RULES_DIR)

import engine  # noqa: E402 — needs the sys.path line above

if hasattr(sys.stdout, "reconfigure"):
    # A violation line carries paths, and a path holding a character outside the console's codepage
    # kills the process on Windows — where the gate that runs this lives
    # (learnings/python-windows-console-encoding.md).
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def rule_versions() -> dict[str, int]:
    """Every rule the version set names, mapped to the version that introduced it.

    The lowest version wins where two name the same rule, because "introduced" is when a repo took
    the rule on. Reading it off the frontmatter is what keeps a rule from having to state its own
    version: the folder that hands the checker a rule is the folder that dates it.
    """
    introduced: dict[str, int] = {}
    for entry in engine.load_versions():
        for name in entry.rules:
            introduced[name] = min(introduced.get(name, entry.number), entry.number)
    return introduced


def run(name: str, root: str) -> list[str]:
    """One rule's violations, empty when it holds. Anything short of an answer raises.

    The shape of what comes back is asserted rather than trusted: a rule returning None because a
    branch forgot its `return` would otherwise read as a clean pass, which is the one wrong answer
    this checker exists to make impossible.
    """
    module = importlib.import_module(name)
    rule = getattr(module, "check", None)
    if not callable(rule):
        raise TypeError(f"rules/{name}.py exposes no check(root) function")
    found = rule(root)
    if not isinstance(found, list) or any(not isinstance(line, str) for line in found):
        raise TypeError(f"rules/{name}.py returned {found!r}, not a list of violation lines")
    return found


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        print("usage: check.py <repo-root>")
        return 2
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        print(f"{sys.argv[1]} is not a directory, so there is nothing here to check")
        return 2
    try:
        # Zero for a repo that is exempt or has never been asked, so both run no rules and say so
        # rather than being checked against a version nobody decided; an unreadable record raises.
        adopted = engine.adopted(root)
    except Exception as exc:
        print(f"the convention record in this repo could not be read ({exc}), so which rules apply "
              f"here was never established")
        return 2
    try:
        introduced = rule_versions()
    except Exception as exc:
        print(f"the version set in this dotfiles checkout could not be read ({exc}), so which rules "
              f"apply here was never established")
        return 2

    # An exempt repo counts as zero adopted versions, which is the right answer to "which rules
    # apply" and the wrong sentence to print: it has not adopted v0, it adopts nothing. The reason
    # is asked for here so the header says which of the two this is.
    exempt = engine.read_record(root).exempt
    applicable = sorted((number, name) for name, number in introduced.items() if number <= adopted)
    stands = f"exempt ({exempt})" if exempt else f"adopted v{adopted}"
    print(f"conventions check: {root}")
    print(f"{stands}, dotfiles at {engine.dotfiles_sha()} — {len(applicable)} rule(s) taken on")
    if not applicable:
        # Said rather than left to the silence, so "checked and clean" and "checked nothing" cannot
        # be read off the same empty output.
        print("nothing was checked: no version this repo has adopted introduces a continuing rule")
        return 0

    violated: list[str] = []
    unmeasured: list[str] = []
    violations = 0
    for number, name in applicable:
        try:
            found = run(name, root)
        except Exception as exc:
            unmeasured.append(name)
            print(f"\n{name} (v{number}) — UNMEASURED: {type(exc).__name__}: {exc}")
            # The traceback and not only the sentence: a rule that refused says why in its message,
            # while a rule with a bug says it here and nowhere else. Unchained, because a helper
            # that wraps a failure quotes the original in its own message — printing the cause's
            # stack as well doubles the length of every refusal a commit gate has to read.
            print("\n".join(f"    {line}" for line in traceback.format_exc(chain=False).splitlines()))
            continue
        if found:
            violated.append(name)
            violations += len(found)
            print(f"\n{name} (v{number})")
            for line in found:
                print(f"  {line}")

    tally: list[str] = []
    if violations:
        tally.append(f"{violations} violation(s) across {len(violated)} rule(s)")
    if unmeasured:
        tally.append(f"{len(unmeasured)} rule(s) unmeasured")
    if not tally:
        print(f"\nall {len(applicable)} rule(s) held: {', '.join(name for _, name in applicable)}")
        return 0
    tally.append(f"{len(applicable) - len(violated) - len(unmeasured)} held")
    print("\n" + "; ".join(tally) + ".")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # A crash in the runner itself means no rule was measured, which is the refusal code and not
        # the violation one: the traceback goes to stderr through the interpreter's own hook, and a
        # gate reading the exit status is told a human has something to fix.
        sys.excepthook(*sys.exc_info())
        raise SystemExit(2)
