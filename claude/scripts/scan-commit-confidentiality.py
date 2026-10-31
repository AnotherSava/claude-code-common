#!/usr/bin/env python3
"""Scan files, staged changes and unpushed commits for content that must not reach a public repo.

Exists because the scan was prose, so every run rebuilt it by hand and could rebuild its failures with it. Both of the
documented ones recurred on 2026-10-08: a scan that read no files and reported "none", and a candidate set harvested
by tokenizing prose, whose English words buried every real hit. Here both are controls that fail loudly instead.

`--staged` and `--range` read only the lines a change adds, which is what a commit or a push publishes; paths given
on the command line are read whole, for a deliberate audit of a file.

Findings come in two kinds. A **blocking** finding is a shape that is a leak unless shown otherwise — a private key,
this machine's home directory, a machine name, a real tailnet host, a public or tailnet IP address, a real email
address — and it stops `shared/commit.py` and the `pre-push` hook. A **review** finding is a shape that is usually prose in this repo — a
credential word, a public domain, an `ssh host` position — and it is printed for a reader to triage, never acted on
here. Measured on 300 commits of added lines: blocking on every shape stopped one commit in six, which no unattended
gate can carry.

Exit codes are three-valued on purpose — a control that could not run must never look like a clean scan:
    0  controls passed, no blocking findings (review findings may be printed)
    1  controls passed, blocking findings reported
    2  a control failed; the scan proves nothing

`--self-test` answers about the controls instead of about a tree, so it has nothing to report a control failure
about and returns 0 or 1 alone.
"""

import argparse
import hashlib
import ipaddress
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Set, Tuple

# A candidate matching more lines than this across the scanned set is reported as noise rather than as findings.
# Self-calibrating, so no word list is needed and a short real hostname is not dropped for being short: selectivity
# is what separates a name from a word, not length.
NOISE_MATCH_THRESHOLD = 3

# The committed per-repo allow-list a blocking false positive is cleared through. One fingerprint per line, `#`
# starting a comment; `fingerprint()` is what the scanner prints beside each blocking finding.
ALLOW_FILE = ".claude/confidentiality-allow"

# A line in the private coordinates file naming a machine whose name is also an ordinary word. Its matches become
# review findings: the noise filter cannot catch such a word in a scan of one commit's few added lines.
REVIEW_ONLY = re.compile(r"^\s*scan-review-only:\s*(\S+)", re.I | re.M)

REVIEW_PATTERNS: Sequence[Tuple[str, "re.Pattern[str]"]] = (
    ("absolute-path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/](?:Users|projects|Projects))")),
    ("internal-host", re.compile(r"\b[a-z0-9-]+\.(?:local|internal|lan)\b", re.I)),
    ("public-dotted", re.compile(r"\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|dev|app)\b", re.I)),
    ("host-position", re.compile(r"(?:(?:SSH_)?HOST=|ssh\s+[a-z0-9]|-C\s+[a-z0-9])", re.I)),
    ("credential-word", re.compile(r"(?:api[-_ ]?key|passwo?rd|passphrase|secret|bearer|token)", re.I)),
)

# A dotted quad standing alone: not the front of a five-part version, and not a CIDR prefix, which names a network.
IPV4 = re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?!\.?\d|/\d)")
# Tailscale hands out addresses from the shared CGNAT range, so one there names a machine on somebody's tailnet even
# though `ipaddress` calls the range non-global. Tailscale's fixed MagicDNS resolver, 100.100.100.100, sits in the
# range too and names no machine, yet blocks like any other address there: a line adding it needs an allow-list entry.
TAILNET_RANGE = ipaddress.ip_network("100.64.0.0/10")
# Four single-digit parts is the shape of a version string (`8.1.3.1` in a Gemfile.lock); no machine of the user's has
# such an address, and the public ones that do (8.8.8.8, 1.1.1.1) are well-known resolvers, which publish nothing.
VERSION_SHAPED = re.compile(r"\d(?:\.\d){3}")
# An `@2x`/`@3x` asset name, whose "domain" is a scale factor and a file extension.
ASSET_SCALE_DOMAIN = re.compile(r"^\d+x\.", re.I)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
TAILNET = re.compile(r"\b[a-z0-9-]+\.([a-z0-9-]+)\.ts\.net\b", re.I)
PRIVATE_KEY = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
RESERVED_EMAIL_DOMAIN = re.compile(r"(?:^|\.)(?:example\.(?:com|net|org)|invalid|test|example|localhost)$", re.I)
# The tailnet segment of a placeholder: `tailxxxx`, `tail-example`. A real one is `tail` and hex digits.
PLACEHOLDER_TAILNET = re.compile(r"x{3,}|example|<", re.I)


def _ip_names_a_machine(text: str) -> bool:
    """A public address, or a host on a tailnet. Private, link-local, loopback, documentation (RFC 5737) and other
    reserved addresses name no machine an outsider can reach, and a version string is not an address at all."""
    try:
        addr = ipaddress.IPv4Address(text)
    except ValueError:
        return False
    if VERSION_SHAPED.fullmatch(text):
        return False
    return addr.is_global or addr in TAILNET_RANGE


def _ip_blocks(line: str) -> bool:
    return any(_ip_names_a_machine(m.group(0)) for m in IPV4.finditer(line))


def _email_blocks(line: str) -> bool:
    return any(m.group(0).lower() != "git@github.com" and not RESERVED_EMAIL_DOMAIN.search(m.group(1)) and not ASSET_SCALE_DOMAIN.match(m.group(1))
               for m in EMAIL.finditer(line))


def _tailnet_blocks(line: str) -> bool:
    return any(not PLACEHOLDER_TAILNET.search(m.group(1)) for m in TAILNET.finditer(line))


def _home_pattern(home: str) -> "re.Pattern[str]":
    """This machine's own home directory, in either platform's spelling. Another user's path is a review finding."""
    user = re.escape(os.path.basename(home.rstrip("/\\")))
    return re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])" + user + r"(?![A-Za-z0-9_-])", re.I)


HOME = _home_pattern(os.path.expanduser("~"))

# Each sees one added line. The loopback and reserved-domain exemptions are what make these quiet enough to block on.
BLOCKING_CHECKS: Sequence[Tuple[str, object]] = (
    ("private-key", lambda line: bool(PRIVATE_KEY.search(line))),
    ("home-path", lambda line: bool(HOME.search(line))),
    ("ipv4", _ip_blocks),
    ("tailnet-host", _tailnet_blocks),
    ("email", _email_blocks),
)

# A hostname need not look like an address, so the shapes are: an IPv4 literal, a dotted name, or a bare token in a
# position that can only hold a host. Tokenizing the prose around them is what produced 462 candidates and 1083
# meaningless matches, so the position is required. The command itself is matched case-sensitively: under the global
# re.I a sentence opening "SSH would work…" in the coordinates file harvested "would", which then flagged ordinary prose.
HOST_SHAPE = re.compile(
    r"\b(?:\d{1,3}(?:\.\d{1,3}){3})\b"
    r"|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+){1,}\.(?:net|com|org|io|dev|app|local|internal|lan)\b"
    r"|(?:(?:SSH_)?HOST=|(?-i:ssh)\s+(?:[A-Za-z0-9._-]+@)?|-C\s+)([A-Za-z0-9][A-Za-z0-9._-]{2,})",
    re.I,
)

# One scanned line: its number in the file it belongs to, and its text.
Line = Tuple[int, str]
# One finding: its label, the source it is in, the line number, and the line's text (for the fingerprint).
Finding = Tuple[str, str, int, str]


def mask(value: str) -> str:
    """Render a candidate without republishing it into a transcript this scan protects."""
    if len(value) < 3:
        return "*" * len(value)
    return "{0}{1}{2} (len {3}, dots {4})".format(value[0], "*" * (len(value) - 2), value[-1], len(value), value.count("."))


def fingerprint(source: str, text: str) -> str:
    """The allow-list key for a finding: its file and its line's text, never the matched value. A range source is
    filed as `<sha>:<path>`, and the sha is dropped so an entry outlives the commit it was first seen in."""
    path = source.split(":", 1)[1] if re.match(r"^[0-9a-f]{7,40}:", source) else source
    return hashlib.sha256("{0}\0{1}".format(path, text.strip()).encode("utf-8")).hexdigest()[:12]


def fail_control(headline: str, details: Sequence[str] = (), scope: str = "") -> int:
    """Print a control failure so it cannot read as a clean scan, and yield the exit code for one.

    One function because the "NOT SCANNED" line is what separates an unmeasured run from a clean one; a copy per call
    site is a chance for one path to print something softer.
    """
    print("CONTROL FAILED — {0}".format(headline))
    for detail in details:
        print("  {0}".format(detail))
    print("NOT SCANNED{0}. This is not a clean result.".format(scope))
    return 2


def range_key(git_range: str) -> str:
    """The source name an empty git range is reported under."""
    return "<git {0}>".format(git_range)


STAGED_KEY = "<staged changes>"


def added_lines(patch: str, with_commits: bool) -> Dict[str, List[Line]]:
    """The lines a patch adds, filed by the path they land in (prefixed `<sha>:` when `with_commits`), numbered as in
    the new file. Removed and context lines are what the change takes away or leaves alone, so they publish nothing."""
    sources: Dict[str, List[Line]] = {}
    commit, path, number = "", None, 0
    for raw in patch.splitlines():
        if raw.startswith("COMMIT "):
            commit = raw[7:].strip()
        elif raw.startswith("+++ "):
            target = raw[4:]
            path = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
        elif raw.startswith("@@"):
            m = re.match(r"@@ -\S+ \+(\d+)", raw)
            number = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path is not None:
            name = "{0}:{1}".format(commit, path) if with_commits else path
            sources.setdefault(name, []).append((number, raw[1:]))
            number += 1
    return sources


def read_sources(paths: Sequence[str], git_range: Optional[str], staged: bool, repo: pathlib.Path) -> Dict[str, List[Line]]:
    """Read every path literally, and the added lines of the range and the index. A missing path raises rather than
    scanning nothing quietly. Every source not named in `paths` holds added lines only."""
    sources: Dict[str, List[Line]] = {}
    for rel in paths:
        target = pathlib.Path(rel)
        if not target.is_absolute():
            target = repo / rel
        sources[rel] = list(enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), 1))
    if git_range:
        out = subprocess.run(["git", "-C", str(repo), "log", "-p", "-U0", "--no-textconv", "--no-renames", "--format=COMMIT %h"] + git_range.split(),
                             capture_output=True, text=True, check=True).stdout
        sources.update(added_lines(out, True) or {range_key(git_range): []})
    if staged:
        out = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "-U0", "--no-textconv", "--no-renames"], capture_output=True, text=True, check=True).stdout
        sources.update(added_lines(out, False) or {STAGED_KEY: []})
    return sources


def control_read(sources: Dict[str, List[Line]], allow_empty: Sequence[str] = (), short_ok: Set[str] = frozenset()) -> List[str]:
    """Prove the matcher reached each source, by searching each for a slice of its own content.

    This is what distinguishes a clean scan from one whose paths never resolved: an unreadable or empty source cannot
    supply a probe that matches itself. An empty range or index is the one source that can be legitimately empty —
    nothing to publish is a state, not a failed read — so a caller naming it in `allow_empty` exempts it. An added-line
    source is often one short line, so a source named in `short_ok` needs only a non-empty line to probe with. A file
    whose only added lines are blank still fails, so a commit adding nothing but a blank line to a file exits 2 ("could
    not run") and is blocked by `commit.py` and pre-push alike: fold that line into a commit with real content in the
    same file, or drop it.
    """
    failures: List[str] = []
    for name, lines in sources.items():
        if not lines and name in allow_empty:
            continue
        texts = [text for _, text in lines]
        probe = max(texts, key=len).strip() if texts else ""
        if len(probe) < (1 if name in short_ok else 12):
            failures.append("{0}: no line long enough to probe with ({1} line(s))".format(name, len(lines)))
            continue
        needle = probe[:12]
        if not any(needle in text for text in texts):
            failures.append("{0}: self-probe did not match — the matcher is not reading it".format(name))
    return failures


def harvest_candidates(coord_path: pathlib.Path) -> Tuple[Set[str], Set[str]]:
    """Machine names from the private coordinates file, split into the ones that block and the ones marked
    review-only. Loopback and the unspecified address name no machine, so they are never candidates."""
    if not coord_path.exists():
        return set(), set()
    text = coord_path.read_text(encoding="utf-8", errors="replace")
    found: Set[str] = set()
    for m in HOST_SHAPE.finditer(text):
        value = (m.group(1) or m.group(0)).strip().lower()
        if len(value) > 3 and not re.fullmatch(r"127(?:\.\d{1,3}){3}|0\.0\.0\.0", value):
            found.add(value)
    review_only = {m.group(1).lower() for m in REVIEW_ONLY.finditer(text)}
    return found - review_only, found & review_only


def candidate_pattern(cand: str) -> "re.Pattern[str]":
    """Match a candidate only where no letter or digit adjoins it. A substring test fires on a short machine name
    spelled inside an ordinary word, as one did inside "there", and the noise filter cannot catch that in a one-file
    commit, where the word matches too few lines to count. Punctuation and underscore still bound it, so `name.local`,
    `user@name`, `name-mac` and `name_backup` all match; a name that is itself a word still fires, as it must."""
    return re.compile(r"(?<![a-z0-9]){0}(?![a-z0-9])".format(re.escape(cand)))


def scan(sources: Dict[str, List[Line]], candidates: Set[str], review_names: Set[str] = frozenset()) -> Tuple[List[Finding], List[Finding], List[Tuple[str, int]], List[str]]:
    """Return blocking findings, review findings, noisy candidates with their counts, and control failures."""
    patterns = {c: candidate_pattern(c) for c in candidates | set(review_names)}
    counts = {c: 0 for c in candidates}
    for lines in sources.values():
        for _, text in lines:
            low = text.lower()
            for cand in candidates:
                if patterns[cand].search(low):
                    counts[cand] += 1

    noisy = sorted((c for c in candidates if counts[c] > NOISE_MATCH_THRESHOLD), key=lambda c: -counts[c])
    useful = candidates - set(noisy)

    blocking: List[Finding] = []
    review: List[Finding] = []
    for name, lines in sources.items():
        for number, text in lines:
            low = text.lower()
            for label, check in BLOCKING_CHECKS:
                if check(text):
                    blocking.append((label, name, number, text))
            if any(patterns[c].search(low) for c in useful):
                blocking.append(("user-hostname", name, number, text))
            for label, pat in REVIEW_PATTERNS:
                if pat.search(text):
                    review.append((label, name, number, text))
            if any(patterns[c].search(low) for c in review_names):
                review.append(("word-hostname", name, number, text))

    control_failures: List[str] = []
    if candidates and not useful:
        control_failures.append("every one of the {0} harvested candidate(s) is noise — the extraction discriminates nothing".format(len(candidates)))
    return blocking, review, [(c, counts[c]) for c in noisy], control_failures


def read_allow(repo: pathlib.Path) -> Set[str]:
    path = repo / ALLOW_FILE
    if not path.exists():
        return set()
    return {line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()} - {""}


def self_test() -> int:
    """Assert each control, each blocking shape and its exemption, and the noise path actually fire. A fixture that
    misses its branch reports success, which is the failure mode this whole script exists to remove."""
    failures: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        user = os.path.basename(os.path.expanduser("~").rstrip("/\\"))

        planted = root / "planted.md"
        planted.write_text(
            "This paragraph is long enough to supply a self-probe for the read control.\n"
            "A deploy note mentioning /Users/{0}/projects/example-app and admin@realcorp.co.\n"
            "Reach it at 100.64.12.7 or box.tail1a2b3c.ts.net, and keep the api token out.\n"
            "The origin answers on 45.33.120.9.\n".format(user),
            encoding="utf-8",
        )
        sources = read_sources(["planted.md"], None, False, root)
        if control_read(sources):
            failures.append("read control failed on a readable file")
        blocking, review, _, ctl = scan(sources, set())
        found = {f[0] for f in blocking}
        for label in ("home-path", "email", "ipv4", "tailnet-host"):
            if label not in found:
                failures.append("planted {0} was not a blocking finding".format(label))
        ip_lines = {f[2] for f in blocking if f[0] == "ipv4"}
        if ip_lines != {3, 4}:
            failures.append("planted tailnet and public addresses blocked on lines {0}, expected [3, 4]".format(sorted(ip_lines)))
        if "credential-word" not in {f[0] for f in review}:
            failures.append("planted credential word was not a review finding")
        if "credential-word" in found:
            failures.append("a credential word blocked")
        if ctl:
            failures.append("extraction control fired with no candidates supplied")

        # Each exemption is what makes a blocking shape quiet enough to block on, so each is asserted to hold.
        exempt = root / "exempt.md"
        exempt.write_text(
            "Bind 127.0.0.1 or 0.0.0.0, mail t@example.invalid or admin@example.com, clone git@github.com:o/r.\n"
            "A placeholder host anything.tailxxxx.ts.net and another user's /Users/someone-else/app path.\n"
            "LAN 192.168.1.10, metadata 169.254.169.254, docs HostName 203.0.113.10, not remote_ip 100.64.0.0/10.\n"
            "#define AppVersion \"0.20.13.1\", activesupport (8.1.3.1), libfoo 1.2.3.45.6, icon \"icons/128x128@2x.png\".\n",
            encoding="utf-8",
        )
        blocking, review, _, _ = scan(read_sources(["exempt.md"], None, False, root), set())
        if blocking:
            failures.append("an exempt value blocked: {0}".format(sorted({f[0] for f in blocking})))
        if "absolute-path" not in {f[0] for f in review}:
            failures.append("another user's absolute path was not a review finding")

        try:
            read_sources(["does-not-exist.md"], None, False, root)
            failures.append("a missing path did not raise")
        except OSError:
            pass

        empty = root / "empty.md"
        empty.write_text("", encoding="utf-8")
        if not control_read(read_sources(["empty.md"], None, False, root)):
            failures.append("read control passed on an empty file")

        # An empty range is a state, not a failed read. Exempting it must not also exempt an empty file, or the
        # control stops telling the two apart — which is the whole distinction.
        key = range_key("HEAD --not --remotes")
        if control_read({key: []}, (key,)):
            failures.append("read control rejected an empty range it was told to allow")
        if not control_read({"empty.md": []}, (key,)):
            failures.append("allow_empty exempted a source it does not name")

        # Only added lines are read: a removed line and a context line publish nothing.
        patch = "COMMIT abc1234\n+++ b/app.txt\n@@ -1,2 +1,2 @@\n-old 100.64.0.1 line\n+new line at 100.64.0.2\n"
        added = added_lines(patch, True)
        if added != {"abc1234:app.txt": [(1, "new line at 100.64.0.2")]}:
            failures.append("added_lines read {0}".format(added))

        # The noise branch needs MORE than NOISE_MATCH_THRESHOLD matching lines, or the fixture never reaches it and
        # the test passes without testing anything.
        wordy = root / "wordy.md"
        wordy.write_text(("the home of the thing\n" * (NOISE_MATCH_THRESHOLD + 2)), encoding="utf-8")
        blocking, _, noisy, ctl = scan(read_sources(["wordy.md"], None, False, root), {"home"})
        if not noisy:
            failures.append("word-like candidate was not reported as noise")
        if any(f[0] == "user-hostname" for f in blocking):
            failures.append("word-like candidate produced findings instead of a noise report")
        if not ctl:
            failures.append("extraction control did not fire when every candidate was noise")

        # At most NOISE_MATCH_THRESHOLD lines, even under a substring match, so the candidate stays useful and only
        # the word-boundary match decides each line.
        bounded = root / "bounded.md"
        bounded.write_text("ssh to name_backup now\nreach name.local or user@name\nthe rename went fine\n", encoding="utf-8")
        blocking, _, _, _ = scan(read_sources(["bounded.md"], None, False, root), {"name"})
        hit_lines = {f[2] for f in blocking if f[0] == "user-hostname"}
        if hit_lines != {1, 2}:
            failures.append("bounded candidate matched lines {0}, expected [1, 2]".format(sorted(hit_lines)))

        # A review-only machine name reports where it appears but never blocks.
        blocking, review, _, _ = scan(read_sources(["bounded.md"], None, False, root), set(), {"name"})
        if any(f[0] == "user-hostname" for f in blocking) or "word-hostname" not in {f[0] for f in review}:
            failures.append("a review-only machine name blocked, or was not reported for review")

        coords = root / "coords.md"
        coords.write_text("SSH would work from either side.\nLog in with `ssh someone@examplebox` or `ssh me@wordbox`.\n"
                          "Bind 127.0.0.1 only.\nscan-review-only: wordbox\n", encoding="utf-8")
        harvested = harvest_candidates(coords)
        if harvested != ({"examplebox"}, {"wordbox"}):
            failures.append("harvest gave {0} blocking and {1} review-only candidate(s), expected 1 and 1".format(len(harvested[0]), len(harvested[1])))

        if fingerprint("abc1234:app.txt", " same line ") != fingerprint("app.txt", "same line"):
            failures.append("a fingerprint depends on the commit or on surrounding whitespace")

    if failures:
        for f in failures:
            print("self-test FAILED: {0}".format(f))
        return 1
    print("scan-commit-confidentiality self-test: all controls, blocking shapes, exemptions and the noise path fire")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="files to scan whole, repo-relative or absolute")
    parser.add_argument("--range", dest="git_range", help="also scan the lines these commits add, e.g. 'HEAD --not --remotes'")
    parser.add_argument("--staged", action="store_true", help="also scan the lines the index adds over HEAD")
    parser.add_argument("--repo", default=".", help="repo root paths resolve against")
    parser.add_argument("--self-test", action="store_true", help="prove the controls fire, then exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.paths and not args.git_range and not args.staged:
        parser.error("give at least one path, --range or --staged")

    repo = pathlib.Path(args.repo).resolve()
    try:
        sources = read_sources(args.paths, args.git_range, args.staged, repo)
    except (OSError, subprocess.CalledProcessError) as exc:
        return fail_control("could not read the sources: {0}".format(exc))

    allow_empty = tuple(name for name, wanted in ((range_key(args.git_range or ""), args.git_range), (STAGED_KEY, args.staged)) if wanted)
    read_failures = control_read(sources, allow_empty, set(sources) - set(args.paths))
    if read_failures:
        return fail_control("the matcher is not reading every source:", read_failures)
    empty = [name for name in allow_empty if name in sources and not sources[name]]
    print("control-read: self-probe matched in all {0} source(s)".format(len(sources) - len(empty)))
    for name in empty:
        print("control-read: {0} adds no lines, so there was nothing there to scan".format(name))

    coord = pathlib.Path(os.path.expanduser("~/.claude/memory/machines-private.secret.md"))
    candidates, review_names = harvest_candidates(coord)
    print("control-extract: {0} host-shaped candidate(s) harvested, {1} marked review-only".format(len(candidates), len(review_names)))
    if not candidates:
        print("  (none — the machine coordinates are absent or still encrypted; the")
        print("   user-hostname class was NOT COVERED by this run)")

    blocking, review, noisy, ctl_failures = scan(sources, candidates, review_names)

    if noisy:
        print("\nexcluded as noise (matched more than {0} line(s); values masked):".format(NOISE_MATCH_THRESHOLD))
        for cand, n in noisy:
            print("  {0}  matches={1}".format(mask(cand), n))

    if ctl_failures:
        print()
        return fail_control("the candidate set discriminates nothing:", ctl_failures, " for the user-hostname class")

    allowed = read_allow(repo)
    kept = [f for f in blocking if fingerprint(f[1], f[3]) not in allowed]
    if len(kept) != len(blocking):
        print("\nallowed by {0}: {1} occurrence(s)".format(ALLOW_FILE, len(blocking) - len(kept)))

    print("\nreview: {0} occurrence(s) — usually prose here; read each, nothing blocks on them".format(len(review)))
    for label, name, line, _ in review:
        print("  {0:16s} {1}:{2}".format(label, name, line))
    print("\nblocking: {0} occurrence(s) — reported per occurrence, never deduplicated".format(len(kept)))
    for label, name, line, text in kept:
        print("  {0:16s} {1}:{2}  allow={3}".format(label, name, line, fingerprint(name, text)))
    if kept:
        print("\nA false positive is cleared by adding its allow= value to {0}, with a comment saying why.".format(ALLOW_FILE))
    return 1 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
