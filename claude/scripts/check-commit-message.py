#!/usr/bin/env python3
"""Check a commit message against the mechanical rules in `commit-message-rules.md`.

Only the countable rules live here. Whether a body restates the code's own comments, or
explains a reason that is not the author's, needs a reader — those stay with `/commit`.

    check-commit-message.py <rev> [<rev> …]      # from git history
    check-commit-message.py --file <path>        # a prepared message, e.g. COMMIT_EDITMSG
    check-commit-message.py --range @{u}..HEAD   # every commit in a range

Exits 1 when any message fails, 0 otherwise. Prints one line per violation.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

SUBJECT_MAX = 50
BODY_LINE_MAX = 72
BODY_LINES_MAX = 3
UNBREAKABLE_TOKEN = 40

# Conventional Commit types this machine's rules name, plus the ones in common use alongside them.
TYPES = {"feat", "fix", "refactor", "docs", "chore", "test", "style", "perf", "build", "ci", "revert"}
SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?: (?P<rest>.+)$")

# A message git itself composes, which no convention governs.
GENERATED_PREFIXES = ("Merge branch", "Merge remote-tracking", "Merge tag", "Merge pull request", "Revert \"", "fixup!", "squash!")


def violations(message: str) -> list[str]:
    """Every mechanical rule the message breaks, as human-readable lines."""
    lines = message.rstrip("\n").split("\n")
    subject = lines[0] if lines else ""
    found: list[str] = []

    if subject.startswith(GENERATED_PREFIXES):
        return found

    if len(subject) > SUBJECT_MAX:
        found.append(f"subject is {len(subject)} chars, over {SUBJECT_MAX}")

    match = SUBJECT_RE.match(subject)
    if not match:
        found.append("subject has no `type: description` or `type(scope): description` prefix")
    else:
        if match.group("type") not in TYPES:
            found.append(f"type {match.group('type')!r} is not one of {', '.join(sorted(TYPES))}")
        rest = match.group("rest")
        first = rest.split()[0] if rest.split() else ""
        # An acronym or an identifier is legitimately capitalised; a sentence-style capital is not.
        # `docs(learnings): LFS objects …` must pass, `docs: Move the rule` must not.
        if first[:1].isupper() and not (first.isupper() or any(c.isupper() for c in first[1:])):
            found.append(f"description starts with a capitalised word ({first!r})")
        if rest.endswith("."):
            found.append("description ends with a period")

    if len(lines) > 1:
        if lines[1].strip():
            found.append("no blank line between subject and body")
        body = [line for line in lines[2:]]
        while body and not body[-1].strip():
            body.pop()
        # Trailers are metadata, not prose, and are not counted against the body. Removing them
        # leaves the blank line that separated them, so trim again before counting paragraphs.
        prose = [line for line in body if not re.match(r"^[A-Z][A-Za-z-]+: ", line)]
        while prose and not prose[-1].strip():
            prose.pop()
        if sum(1 for line in prose if not line.strip()):
            found.append("body has more than one paragraph")
        filled = [line for line in prose if line.strip()]
        if len(filled) > BODY_LINES_MAX:
            found.append(f"body is {len(filled)} lines, over {BODY_LINES_MAX}")
        for line in filled:
            if len(line) <= BODY_LINE_MAX:
                continue
            # A line carrying an unbreakable token — a URL, a path, a hash — cannot be wrapped to
            # width, wherever in the line it sits, so the limit does not apply to it.
            if any(len(token) > UNBREAKABLE_TOKEN for token in line.split()):
                continue
            found.append(f"body line is {len(line)} chars, over {BODY_LINE_MAX}: {line[:40]}…")
            break
    return found


def revs_in(spec: str) -> list[str]:
    out = subprocess.run(["git", "rev-list", "--no-merges", spec], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"cannot resolve range {spec!r}: {out.stderr.strip()}")
    return out.stdout.split()


def message_of(rev: str) -> str:
    return subprocess.run(["git", "log", "-1", "--format=%B", rev], capture_output=True, text=True, check=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revs", nargs="*", help="commit revisions to check")
    parser.add_argument("--file", help="read one prepared message from this path instead")
    parser.add_argument("--range", dest="rev_range", help="check every non-merge commit in this range")
    parser.add_argument("--quiet", action="store_true", help="print nothing; the exit status is the answer")
    args = parser.parse_args()

    subjects: list[tuple[str, str]] = []
    if args.file:
        with open(args.file) as handle:
            text = "\n".join(line for line in handle.read().split("\n") if not line.startswith("#"))
        subjects.append(("(prepared)", text))
    for rev in (revs_in(args.rev_range) if args.rev_range else []) + args.revs:
        subjects.append((rev, message_of(rev)))

    failed = 0
    for name, message in subjects:
        found = violations(message)
        if not found:
            continue
        failed += 1
        if not args.quiet:
            short = name[:9]
            print(f"{short}: {message.split(chr(10))[0][:60]}")
            for line in found:
                print(f"  - {line}")
    if not args.quiet and not failed:
        print(f"{len(subjects)} message(s) checked, all pass")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
