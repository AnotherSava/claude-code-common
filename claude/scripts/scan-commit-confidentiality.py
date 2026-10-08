#!/usr/bin/env python3
"""Scan files and unpushed commits for content that must not reach a public repo.

Exists because `/commit` step 5's scan was prose, so every run rebuilt it by hand and could
rebuild its failures with it. Both of the documented ones recurred on 2026-10-08: a scan that
read no files and reported "none", and a candidate set harvested by tokenizing prose, whose
English words buried every real hit. Here both are controls that fail loudly instead.

Exit codes are three-valued on purpose — a control that could not run must never look like a
clean scan:
    0  controls passed, no findings
    1  controls passed, findings reported
    2  a control failed; the scan proves nothing

`--self-test` answers about the controls instead of about a tree, so it has nothing to report a
control failure about and returns 0 or 1 alone.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Set, Tuple

# A candidate matching more lines than this across the scanned set is reported as noise rather
# than as findings. Self-calibrating, so no word list is needed and a short real hostname is
# not dropped for being short: selectivity is what separates a name from a word, not length.
NOISE_MATCH_THRESHOLD = 3

PATTERNS: Sequence[Tuple[str, "re.Pattern[str]"]] = (
    ("absolute-path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/](?:Users|projects|Projects))")),
    ("ipv4", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("internal-host", re.compile(r"\b[a-z0-9-]+\.(?:local|internal|lan)\b", re.I)),
    ("tailnet-host", re.compile(r"\b[a-z0-9-]+\.[a-z0-9-]+\.ts\.net\b", re.I)),
    ("public-dotted", re.compile(r"\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|dev|app)\b", re.I)),
    ("host-position", re.compile(r"(?:(?:SSH_)?HOST=|ssh\s+[a-z0-9]|-C\s+[a-z0-9])", re.I)),
    ("private-key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("credential-word", re.compile(r"(?:api[-_ ]?key|passwo?rd|passphrase|secret|bearer|token)", re.I)),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)

# A hostname need not look like an address, so the shapes are: an IPv4 literal, a dotted name,
# or a bare token in a position that can only hold a host. Tokenizing the prose around them is
# what produced 462 candidates and 1083 meaningless matches, so the position is required.
HOST_SHAPE = re.compile(
    r"\b(?:\d{1,3}(?:\.\d{1,3}){3})\b"
    r"|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+){1,}\.(?:net|com|org|io|dev|app|local|internal|lan)\b"
    r"|(?:(?:SSH_)?HOST=|ssh\s+(?:[A-Za-z0-9._-]+@)?|-C\s+)([A-Za-z0-9][A-Za-z0-9._-]{2,})",
    re.I,
)


def mask(value: str) -> str:
    """Render a candidate without republishing it into a transcript this scan protects."""
    if len(value) < 3:
        return "*" * len(value)
    return "{0}{1}{2} (len {3}, dots {4})".format(
        value[0], "*" * (len(value) - 2), value[-1], len(value), value.count(".")
    )


def fail_control(headline: str, details: Sequence[str] = (), scope: str = "") -> int:
    """Print a control failure so it cannot read as a clean scan, and yield the exit code for one.

    One function because the "NOT SCANNED" line is what separates an unmeasured run from a clean
    one; a copy per call site is a chance for one path to print something softer.
    """
    print("CONTROL FAILED — {0}".format(headline))
    for detail in details:
        print("  {0}".format(detail))
    print("NOT SCANNED{0}. This is not a clean result.".format(scope))
    return 2


def range_key(git_range: str) -> str:
    """The source name a git range is filed under. Shared so a caller can name it in `allow_empty`."""
    return "<git {0}>".format(git_range)


def read_sources(paths: Sequence[str], git_range: Optional[str], repo: pathlib.Path) -> Dict[str, List[str]]:
    """Read every path literally. A missing path raises rather than scanning nothing quietly."""
    sources: Dict[str, List[str]] = {}
    for rel in paths:
        target = pathlib.Path(rel)
        if not target.is_absolute():
            target = repo / rel
        sources[rel] = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if git_range:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "-p", "--no-textconv"] + git_range.split(),
            capture_output=True, text=True, check=True,
        ).stdout
        sources[range_key(git_range)] = out.splitlines()
    return sources


def control_read(sources: Dict[str, List[str]], allow_empty: Sequence[str] = ()) -> List[str]:
    """Prove the matcher reached each source, by searching each for a slice of its own content.

    This is what distinguishes a clean scan from one whose paths never resolved: an unreadable
    or empty source cannot supply a probe that matches itself. A git range is the one source
    that can be legitimately empty — no unpushed commits is a state, not a failed read — so a
    caller naming it in `allow_empty` exempts it, and main() then says it held nothing rather
    than letting an empty range read as scanned history.
    """
    failures: List[str] = []
    for name, lines in sources.items():
        if not lines and name in allow_empty:
            continue
        probe = max(lines, key=len).strip() if lines else ""
        if len(probe) < 12:
            failures.append("{0}: no line long enough to probe with ({1} line(s))".format(name, len(lines)))
            continue
        needle = probe[:12]
        if not any(needle in ln for ln in lines):
            failures.append("{0}: self-probe did not match — the matcher is not reading it".format(name))
    return failures


def harvest_candidates(coord_path: pathlib.Path) -> Set[str]:
    if not coord_path.exists():
        return set()
    text = coord_path.read_text(encoding="utf-8", errors="replace")
    found: Set[str] = set()
    for m in HOST_SHAPE.finditer(text):
        value = (m.group(1) or m.group(0)).strip().lower()
        if len(value) > 3:
            found.add(value)
    return found


def scan(sources: Dict[str, List[str]], candidates: Set[str]) -> Tuple[List[Tuple[str, str, int]], List[Tuple[str, int]], List[str]]:
    counts = {c: 0 for c in candidates}
    for lines in sources.values():
        for ln in lines:
            low = ln.lower()
            for cand in candidates:
                if cand in low:
                    counts[cand] += 1

    noisy = sorted((c for c in candidates if counts[c] > NOISE_MATCH_THRESHOLD), key=lambda c: -counts[c])
    useful = candidates - set(noisy)

    findings: List[Tuple[str, str, int]] = []
    for name, lines in sources.items():
        for i, ln in enumerate(lines, 1):
            for label, pat in PATTERNS:
                if pat.search(ln):
                    findings.append((label, name, i))
            low = ln.lower()
            for cand in useful:
                if cand in low:
                    findings.append(("user-hostname", name, i))

    control_failures: List[str] = []
    if candidates and not useful:
        control_failures.append(
            "every one of the {0} harvested candidate(s) is noise — the extraction discriminates nothing".format(len(candidates))
        )
    return findings, [(c, counts[c]) for c in noisy], control_failures


def self_test() -> int:
    """Assert each control and the noise path actually fire. A fixture that misses its branch
    reports success, which is the failure mode this whole script exists to remove."""
    failures: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)

        planted = root / "planted.md"
        planted.write_text(
            "This paragraph is long enough to supply a self-probe for the read control.\n"
            "A deploy note mentioning /Users/example-user/projects/example-app and admin@example.com.\n",
            encoding="utf-8",
        )
        sources = read_sources(["planted.md"], None, root)
        if control_read(sources):
            failures.append("read control failed on a readable file")
        findings, _, ctl = scan(sources, set())
        labels = {f[0] for f in findings}
        if "absolute-path" not in labels:
            failures.append("planted absolute path not found")
        if "email" not in labels:
            failures.append("planted email not found")
        if ctl:
            failures.append("extraction control fired with no candidates supplied")

        try:
            read_sources(["does-not-exist.md"], None, root)
            failures.append("a missing path did not raise")
        except OSError:
            pass

        empty = root / "empty.md"
        empty.write_text("", encoding="utf-8")
        if not control_read(read_sources(["empty.md"], None, root)):
            failures.append("read control passed on an empty file")

        # An empty git range is a state, not a failed read. Exempting it must not also exempt an
        # empty file, or the control stops telling the two apart — which is the whole distinction.
        key = range_key("HEAD --not --remotes")
        if control_read({key: []}, (key,)):
            failures.append("read control rejected an empty range it was told to allow")
        if not control_read({"empty.md": []}, (key,)):
            failures.append("allow_empty exempted a source it does not name")

        # The noise branch needs MORE than NOISE_MATCH_THRESHOLD matching lines, or the fixture
        # never reaches it and the test passes without testing anything.
        wordy = root / "wordy.md"
        wordy.write_text(("the home of the thing\n" * (NOISE_MATCH_THRESHOLD + 2)), encoding="utf-8")
        findings, noisy, ctl = scan(read_sources(["wordy.md"], None, root), {"home"})
        if not noisy:
            failures.append("word-like candidate was not reported as noise")
        if any(f[0] == "user-hostname" for f in findings):
            failures.append("word-like candidate produced findings instead of a noise report")
        if not ctl:
            failures.append("extraction control did not fire when every candidate was noise")

    if failures:
        for f in failures:
            print("self-test FAILED: {0}".format(f))
        return 1
    print("scan-commit-confidentiality self-test: all controls and the noise path fire")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="files to scan, repo-relative or absolute")
    parser.add_argument("--range", dest="git_range", help="also scan commit content, e.g. 'HEAD --not --remotes'")
    parser.add_argument("--repo", default=".", help="repo root paths resolve against")
    parser.add_argument("--self-test", action="store_true", help="prove the controls fire, then exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.paths and not args.git_range:
        parser.error("give at least one path or a --range")

    repo = pathlib.Path(args.repo).resolve()
    try:
        sources = read_sources(args.paths, args.git_range, repo)
    except (OSError, subprocess.CalledProcessError) as exc:
        return fail_control("could not read the sources: {0}".format(exc))

    allow_empty = (range_key(args.git_range),) if args.git_range else ()
    read_failures = control_read(sources, allow_empty)
    if read_failures:
        return fail_control("the matcher is not reading every source:", read_failures)
    empty_ranges = [name for name in allow_empty if not sources.get(name)]
    print("control-read: self-probe matched in all {0} source(s)".format(len(sources) - len(empty_ranges)))
    for name in empty_ranges:
        print("control-read: {0} holds no commits, so there was no history to scan".format(name))

    coord = pathlib.Path(os.path.expanduser("~/.claude/memory/machines-private.secret.md"))
    candidates = harvest_candidates(coord)
    print("control-extract: {0} host-shaped candidate(s) harvested".format(len(candidates)))
    if not candidates:
        print("  (none — the machine coordinates are absent or still encrypted; the")
        print("   user-hostname class was NOT COVERED by this run)")

    findings, noisy, ctl_failures = scan(sources, candidates)

    if noisy:
        print("\nexcluded as noise (matched more than {0} line(s); values masked):".format(NOISE_MATCH_THRESHOLD))
        for cand, n in noisy:
            print("  {0}  matches={1}".format(mask(cand), n))

    if ctl_failures:
        print()
        return fail_control("the candidate set discriminates nothing:", ctl_failures, " for the user-hostname class")

    print("\nfindings: {0} occurrence(s) — reported per occurrence, never deduplicated".format(len(findings)))
    for label, name, line in findings:
        print("  {0:16s} {1}:{2}".format(label, name, line))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
