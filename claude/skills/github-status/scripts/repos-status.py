#!/usr/bin/env python3
"""repos-status — scan every GitHub-owned clone on this machine and on its peer,
and report which ones have pending work.

A machine is scanned by walking PROJECTS_ROOT for git repos whose `origin`
belongs to GITHUB_USER, fetching each one, auto-pulling the clean ones that are
behind, and counting open issues via `gh`. The peer machine is scanned by piping
*this same file* into its interpreter over SSH (`ssh host "python - --json"`), so
the two ends can never run different versions of the scan and nothing has to be
installed or kept in sync on the far side.

Results merge on the repo's `OWNER/REPO` origin slug — the only identity that
survives a different clone path on each machine. A machine that has no clone of
a repo is reported as `absent`, one that has a clean clone as `clean`, and a
machine that could not be reached as `not reached`; those three say different
things and none of them is a blank.

Output is a box table on stdout with per-repo detail sections, plus a
self-contained HTML report written to the repo's gitignored tmp/.

Modes:
  (default)         scan both machines, print the table and the detail sections,
                    and write the state file that --report reads
  --json            scan THIS machine only and print its snapshot as JSON; this
                    is what the peer invocation runs over SSH
  --report          re-read the state file, fold in the per-repo descriptions
                    read from stdin, print the final table, and write the HTML
  --width N         target total table width (also accepted via GHS_WIDTH)
  --descriptions P  read the descriptions from P instead of stdin
  --html PATH       where to write the HTML report
  --state PATH      where the state file lives

Environment:
  PROJECTS_ROOT — directory to scan (overrides config/config.env)
  GITHUB_USER   — origin-URL owner to filter by (default AnotherSava)
  ROOT_DEPTH    — find -maxdepth value (default 4)
  GHS_WIDTH     — target table width (else terminal width, then 120)

Config keys — config/config.env, per-machine and gitignored:
  PROJECTS_ROOT — as above
  MACHINE_NAME  — what this machine is called in the report (default: hostname)
  PEER_SSH      — `user@host` for the other machine; omit to scan only this one
  PEER_PYTHON   — the interpreter name on the peer (default python3; a Windows
                  peer has `python` and no `python3`)
  GHS_WIDTH     — as above

If PROJECTS_ROOT is not set and config/config.env is missing, exits with status
2 — the github-status SKILL.md is expected to prompt the user and create the
config file before invoking.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

EXCLUDED: set[str] = {"notion", "claude-mermaid-fix"}

# How long to wait for the peer's whole scan. It fetches, pulls and queries `gh`
# for every repo it owns, so this is minutes-scale work, not a round trip.
PEER_TIMEOUT = 300
PEER_CONNECT_TIMEOUT = 15

# Minimum width the DESCRIPTION column may shrink to before the total-width
# budget stops being honored — below this, wrapping produces unreadable
# one-or-two-word ribbons, so the table overflows instead.
DESC_MIN_WIDTH = 18


# ── formatting ────────────────────────────────────────────────────────────────


def format_lines(added: int, deleted: int) -> str:
    """Render +A/-D, omitting either side when it's 0. Empty if both are 0."""
    if added and deleted:
        return f"+{added}/-{deleted}"
    if added:
        return f"+{added}"
    if deleted:
        return f"-{deleted}"
    return ""


def format_local(uncommitted: int, added: int, deleted: int) -> str:
    """Render '<count> (+A/-D)' for the LOCAL column. '<count>' alone if no line diff."""
    if not uncommitted:
        return ""
    lines = format_lines(added, deleted)
    return f"{uncommitted} ({lines})" if lines else str(uncommitted)


def human_age(seconds: float) -> str:
    """Format a delta in seconds as a short label like '5 hours', '2 weeks'.

    Picks the largest unit where the count is >= 1, rounds down. Future
    timestamps (negative delta) and zero return empty string.
    """
    if seconds <= 0:
        return ""
    minute, hour, day, week, month, year = 60, 3600, 86400, 86400 * 7, 86400 * 30, 86400 * 365
    for limit, unit, label in [
        (minute, 1, "sec"),
        (hour, minute, "min"),
        (day, hour, "hour"),
        (week, day, "day"),
        (month, day * 7, "week"),
        (year, day * 30, "month"),
        (float("inf"), day * 365, "year"),
    ]:
        if seconds < limit:
            n = max(1, int(seconds // unit))
            return f"{n} {label}" if n == 1 else f"{n} {label}s"
    return ""


def local_stamp(epoch: float) -> str:
    """An absolute timestamp in this machine's local time, for hover text.

    Epochs are absolute, so a peer's timestamp converts correctly here even
    though it was taken under a different clock and time zone.
    """
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else ""


def os_label() -> str:
    return {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform)


# ── git ───────────────────────────────────────────────────────────────────────


def git(args: list[str], cwd: Path) -> str:
    """Run git; return stdout with trailing newlines removed.

    The decode is pinned to UTF-8 rather than left to `text=True`, which would
    use the locale codepage — cp1251 on a Russian-locale Windows peer. Git emits
    commit subjects and branch names as raw UTF-8 and, unlike paths, does not
    escape them, so a Cyrillic subject would come back as mojibake, and one
    containing a byte cp1251 leaves undefined would raise UnicodeDecodeError and
    take the whole peer scan down with it. `errors="replace"` degrades a
    genuinely non-UTF-8 message to U+FFFD instead.

    NOTE: we cannot use .strip() — porcelain output's first line can legally
    start with a space (X=' ' for unstaged-only changes), and a blanket strip
    would corrupt the column alignment.
    """
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


def git_z(args: list[str], cwd: Path) -> list[str]:
    """Run a `-z` git listing command and return its NUL-separated fields.

    Without -z, git escapes non-ASCII bytes into octal and wraps the path in
    quotes, so a Cyrillic or accented filename comes back as a name no
    filesystem call can resolve — the file then silently drops out of every
    mtime and line count. -z also removes the "what if a filename contains a
    newline" question.
    """
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True)
    if r.returncode != 0:
        return []
    return [f.decode("utf-8", "replace") for f in r.stdout.split(b"\0") if f]


def porcelain_entries(repo: Path) -> list[tuple[str, str]]:
    """Return [(XY status, path)] from `git status --porcelain -z`.

    Under -z a rename or copy emits its destination record followed by the
    origin path as a field of its own, so that extra field has to be consumed
    rather than read as another entry.
    """
    fields = git_z(["status", "--porcelain", "-z"], repo)
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(fields):
        record = fields[i]
        i += 1
        if len(record) < 3:
            continue
        code, path = record[:2], record[3:]
        if "R" in code or "C" in code:
            i += 1  # the origin path rides along as the next field
        entries.append((code, path))
    return entries


def find_repos(root: Path, depth: int) -> list[Path]:
    """Walk `root` up to `depth` levels and return directories containing `.git`.

    Pure Python so it behaves identically on Linux, macOS, and Windows (where
    `find.exe` is a line-filter, not a directory walker).
    """
    repos: list[Path] = []
    root = root.resolve()
    skip_names = {"_archive", "node_modules"}
    for dirpath, dirnames, _ in os.walk(root):
        cur = Path(dirpath)
        try:
            cur_depth = len(cur.relative_to(root).parts)
        except ValueError:
            continue
        dirnames[:] = [d for d in dirnames if d not in skip_names]
        if ".git" in dirnames:
            repos.append(cur)
            dirnames[:] = []  # don't descend into a repo
            continue
        if cur_depth >= depth - 1:
            dirnames[:] = []
    repos.sort()
    return repos


def fetch_one(repo: Path) -> None:
    """Run `git fetch --quiet` in one repo. Swallow failures (offline, dead remote, stalled).

    The timeout has to be caught, not just set: subprocess.run *raises*
    TimeoutExpired rather than returning non-zero, and one stalled remote out of
    forty would otherwise abort the entire scan — which on the peer surfaces as
    a whole machine reported NOT REACHED, discarding every repo it had already
    read.
    """
    try:
        subprocess.run(["git", "-C", str(repo), "fetch", "--quiet"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def fetch_all(repos: list[Path]) -> None:
    if not repos:
        return
    with ThreadPoolExecutor(max_workers=min(16, len(repos))) as ex:
        list(ex.map(fetch_one, repos))


def pull_one(repo: Path) -> bool:
    """Attempt fast-forward pull. Return True on success.

    --ff-only refuses to create a merge commit if the branch has diverged
    (local has unpushed commits AND remote has inbound commits), so this is
    safe to run unconditionally on the eligible set. A stalled pull is caught
    for the same reason as in fetch_one — it raises rather than returning.
    """
    try:
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only", "--quiet"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


ORIGIN_SLUG = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def origin_slug(repo: Path) -> str | None:
    """Return 'OWNER/REPO' parsed from the repo's `origin` URL, or None."""
    m = ORIGIN_SLUG.search(git(["remote", "get-url", "origin"], repo))
    return f"{m['owner']}/{m['repo']}" if m else None


def open_issue_count(slug: str) -> int | None:
    """Return the count of open issues (PRs excluded) on the repo's OWN fork.

    Targets the `origin` slug explicitly with `--repo` — without it, `gh`
    auto-resolves a fork to its `upstream` parent and would report the parent's
    issues instead of the user's. Returns None on any failure — gh not
    installed, not authenticated, issues disabled on the fork, or unparseable
    output — so the caller can leave the count unknown rather than show a bogus
    0 or someone else's count. A machine whose `gh` is unauthenticated
    therefore contributes nothing here, and the other machine's answer stands.
    """
    try:
        r = subprocess.run(
            ["gh", "issue", "list", "--repo", slug, "--state", "open", "--limit", "200", "--json", "number"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        return len(json.loads(r.stdout or "[]"))
    except json.JSONDecodeError:
        return None


# ── per-machine state ─────────────────────────────────────────────────────────


@dataclass
class RepoState:
    """One machine's view of one repo. Serialized verbatim across the SSH hop."""

    path: str  # clone path relative to that machine's PROJECTS_ROOT
    branch: str
    unpushed: int  # commits in @{upstream}..HEAD
    behind: int  # commits in HEAD..@{upstream}, as counted before any auto-pull
    pulled: bool  # a `git pull --ff-only` succeeded after state collection
    uncommitted: int  # porcelain entry count
    lines_added: int
    lines_deleted: int
    oldest_epoch: float  # oldest pending file mtime or unpushed commit; 0 if none
    changes: list[str]  # "XY path" porcelain entries
    commits: list[str]  # "hash subject" for @{upstream}..HEAD
    open_issues: int | None  # via `gh` on that machine; None when it could not answer

    @property
    def has_work(self) -> bool:
        return bool(self.uncommitted or self.unpushed or self.behind)

    @classmethod
    def from_dict(cls, d: dict) -> "RepoState":
        return cls(**d)


@dataclass
class MachineSnapshot:
    """Everything one machine reports about itself in a single scan."""

    name: str
    os_label: str
    projects_root: str
    scanned_at: float
    scanned_count: int  # owned repos discovered, before the pending-work filter
    repos: dict[str, RepoState] = field(default_factory=dict)  # keyed by OWNER/REPO
    status: str = "ok"  # "ok" | "unreachable"
    error: str = ""  # what went wrong, when status is not "ok"

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "MachineSnapshot":
        repos = {slug: RepoState.from_dict(r) for slug, r in d.pop("repos", {}).items()}
        return cls(repos=repos, **d)

    @classmethod
    def unreachable(cls, name: str, error: str) -> "MachineSnapshot":
        return cls(name=name, os_label="", projects_root="", scanned_at=0.0,
                   scanned_count=0, status="unreachable", error=error)


def collect_state(repo: Path, rel: str) -> RepoState:
    branch = git(["symbolic-ref", "--short", "HEAD"], repo) or "(detached)"
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], repo)
    commits: list[str] = []
    candidates: list[float] = []
    unpushed = behind = 0
    if upstream:
        unpushed = int(git(["rev-list", "--count", f"{upstream}..HEAD"], repo) or 0)
        behind = int(git(["rev-list", "--count", f"HEAD..{upstream}"], repo) or 0)
        if unpushed:
            log = git(["log", f"{upstream}..HEAD", "--format=%h %s"], repo)
            commits = [l for l in log.splitlines() if l]
            # %ct = committer epoch; the last line is the oldest commit, since log is newest-first.
            cts = git(["log", f"{upstream}..HEAD", "--format=%ct"], repo).splitlines()
            if cts:
                candidates.append(float(cts[-1]))

    entries = porcelain_entries(repo)
    for _, path in entries:
        try:
            candidates.append((repo / path).stat().st_mtime)
        except (FileNotFoundError, OSError):
            pass  # deleted in workdir; no mtime recoverable

    # Line-count diff across tracked files (staged + unstaged combined). Binary
    # files show "-\t-\tpath" in --numstat and fail the int() below, which is
    # what skips them. Only the two integers are read, so a quoted path here is
    # harmless and -z (whose rename records carry extra fields) buys nothing.
    lines_added = lines_deleted = 0
    for line in git(["diff", "HEAD", "--numstat"], repo).splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            lines_added += int(parts[0])
            lines_deleted += int(parts[1])
        except ValueError:
            pass
    # Untracked files: `git diff` doesn't see them. Treat each as pure additions —
    # use `git ls-files` so .gitignore is respected (untracked dirs are recursed).
    # Skip binary content (NUL-byte sniff) and very large files (>1 MB).
    for path in git_z(["ls-files", "--others", "--exclude-standard", "-z"], repo):
        full = repo / path
        try:
            if not full.is_file() or full.stat().st_size > 1_000_000:
                continue
            with full.open("rb") as f:
                head = f.read(8192)
            if b"\x00" in head:
                continue
            with full.open("rb") as f:
                lines_added += sum(1 for _ in f)
        except OSError:
            pass

    return RepoState(
        path=rel, branch=branch, unpushed=unpushed, behind=behind, pulled=False,
        uncommitted=len(entries), lines_added=lines_added, lines_deleted=lines_deleted,
        oldest_epoch=min(candidates) if candidates else 0.0,
        changes=[f"{code} {path}" for code, path in entries], commits=commits, open_issues=None,
    )


def discover_owned(projects_root: Path, github_user: str, depth: int) -> list[tuple[Path, str, str]]:
    """Return [(repo_path, rel_to_root, slug)] for repos whose origin matches github_user."""
    owner_pat = re.compile(rf"github\.com[:/]{re.escape(github_user)}/")
    owned: list[tuple[Path, str, str]] = []
    for repo in find_repos(projects_root, depth):
        # Forward slashes everywhere (PurePath.as_posix) — on Windows the native
        # separator is a backslash, which would make the same repo look like a
        # different one when the two machines' paths are compared in a report.
        rel = repo.relative_to(projects_root).as_posix()
        if rel in EXCLUDED:
            continue
        origin = git(["remote", "get-url", "origin"], repo)
        if not owner_pat.search(origin):
            continue
        slug = origin_slug(repo)
        if slug:
            owned.append((repo, rel, slug))
    return owned


def scan_machine(name: str, projects_root: Path, github_user: str, depth: int) -> MachineSnapshot:
    """Fetch, read, auto-pull and issue-count every owned repo on this machine."""
    owned = discover_owned(projects_root, github_user, depth)
    print(f"[{name}] fetching {len(owned)} repos...", file=sys.stderr)
    fetch_all([repo for repo, _, _ in owned])

    states = {slug: collect_state(repo, rel) for repo, rel, slug in owned}
    by_slug = {slug: repo for repo, _, slug in owned}

    # Pull repos with inbound commits and no uncommitted changes. `behind` is
    # intentionally left as counted, so the report can say "4 pulled" rather
    # than silently showing nothing where four commits arrived.
    eligible = [slug for slug, st in states.items() if st.behind and not st.uncommitted]
    if eligible:
        print(f"[{name}] pulling {len(eligible)} clean repo(s)...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=min(16, len(eligible))) as ex:
            for slug, ok in zip(eligible, ex.map(lambda s: pull_one(by_slug[s]), eligible)):
                states[slug].pulled = ok

    # Issue counts for every owned repo, not just the pending-work set — a repo
    # with open issues but a clean, pushed tree earns a place in the report on
    # issues alone, so the count must be known before the display filter runs.
    if states:
        print(f"[{name}] counting open issues for {len(states)} repo(s)...", file=sys.stderr)
        slugs = list(states)
        with ThreadPoolExecutor(max_workers=min(16, len(slugs))) as ex:
            for slug, count in zip(slugs, ex.map(open_issue_count, slugs)):
                states[slug].open_issues = count

    return MachineSnapshot(
        # as_posix so a Windows root reads `D:/projects` in the report, matching
        # how it is written in config.env and how every repo path is rendered.
        name=name, os_label=os_label(), projects_root=projects_root.as_posix(),
        scanned_at=time.time(), scanned_count=len(owned), repos=states,
    )


# ── the peer machine ──────────────────────────────────────────────────────────


def peer_name(peer_ssh: str) -> str:
    """Display name for a peer that never answered: the host, minus any domain."""
    host = peer_ssh.rsplit("@", 1)[-1]
    return host.split(".", 1)[0] or host


def scan_peer(peer_ssh: str, peer_python: str, source: bytes) -> MachineSnapshot:
    """Run this same script on the peer over SSH and parse the snapshot it prints.

    The script is piped into `python -` rather than copied to the far side, so
    there is no temp file to clean up, nothing to install, and no way for the
    two ends to run different versions of the scan.

    Every one of ssh's three handles is a real temporary file rather than a pipe,
    which `capture_output=True` and `input=` would give it. Measured on the
    Windows peer 2026-09-14: inside an sshd session, ssh.exe with pipe handles
    hangs on any stdin at all (18 bytes the same as 53 KB), while the identical
    call with file handles returns in 0.2s. From an ordinary console there it
    works, so this only bites a run of this skill from a remote shell — but file
    handles are what has been verified on that machine in both contexts, and
    pipes have not. `git` and `gh` are unaffected and keep using pipes; this is
    ssh.exe specifically.
    """
    name = peer_name(peer_ssh)
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={PEER_CONNECT_TIMEOUT}",
           peer_ssh, f"{peer_python} - --json"]
    print(f"[{name}] scanning over ssh...", file=sys.stderr)
    try:
        with tempfile.TemporaryFile() as fin, tempfile.TemporaryFile() as fout, tempfile.TemporaryFile() as ferr:
            fin.write(source)
            fin.seek(0)
            code = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr, timeout=PEER_TIMEOUT).returncode
            fout.seek(0)
            ferr.seek(0)
            out, err_bytes = fout.read(), ferr.read()
    except subprocess.TimeoutExpired:
        return MachineSnapshot.unreachable(name, f"no answer within {PEER_TIMEOUT}s")
    except OSError as e:
        return MachineSnapshot.unreachable(name, str(e))

    err = err_bytes.decode("utf-8", "replace").strip()
    if code != 0:
        detail = next((l for l in reversed(err.splitlines()) if l.strip()), f"exit status {code}")
        return MachineSnapshot.unreachable(name, detail)
    try:
        return MachineSnapshot.from_dict(json.loads(out.decode("utf-8", "replace")))
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        return MachineSnapshot.unreachable(name, f"unreadable snapshot: {e}")


# ── merging the machines ──────────────────────────────────────────────────────


@dataclass
class RepoRow:
    """One repo as the report shows it: its identity, plus each machine's view."""

    slug: str
    name: str  # the clone path on the nearest machine that has it — what the user calls it
    open_issues: int | None
    sort_epoch: float
    states: dict[str, RepoState | None]  # machine name -> state, None where absent
    description: str = ""

    @property
    def has_work(self) -> bool:
        return any(st.has_work for st in self.states.values() if st)


def merge(snapshots: list[MachineSnapshot]) -> list[RepoRow]:
    """Fold the machines' snapshots into one row per repo, keyed by origin slug.

    Slug is the identity because the clone path differs per machine. The name
    shown is the clone path rather than the GitHub repo name, because those two
    can disagree (`claude-code-common` is checked out as `claude`) and the local
    folder is what the user calls it; machines are ordered local-first, so the
    name comes from this machine wherever it has the repo.

    Open issues are a property of the repo rather than of a machine, so the
    first machine that could answer supplies the count — an unauthenticated
    `gh` on one machine does not blank the column.
    """
    slugs: list[str] = []
    for snap in snapshots:
        for slug in snap.repos:
            if slug not in slugs:
                slugs.append(slug)

    rows: list[RepoRow] = []
    for slug in slugs:
        states = {snap.name: snap.repos.get(slug) for snap in snapshots}
        present = [st for st in states.values() if st]
        issues = next((st.open_issues for st in present if st.open_issues is not None), None)
        rows.append(RepoRow(
            slug=slug, name=present[0].path if present else slug.split("/", 1)[1], open_issues=issues,
            sort_epoch=max((st.oldest_epoch for st in present), default=0.0), states=states,
        ))

    # Keep repos with something to report: pending work on some machine, or open
    # issues. Sort by AGE ascending — freshest pending work first, oldest last —
    # which sorting the epoch descending achieves, since age = now - epoch.
    rows = [r for r in rows if r.has_work or r.open_issues]
    rows.sort(key=lambda r: r.sort_epoch, reverse=True)
    return rows


# ── the terminal table ────────────────────────────────────────────────────────

COLUMNS = [
    ("PROJECT", "project"),
    ("MACHINE", "machine"),
    ("BRANCH", "branch"),
    ("UNPUSHED", "unpushed"),
    ("REMOTE", "remote"),
    ("LOCAL", "local"),
    ("AGE", "age"),
    ("ISSUES", "issues"),
    ("DESCRIPTION", "description"),
]

# Column keys whose HEADER renders centered (values stay left-aligned).
CENTERED_HEADERS = {"unpushed", "remote", "local", "age", "issues"}

DEFAULT_BRANCHES = {"main", "master"}

PENDING_DESCRIPTION = "<analyze below>"


@dataclass
class DisplayGroup:
    """One repo's block of the table: a line per machine, sharing a description."""

    rows: list[dict[str, str]]
    description: str


def machine_cell(name: str, state: RepoState | None) -> str:
    """The MACHINE cell, carrying the machine's state when it has no metrics.

    'clean' and 'absent' are different facts and a blank cell would say both at
    once, so each gets a word of its own. A machine that was never reached has
    no row at all — the summary above the table names it once, with the error,
    which beats repeating it under every repo.
    """
    if state is None:
        return f"{name} absent"
    if not state.has_work:
        return f"{name} clean"
    return name


def build_groups(rows: list[RepoRow], reached: list[str]) -> list[DisplayGroup]:
    now = time.time()
    groups: list[DisplayGroup] = []
    for row in rows:
        lines: list[dict[str, str]] = []
        for machine in reached:
            state = row.states.get(machine)
            first = not lines
            cells = {
                "project": row.name if first else "",
                "machine": machine_cell(machine, state),
                "branch": "", "unpushed": "", "remote": "", "local": "", "age": "",
                "issues": str(row.open_issues) if first and row.open_issues else "",
            }
            if state:
                if state.branch not in DEFAULT_BRANCHES:
                    cells["branch"] = state.branch
                if state.unpushed:
                    cells["unpushed"] = str(state.unpushed)
                if state.behind:
                    cells["remote"] = f"{state.behind} ✓" if state.pulled else str(state.behind)
                cells["local"] = format_local(state.uncommitted, state.lines_added, state.lines_deleted)
                if state.oldest_epoch:
                    cells["age"] = human_age(now - state.oldest_epoch)
            lines.append(cells)
        groups.append(DisplayGroup(rows=lines, description=row.description))
    return groups


def visible_columns(groups: list[DisplayGroup], machine_count: int) -> list[tuple[str, str]]:
    """Keep PROJECT, plus every column that some cell actually fills.

    MACHINE is dropped on a single-machine run, where it would repeat one name
    down the whole table and say nothing.
    """
    filled = {key for g in groups for line in g.rows for key, value in line.items() if value}
    if any(g.description for g in groups):
        filled.add("description")
    if machine_count > 1:
        filled.add("machine")
    else:
        filled.discard("machine")
    return [(h, k) for h, k in COLUMNS if k == "project" or k in filled]


def target_width(config: Path) -> int:
    """Total table width to fill. Resolved in order: GHS_WIDTH env var, the
    GHS_WIDTH line in config.env, then the detected terminal width (120 if that
    can't be queried — e.g. stdout is a pipe under the Bash tool).

    The DESCRIPTION column stretches to consume whatever this width leaves after
    the fixed columns, so the table spans the full target width.
    """
    val = config_value(config, "GHS_WIDTH")
    if val and val.isdigit():
        return int(val)
    return shutil.get_terminal_size((120, 24)).columns


def print_table(groups: list[DisplayGroup], cols: list[tuple[str, str]], width: int) -> None:
    headers = [h for h, _ in cols]
    keys = [k for _, k in cols]
    desc_i = keys.index("description") if "description" in keys else None

    # Column width = max(header, longest value). The "│ {cell} │" rendering
    # already provides one space of padding on each side, so no extra math.
    widths = [
        max(len(h), max((len(g.rows[i][k]) for g in groups for i in range(len(g.rows))), default=0))
        for h, k in cols if k != "description"
    ]
    if desc_i is not None:
        widths.insert(desc_i, len(headers[desc_i]))

    # DESCRIPTION is the elastic column: it takes whatever width is left after
    # the fixed columns so the table fills the full target width — expanding to
    # pad short text out to the right edge, wrapping text too long to fit. The
    # floor keeps it readable on very narrow screens (the table overflows the
    # target instead of crushing the column below it).
    table_chrome = 3 * len(cols) + 1  # "│ " + " │ "*(n-1) + " │" per row line
    if desc_i is not None:
        others = sum(w for i, w in enumerate(widths) if i != desc_i)
        widths[desc_i] = max(width - others - table_chrome, DESC_MIN_WIDTH, len(headers[desc_i]))

    bar = lambda left, mid, right: left + mid.join("─" * (w + 2) for w in widths) + right
    header_cells = [f"{h:^{w}}" if k in CENTERED_HEADERS else f"{h:<{w}}"
                    for h, k, w in zip(headers, keys, widths)]
    print(bar("┌", "┬", "┐"))
    print("│ " + " │ ".join(header_cells) + " │")
    print(bar("├", "┼", "┤"))
    for group in groups:
        # The description belongs to the repo, not to a machine, so it wraps
        # down the group's machine lines and extends the group when it is longer.
        desc = textwrap.wrap(group.description, widths[desc_i]) if desc_i is not None and group.description else []
        for i in range(max(len(group.rows), len(desc))):
            line = group.rows[i] if i < len(group.rows) else {}
            cells = [(desc[i] if i < len(desc) else "") if ci == desc_i else line.get(keys[ci], "")
                     for ci in range(len(cols))]
            print("│ " + " │ ".join(f"{c:<{w}}" for c, w in zip(cells, widths)) + " │")
    print(bar("└", "┴", "┘"))


def print_machine_summary(snapshots: list[MachineSnapshot]) -> None:
    now = time.time()
    for snap in snapshots:
        if snap.status != "ok":
            print(f"{snap.name}: NOT REACHED — {snap.error}")
            continue
        age = human_age(now - snap.scanned_at)
        when = f"{age} ago" if age else "just now"
        print(f"{snap.name}: {snap.os_label} · {snap.projects_root} · {snap.scanned_count} repos · scanned {when}")


def print_detail(rows: list[RepoRow], multi: bool) -> None:
    """Per-repo uncommitted and unpushed listings — the raw material for the
    one-line descriptions Claude writes in SKILL.md step 3.

    Porcelain status is XY where X (staged) / Y (unstaged) may be a space — swap
    spaces for a center dot so the columns line up visually.
    """
    dirty = [(r, m, s) for r in rows for m, s in r.states.items() if s and s.changes]
    if dirty:
        print("\nUncommitted changes:")
        for row, machine, state in dirty:
            print(f"\n{row.name}{f' [{machine}]' if multi else ''}:")
            for line in state.changes:
                print(f"  {line[:2].replace(' ', '·')}{line[2:]}")

    pending = [(r, m, s) for r in rows for m, s in r.states.items() if s and s.commits]
    if pending:
        print("\nUnpushed commits (for Claude to summarize per repo):")
        for row, machine, state in pending:
            print(f"\n{row.name}{f' [{machine}]' if multi else ''} ({len(state.commits)}):")
            for line in state.commits:
                print(f"  {line}")


# ── the HTML report ───────────────────────────────────────────────────────────

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark;
           --bg:#fbfbfa; --fg:#22201d; --mut:#6b6660; --line:#e3e0da; --card:#fff; --accent:#7a5c3e;
           --add:#2f6f3e; --del:#a03530; --warn:#a05a12; --chip:rgba(122,92,62,.10); }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#191817; --fg:#e6e3de; --mut:#98938c; --line:#333029; --card:#211f1d; --accent:#c8a678;
             --add:#7fbf8a; --del:#e08b85; --warn:#d9a05a; --chip:rgba(200,166,120,.13); }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
          font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
  a {{ color:inherit; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  header.top {{ border-bottom:1px solid var(--line); padding:18px 26px 14px; }}
  header.top h1 {{ font-size:16px; font-weight:600; margin:0 0 3px; }}
  header.top p.sub {{ margin:0 0 12px; color:var(--mut); font-size:13px; }}
  .machines {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .machine {{ border:1px solid var(--line); border-radius:8px; background:var(--card);
              padding:7px 12px; font-size:12.5px; display:flex; align-items:baseline; gap:8px; }}
  .machine.bad {{ border-color:var(--warn); }}
  .mname {{ font-weight:650; }}
  .mmeta, .mtime {{ color:var(--mut); }}
  .merr {{ color:var(--warn); font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; }}
  /* align-items:start, not stretch: opening one card's file list would
     otherwise grow every other card in its row. */
  main {{ padding:22px 26px 64px; display:grid; gap:14px; align-items:start;
          grid-template-columns:repeat(auto-fill,minmax(430px,1fr)); }}
  article.repo {{ border:1px solid var(--line); border-radius:9px; background:var(--card); padding:12px 14px; }}
  article.repo > header {{ display:flex; align-items:baseline; gap:9px; margin-bottom:6px; }}
  .rname {{ font-weight:650; font-size:14.5px; }}
  .issues {{ margin-left:auto; color:var(--accent); background:var(--chip);
             border-radius:20px; padding:1px 9px; font-size:11.5px; font-weight:600; white-space:nowrap; }}
  p.desc {{ margin:0 0 9px; font-size:13.5px; }}
  p.desc.pending {{ color:var(--mut); font-style:italic; }}
  .mrow {{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; padding:3px 0;
           border-top:1px solid var(--line); font-size:12.5px; }}
  .mtag {{ font-weight:600; min-width:58px; }}
  .mpath {{ color:var(--mut); font-size:11.5px;
            font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .m {{ color:var(--mut); }}
  .m b {{ color:var(--fg); font-weight:600; }}
  .add {{ color:var(--add); font-weight:600; }}
  .del {{ color:var(--del); font-weight:600; }}
  .state {{ color:var(--mut); font-style:italic; }}
  .state.gone {{ color:var(--warn); font-style:normal; }}
  details {{ margin:5px 0 0 66px; }}
  details summary {{ cursor:pointer; color:var(--mut); font-size:12px; }}
  /* Deep paths wrap onto a hanging indent rather than opening a horizontal
     scrollbar inside every file list. The indent is per entry, so each entry is
     its own block — text-indent on one shared block would outdent the first
     line only, making every later entry read as a wrapped continuation. */
  .listing {{ margin:5px 0 8px; padding:8px 10px; background:var(--chip); border-radius:6px;
              font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
              font-size:11.5px; line-height:1.45; }}
  .listing div {{ white-space:pre-wrap; overflow-wrap:anywhere; padding-left:3ch; text-indent:-3ch; }}
  p.none {{ padding:40px 26px; color:var(--mut); font-size:13.5px; max-width:80ch; }}
</style>
<header class="top">
  <h1>{title}</h1>
  <p class="sub">{sub}</p>
  <div class="machines">{machines}</div>
</header>
{body}
"""


def esc(text: str) -> str:
    return html.escape(str(text))


def machine_card(snap: MachineSnapshot, now: float) -> str:
    if snap.status != "ok":
        return (f'<div class="machine bad"><span class="mname">{esc(snap.name)}</span>'
                f'<span class="mmeta">not reached</span>'
                f'<span class="merr">{esc(snap.error)}</span></div>')
    age = human_age(now - snap.scanned_at)
    return (f'<div class="machine"><span class="mname">{esc(snap.name)}</span>'
            f'<span class="mmeta">{esc(snap.os_label)} · {esc(snap.projects_root)} · '
            f'{snap.scanned_count} repos</span>'
            f'<span class="mtime" title="{esc(local_stamp(snap.scanned_at))}">'
            f'scanned {esc(age) + " ago" if age else "just now"}</span></div>')


def metric_html(state: RepoState, now: float) -> str:
    parts: list[str] = []
    if state.branch not in DEFAULT_BRANCHES:
        parts.append(f'<span class="m">on <b>{esc(state.branch)}</b></span>')
    if state.unpushed:
        parts.append(f'<span class="m"><b>{state.unpushed}</b> ahead</span>')
    if state.behind:
        parts.append(f'<span class="m"><b>{state.behind}</b> {"pulled" if state.pulled else "behind"}</span>')
    if state.uncommitted:
        lines = ""
        if state.lines_added:
            lines += f' <span class="add">+{state.lines_added}</span>'
        if state.lines_deleted:
            lines += f' <span class="del">&minus;{state.lines_deleted}</span>'
        noun = "file" if state.uncommitted == 1 else "files"
        parts.append(f'<span class="m"><b>{state.uncommitted}</b> {noun}{lines}</span>')
    if state.oldest_epoch:
        parts.append(f'<span class="m" title="oldest pending change: {esc(local_stamp(state.oldest_epoch))}">'
                     f'{esc(human_age(now - state.oldest_epoch))} ago</span>')
    return "".join(parts)


def machine_row_html(machine: str, state: RepoState | None, repo_name: str, now: float) -> str:
    tag = f'<span class="mtag">{esc(machine)}</span>'
    if state is None:
        return f'<div class="mrow">{tag}<span class="state gone">not cloned here</span></div>'
    # The clone path only earns a place when it differs from the repo's own name;
    # otherwise it repeats the card's title on every row.
    path = f'<span class="mpath">{esc(state.path)}</span>' if state.path != repo_name else ""
    body = metric_html(state, now) if state.has_work else '<span class="state">clean</span>'
    out = f'<div class="mrow">{tag}{path}{body}</div>'
    # The metrics row above already carries both counts, so the summaries name
    # what is inside rather than repeating the number.
    if state.changes:
        entries = (f"{l[:2].replace(' ', '·')}{l[2:]}" for l in state.changes)
        out += f'<details><summary>uncommitted files</summary>{listing_html(entries)}</details>'
    if state.commits:
        out += f'<details><summary>unpushed commits</summary>{listing_html(state.commits)}</details>'
    return out


def listing_html(entries: Iterable[str]) -> str:
    return '<div class="listing">' + "".join(f"<div>{esc(e)}</div>" for e in entries) + "</div>"


def repo_card(row: RepoRow, reached: list[str], now: float) -> str:
    head = f'<a class="rname" href="https://github.com/{esc(row.slug)}">{esc(row.name)}</a>'
    if row.open_issues:
        label = "1 open issue" if row.open_issues == 1 else f"{row.open_issues} open issues"
        head += f'<a class="issues" href="https://github.com/{esc(row.slug)}/issues">{label}</a>'
    desc = ""
    if row.description == PENDING_DESCRIPTION:
        desc = '<p class="desc pending">description not written</p>'
    elif row.description:
        desc = f'<p class="desc">{esc(row.description)}</p>'
    rows = "".join(machine_row_html(m, row.states.get(m), row.name, now) for m in reached)
    return f'<article class="repo"><header>{head}</header>{desc}{rows}</article>'


def write_html(path: Path, rows: list[RepoRow], snapshots: list[MachineSnapshot], owner: str) -> None:
    now = time.time()
    reached = [s for s in snapshots if s.status == "ok"]
    names = [s.name for s in reached]
    total = len({slug for s in reached for slug in s.repos})
    title = f"Repo status — {owner}"
    if rows:
        sub = f"{len(rows)} of {total} repos have pending work or open issues"
        body = "<main>" + "".join(repo_card(r, names, now) for r in rows) + "</main>"
    else:
        scanned = " and ".join(f"{s.scanned_count} on {s.name}" for s in reached) or "none"
        sub = "Nothing pending"
        body = (f'<p class="none">Every repo is clean, pushed, and has no open issues — '
                f'{esc(scanned)} scanned. A repo appears here only when it has uncommitted changes, '
                f'unpushed or inbound commits, or an open issue.</p>')
    page = PAGE.format(title=esc(title), sub=esc(sub),
                       machines="".join(machine_card(s, now) for s in snapshots), body=body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


# ── config and paths ──────────────────────────────────────────────────────────


def script_path() -> Path | None:
    """This file's real path, or None when the script arrived on stdin.

    The peer invocation pipes this file into `python -`, which sets __file__ to
    the literal string "<stdin>" — a name that resolves against the current
    directory and points at nothing.
    """
    p = Path(__file__)
    return p.resolve() if p.is_file() else None


def skill_dir() -> Path:
    here = script_path()
    return here.parent.parent if here else Path.home() / ".claude" / "skills" / "github-status"


def config_file() -> Path:
    """config/config.env beside this script, else the conventional install path.

    The fallback is what lets the piped-over-SSH copy on the peer find that
    machine's own PROJECTS_ROOT without being told it from this side, so the two
    machines' roots never have to be kept in sync in two places.
    """
    local = skill_dir() / "config" / "config.env"
    return local if local.exists() else Path.home() / ".claude" / "skills" / "github-status" / "config" / "config.env"


def tmp_dir() -> Path:
    """The gitignored tmp/ of the repo this skill is checked out into.

    ~/.claude/skills is a symlink into the dotfiles clone, so resolving this
    file lands inside that repo. A skill copied rather than symlinked has no
    repo above it, and its artifacts go beside the skill instead.
    """
    base = skill_dir()
    for parent in base.parents:
        if (parent / ".git").exists():
            return parent / "tmp"
    return base / "tmp"


def config_value(config: Path, key: str) -> str | None:
    """Resolve a setting: the `key` env var first, else its `KEY=value` line in
    config.env. Returns None if neither is present."""
    if val := os.environ.get(key):
        return val
    if config.exists():
        for line in config.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def flag_value(argv: list[str], name: str) -> str | None:
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            return argv[i + 1]
    return None


# ── modes ─────────────────────────────────────────────────────────────────────


def resolve_root(config: Path) -> Path | None:
    root = config_value(config, "PROJECTS_ROOT")
    if not root:
        print(
            f"ERROR: PROJECTS_ROOT is not set and {config} is missing.\n"
            "Run the github-status skill (/github-status) — it will prompt for\n"
            "the projects root and write the config file before invoking this.",
            file=sys.stderr,
        )
        return None
    path = Path(root).expanduser()
    if not path.is_dir():
        print(f"ERROR: PROJECTS_ROOT does not exist: {path}", file=sys.stderr)
        return None
    return path


def github_user() -> str:
    return os.environ.get("GITHUB_USER", "AnotherSava")


def scan_this_machine(config: Path) -> MachineSnapshot | None:
    """This machine's snapshot, or None when PROJECTS_ROOT is unusable.

    Both the local half of a two-machine run and the --json peer invocation go
    through here. They are the two ends of one report, and the --json end runs on
    the machine nobody is watching, so resolving these defaults twice is how the
    two would come to scan under different rules without anyone noticing.
    """
    root = resolve_root(config)
    if root is None:
        return None
    name = config_value(config, "MACHINE_NAME") or socket.gethostname().split(".", 1)[0]
    return scan_machine(name, root, github_user(), int(os.environ.get("ROOT_DEPTH", "4")))


def gather(config: Path) -> list[MachineSnapshot] | None:
    """Scan this machine and, when PEER_SSH is configured, the peer — together.

    Both scans fetch, pull and query `gh` over every repo they own, so running
    them concurrently costs the slower of the two rather than their sum.
    """
    # Fail on an unusable PROJECTS_ROOT before anything is spawned — the peer
    # scan is minutes long, and there is nothing to merge its result into.
    # scan_this_machine resolves it again below, silently, once it is known good.
    if resolve_root(config) is None:
        return None

    peer_ssh = config_value(config, "PEER_SSH")
    source = script_path().read_bytes() if peer_ssh and script_path() else None
    if peer_ssh and source is None:
        print("WARNING: PEER_SSH is set but this script did not come from a file, "
              "so it cannot be sent to the peer — scanning this machine only.", file=sys.stderr)
        peer_ssh = None

    if not peer_ssh:
        local_only = scan_this_machine(config)
        return None if local_only is None else [local_only]

    peer_python = config_value(config, "PEER_PYTHON") or "python3"
    with ThreadPoolExecutor(max_workers=2) as ex:
        local = ex.submit(scan_this_machine, config)
        remote = ex.submit(scan_peer, peer_ssh, peer_python, source)
        local_result = local.result()
        if local_result is None:
            return None
        snapshots = [local_result, remote.result()]
    backfill_issue_counts(snapshots)
    return snapshots


def backfill_issue_counts(snapshots: list[MachineSnapshot]) -> None:
    """Ask this machine about peer-only repos the peer could not answer for.

    `gh issue list --repo OWNER/REPO` needs no clone, so a repo that exists only
    on a peer whose `gh` is unauthenticated can still be counted from here.
    Without this, such a repo reports None; if it is otherwise clean, the display
    filter then drops it and the report never mentions it at all.

    Only peer-only repos are retried — for one this machine also has, its own
    `gh` already tried and a second identical call would return the same answer.
    Writing back into the snapshots rather than onto the merged rows keeps the
    state file authoritative, so a later --report re-merging from disk sees the
    same counts. `snapshots[0]` is this machine, as gather() builds it.
    """
    local, peers = snapshots[0], snapshots[1:]
    unanswered = sorted({
        slug for peer in peers for slug, state in peer.repos.items()
        if state.open_issues is None and slug not in local.repos
    })
    if not unanswered:
        return
    print(f"[{local.name}] counting open issues for {len(unanswered)} repo(s) the peer could not answer for...",
          file=sys.stderr)
    with ThreadPoolExecutor(max_workers=min(16, len(unanswered))) as ex:
        for slug, count in zip(unanswered, ex.map(open_issue_count, unanswered)):
            for peer in peers:
                if slug in peer.repos:
                    peer.repos[slug].open_issues = count


def render(snapshots: list[MachineSnapshot], rows: list[RepoRow], width: int) -> None:
    print_machine_summary(snapshots)
    print()
    reached = [s.name for s in snapshots if s.status == "ok"]
    groups = build_groups(rows, reached)
    if not groups:
        scanned = ", ".join(f"{s.scanned_count} on {s.name}" for s in snapshots if s.status == "ok") or "none"
        print(f"Nothing pending — {scanned} repos scanned, all clean, pushed, and without open issues.")
        return
    print_table(groups, visible_columns(groups, len(reached)), width)


def state_to_json(snapshots: list[MachineSnapshot], rows: list[RepoRow]) -> str:
    return json.dumps({
        "machines": [asdict(s) for s in snapshots],
        "repos": [{"slug": r.slug, "description": r.description} for r in rows],
    }, ensure_ascii=False)


def state_from_json(text: str) -> tuple[list[MachineSnapshot], list[RepoRow]]:
    data = json.loads(text)
    snapshots = [MachineSnapshot.from_dict(m) for m in data["machines"]]
    rows = merge(snapshots)
    saved = {r["slug"]: r["description"] for r in data.get("repos", [])}
    for row in rows:
        row.description = saved.get(row.slug, "")
    return snapshots, rows


def apply_descriptions(rows: list[RepoRow], text: str) -> None:
    """Fold in `{"<project>": "<one-line summary>"}`, keyed by the PROJECT cell.

    A key matching no repo is reported rather than dropped — a description
    silently going nowhere reads exactly like one that was never written.
    """
    described = json.loads(text)
    by_name = {r.name: r for r in rows}
    for name, desc in described.items():
        if name in by_name:
            by_name[name].description = desc
    unmatched = [n for n in described if n not in by_name]
    if unmatched:
        print(f"WARNING: no repo named {', '.join(unmatched)} in the report — "
              "those descriptions were dropped.", file=sys.stderr)


def main() -> int:
    # Windows consoles default to a legacy codepage (e.g. cp1251) that can't
    # encode the Unicode box-drawing characters used in the table, nor decode
    # UTF-8 JSON on stdin. Force UTF-8 on all three streams so the script works
    # identically across platforms — and so the peer's snapshot survives the hop.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    argv = sys.argv[1:]
    config = config_file()

    # Explicit width: `--width N` overrides detection/config for this run (the
    # skill detects the real terminal width and passes it, since a piped stdout
    # hides it from get_terminal_size). Fed through GHS_WIDTH so target_width
    # picks it up uniformly.
    if w := flag_value(argv, "--width"):
        if w.isdigit():
            os.environ["GHS_WIDTH"] = w

    state_path = Path(flag_value(argv, "--state") or tmp_dir() / "github-status-state.json")
    html_path = Path(flag_value(argv, "--html") or tmp_dir() / "github-status.html")

    # Peer mode: scan this machine and print the snapshot, nothing else. Every
    # progress line goes to stderr so stdout carries only the JSON.
    if "--json" in argv:
        snapshot = scan_this_machine(config)
        if snapshot is None:
            return 2
        print(snapshot.to_json())
        return 0

    # Report mode: re-read the scan rather than repeating it, so the descriptions
    # land on the state they were written from.
    if "--report" in argv:
        if not state_path.exists():
            print(f"ERROR: no state file at {state_path} — run the scan first.", file=sys.stderr)
            return 2
        snapshots, rows = state_from_json(state_path.read_text(encoding="utf-8"))
        source = flag_value(argv, "--descriptions")
        text = Path(source).read_text(encoding="utf-8") if source else sys.stdin.read()
        apply_descriptions(rows, text.strip() or "{}")
        render(snapshots, rows, target_width(config))
        owner = rows[0].slug.split("/", 1)[0] if rows else github_user()
        write_html(html_path, rows, snapshots, owner)
        print(f"\nHTML report: file:///{str(html_path).replace(os.sep, '/').lstrip('/')}")
        return 0

    snapshots = gather(config)
    if snapshots is None:
        return 2
    rows = merge(snapshots)
    for row in rows:
        if row.has_work:
            row.description = PENDING_DESCRIPTION
    render(snapshots, rows, target_width(config))
    print_detail(rows, multi=sum(s.status == "ok" for s in snapshots) > 1)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state_to_json(snapshots, rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
