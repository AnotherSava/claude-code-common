#!/usr/bin/env python3
"""Cases for `claude/scripts/check-commit-message.py`.

That checker blocks pushes from `git/hooks/pre-push` in every repo that has adopted these
conventions, so a false positive there stops real work and a false negative is the hole the
checker exists to close. The acronym case is the one found by measuring real history: a
subject reading `docs(learnings): LFS objects …` is correct and an earlier draft rejected it.
"""

from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET = os.path.join(ROOT, "claude", "scripts", "check-commit-message.py")

# (message, substrings that must each appear in some violation; empty list means it must pass)
CASES: list[tuple[str, list[str]]] = [
    ("feat: add marker holder model", []),
    ("refactor(engine): consolidate edge filtering", []),
    ("feat!: drop the legacy envelope", []),
    ("docs(learnings): LFS objects pushed before the fix", []),
    ("docs(learnings): GitHub Actions shallow clone", []),
    ("fix: handle eslint-disable comments", []),
    ("docs: Move the text-only rule into CLAUDE.md", ["capitalised"]),
    ("chore: update README with published models, add missing deps", ["over 50"]),
    ("feat: add thing.", ["period"]),
    ("add a thing without a type", ["prefix"]),
    ("wip: something", ["not one of"]),
    ("Merge branch 'main' into feature", []),
    ("Merge pull request #3 from fork/branch", []),
    ('Revert "feat: add thing"', []),
    ("fixup! feat: add thing", []),
    ("feat: ok subject\nno blank line", ["blank line"]),
    ("feat: ok subject\n\none line body", []),
    ("feat: ok subject\n\nline one\nline two\nline three", []),
    ("feat: ok subject\n\nline one\nline two\nline three\nline four", ["over 3"]),
    ("feat: ok subject\n\npara one\n\npara two", ["more than one paragraph"]),
    # Real prose over the width, every token wrappable — the case the limit exists for.
    ("feat: ok subject\n\nthe parser reads this field and the gate refuses a commit that omits it entirely", ["over 72"]),
    # One unbreakable token means the line cannot be wrapped to width at all, so it is exempt.
    ("feat: ok subject\n\nsee " + "z" * 80, []),
    ("feat: ok subject\n\nbody line\n\nCo-Authored-By: Someone <a@b.c>", []),
    ("feat: ok subject\n\nbody line\n\nRefs: #12", []),
    ("feat: ok subject\n\nsee https://" + "y" * 80, []),
]


def main() -> None:
    spec = importlib.util.spec_from_file_location("ccm", TARGET)
    if spec is None or spec.loader is None:
        print(f"check-commit-message tests: cannot load {TARGET}")
        raise SystemExit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    failed = 0
    for message, expected in CASES:
        found = module.violations(message)
        subject = message.split("\n")[0][:46]
        if bool(found) != bool(expected):
            failed += 1
            print(f"  FAIL {subject!r}: expected {'a violation' if expected else 'a pass'}, got {found}")
            continue
        for want in expected:
            if not any(want in line for line in found):
                failed += 1
                print(f"  FAIL {subject!r}: no violation mentioning {want!r}; got {found}")

    print(f"check-commit-message tests: {len(CASES) - failed} of {len(CASES)} cases behave"
          if not failed else f"check-commit-message tests: {failed} failure(s) across {len(CASES)} cases")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
