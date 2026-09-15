#!/usr/bin/env python3
"""repos-status — scan every GitHub-owned clone on this machine and on its peer,
and report which ones have pending work.

A machine is scanned by walking PROJECTS_ROOT for git repos whose `origin`
belongs to GITHUB_USER, fetching each one, auto-pulling the clean ones that are
behind, and counting open issues via `gh`. The peer machine is scanned by piping
*this same file* into its interpreter over SSH (`ssh host "python - --json"`), so
the two ends can never run different versions of the scan and nothing has to be
installed or kept in sync on the far side.

Each clone is also read against the convention steps the `/adopt` skill defines,
so a repo that is behind on them is reported even when its tree is clean — a
version gap is outstanding work in that repo, and nothing else in this report
would ever mention it.

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
import importlib.util
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
from types import ModuleType

EXCLUDED: set[str] = {"notion", "claude-mermaid-fix"}

# How long to wait for the peer's whole scan. It fetches, pulls and queries `gh`
# for every repo it owns, so this is minutes-scale work, not a round trip.
PEER_TIMEOUT = 300
PEER_CONNECT_TIMEOUT = 15

# Below this the DESCRIPTION column is dropped from the terminal table rather
# than squeezed — see print_table for the measurement behind the number.
DESC_USEFUL_WIDTH = 34



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


# ── conventions (the /adopt record) ───────────────────────────────────────────


@dataclass
class ConventionState:
    """How far one clone is from the convention steps, as `/adopt` would read it.

    Per machine rather than per repo, because both halves of the answer are: the
    step set comes from that machine's own dotfiles checkout, and
    `.claude/conventions.local.tsv` is gitignored and never travels.
    """

    behind: int = 0  # steps with no line in either record file — the "N versions behind" number
    unwired: int = 0  # machine-scoped steps decided in the repo but not wired on that machine
    through: int = 0  # highest version such that every step at or below it has been decided
    recorded: bool = True  # whether a record file exists at all; False means /adopt never ran there
    pending: list[str] = field(default_factory=list)  # "v3 <title>", both kinds, ascending
    note: str = ""  # why the numbers above cannot be trusted; empty when they can

    @property
    def total(self) -> int:
        return self.behind + self.unwired

    @property
    def anything(self) -> bool:
        """Whether this clone has something to say. A note counts: an unreadable
        record is an open question, and a blank cell would read as `current`."""
        return bool(self.total or self.note)


def conventions_module() -> tuple[ModuleType | None, str]:
    """The /adopt engine from the sibling skill, or None and the reason it is missing.

    Loaded by path rather than by name: the peer runs this script from stdin, where
    there is no `__file__` to hang a relative import off, and `skill_dir()` already
    falls back to the conventional install path for exactly that case.

    Reading the record here rather than re-implementing it is the same rule the
    session-start hook follows — two readers of one format drift the day either
    gains a column, and this one would drift silently, on a machine nobody is
    watching.
    """
    path = skill_dir().parent / "adopt" / "conventions.py"
    if not path.is_file():
        # The state a peer is actually in when this fires: its dotfiles checkout predates the
        # /adopt skill. Saying so beats a bare path, which reads as a broken install.
        return None, f"no /adopt engine at {path} — this machine's dotfiles checkout may be behind"
    name = "ghs_conventions"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        # Registered before it is executed, not after: a class defined in a module missing from
        # sys.modules cannot resolve its own namespace, and the engine's NamedTuples are exactly
        # that. It surfaces as an AttributeError raised inside the standard library, nowhere
        # near the line that caused it.
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module, ""
    except BaseException as exc:  # a half-written engine must not take the whole scan down
        sys.modules.pop(name, None)
        return None, f"the /adopt engine could not be loaded ({exc})"


def read_conventions(module: ModuleType, steps: list, repo: Path) -> ConventionState | None:
    """One clone's standing against `steps`, or None where the question does not apply.

    None is returned for a repo that was never going to hold a record — someone
    else's project, or one carrying an `exempt` line — so the column stays empty
    there rather than asserting a gap. Every other way of failing to reach a number
    fills `note` instead, because a blank cell and `current` are the same blank.
    """
    root = str(repo)
    try:
        if module.is_third_party(root) is not None:
            return None
        ledger = module.read_ledger(root)
        if ledger.error:
            return ConventionState(note=module.parse_error_message(ledger))
        if ledger.exempt:
            return None
        recorded = module.decided(ledger)
        highest, latest = (max(recorded) if recorded else 0), steps[-1].version
        if highest > latest:
            # This machine's dotfiles checkout is the behind one, so its step set is
            # older than the record it is reading and every count below would be wrong.
            return ConventionState(note=f"records v{highest}, above the newest step in this machine's "
                                        f"dotfiles checkout (v{latest}) — pull the dotfiles repo there")
        pending, unwired = module.pending_steps(steps, ledger), module.unwired_machine_steps(steps, ledger)
        # One list, sorted by version, exactly as the session-start notice renders it: the two
        # kinds interleave by version and an unwired step appended after the rest reads as
        # out of order.
        entries = [(s.version, f"v{s.version} {s.title}") for s in pending]
        entries += [(s.version, f"v{s.version} {s.title} — decided in this repo, not wired here")
                    for s in unwired]
        entries.sort()
        return ConventionState(behind=len(pending), unwired=len(unwired),
                               through=module.adopted_through(steps, ledger), recorded=bool(ledger.files),
                               pending=[text for _, text in entries])
    except BaseException as exc:
        return ConventionState(note=f"the convention record could not be read ({exc})")


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
    # None where the repo holds no record and never will — see read_conventions. Defaulted so a
    # state file written before this field existed still loads under `--report`.
    conventions: ConventionState | None = None

    @property
    def has_work(self) -> bool:
        """In-flight git work. Deliberately excludes the convention gap: a description
        is owed for every machine this is true of, and an unadopted step is work nobody
        has started rather than work half done, so there is nothing to summarize."""
        return bool(self.uncommitted or self.unpushed or self.behind)

    @property
    def has_conventions_gap(self) -> bool:
        return bool(self.conventions and self.conventions.anything)

    @property
    def has_anything(self) -> bool:
        """Whether this clone has anything outstanding at all — what `clean` denies."""
        return self.has_work or self.has_conventions_gap

    @classmethod
    def from_dict(cls, d: dict) -> "RepoState":
        conv = d.pop("conventions", None)
        return cls(conventions=ConventionState(**conv) if conv else None, **d)


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
    # The convention step set this machine measured its repos against. Stated next to the
    # machine rather than next to each repo, because every gap in that machine's column is
    # relative to it and the two checkouts are routinely at different commits.
    conv_latest: int = 0  # newest step version in this machine's dotfiles checkout
    conv_sha: str = ""  # that checkout's short sha
    # Why no repo here carries a gap; empty only once a scan has measured them. The default is a
    # sentence rather than "" because `--report` re-reads a state file that may predate this
    # field, and defaulting to no-error there renders `conventions v0` — a machine that was never
    # asked, reading exactly like a fleet that is up to date.
    conv_error: str = "this scan predates the convention check; re-run it"

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

    # Conventions last: it is the only part that reads a second skill, and a failure there
    # must cost the machine its gap numbers and nothing else.
    module, conv_error = conventions_module()
    latest, sha, steps = 0, "", []
    if module is not None:
        try:
            steps = module.load_steps()
            latest, sha = (steps[-1].version if steps else 0), module.dotfiles_sha()
        except BaseException as exc:
            steps, conv_error = [], f"the convention steps could not be read ({exc})"
        if not steps and not conv_error:
            # An empty step set would leave every repo measuring as current, which is the one
            # reading a machine with no steps to measure against must not produce.
            conv_error = "the /adopt skill on this machine defines no steps"
    if steps:
        print(f"[{name}] reading the convention record of {len(states)} repo(s)...", file=sys.stderr)
        for repo, _, slug in owned:
            states[slug].conventions = read_conventions(module, steps, repo)

    return MachineSnapshot(
        # as_posix so a Windows root reads `D:/projects` in the report, matching
        # how it is written in config.env and how every repo path is rendered.
        name=name, os_label=os_label(), projects_root=projects_root.as_posix(),
        scanned_at=time.time(), scanned_count=len(owned), repos=states,
        conv_latest=latest, conv_sha=sha, conv_error=conv_error,
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
    # machine name -> its own one-line summary. Per machine rather than per repo
    # because a description describes work and work belongs to a machine: one
    # string for a repo busy on both leaves the second machine's column unexplained.
    descriptions: dict[str, str] = field(default_factory=dict)

    @property
    def has_work(self) -> bool:
        return any(st.has_work for st in self.states.values() if st)

    @property
    def conventions_gap(self) -> bool:
        return any(st.has_conventions_gap for st in self.states.values() if st)

    @property
    def conventions_total(self) -> int:
        """The widest gap any machine reports, for ordering the ageless block of the table."""
        return max((st.conventions.total for st in self.states.values() if st and st.conventions), default=0)

    def working(self, reached: list[str]) -> list[str]:
        """The reached machines with pending work — the ones a description is owed for."""
        return [m for m in reached if (st := self.states.get(m)) and st.has_work]


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

    # Keep repos with something to report: pending work on some machine, open issues,
    # or convention versions still to decide there. Sort by AGE ascending — freshest
    # pending work first, oldest last — which sorting the epoch descending achieves,
    # since age = now - epoch. A repo with no pending work has no age at all, so the
    # whole ageless tail would otherwise sit in discovery order; the widest convention
    # gap breaks that tie, putting the repos furthest behind at the top of it.
    rows = [r for r in rows if r.has_work or r.open_issues or r.conventions_gap]
    rows.sort(key=lambda r: (-r.sort_epoch, -r.conventions_total))
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
    ("CONV", "conventions"),
    ("ISSUES", "issues"),
    ("DESCRIPTION", "description"),
]

# Column keys whose HEADER renders centered (values stay left-aligned).
CENTERED_HEADERS = {"unpushed", "remote", "local", "age", "conventions", "issues"}

DEFAULT_BRANCHES = {"main", "master"}

PENDING_DESCRIPTION = "<analyze below>"


@dataclass
class DisplayGroup:
    """One repo's block of the table: a line per machine, each with its own description."""

    rows: list[dict[str, str]]


def machine_cell(name: str, state: RepoState | None) -> str:
    """The MACHINE cell, carrying the machine's state when it has no metrics.

    'clean' and 'absent' are different facts and a blank cell would say both at
    once, so each gets a word of its own. A machine that was never reached has
    no row at all — the summary above the table names it once, with the error,
    which beats repeating it under every repo.

    A clone behind on conventions is not clean: its CONV cell is filled, and the
    two sitting on one line would contradict each other.
    """
    if state is None:
        return f"{name} absent"
    if not state.has_anything:
        return f"{name} clean"
    return name


def conventions_cell(state: ConventionState | None) -> str:
    """The CONV cell: versions behind, with `+N` for steps this machine has not wired.

    `?` where the record could not be read at all — the number is unknown there, and
    leaving it blank would say `current`, which is the one answer nothing has checked.
    The report spells out all three in words; this column only has room for the count.
    """
    if state is None or not state.anything:
        return ""
    if state.note:
        return "?"
    return (str(state.behind) if state.behind else "") + (f"+{state.unwired}" if state.unwired else "")


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
                "conventions": conventions_cell(state.conventions if state else None),
                "description": row.descriptions.get(machine, ""),
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
                    cells["age"] = compact_age(now - state.oldest_epoch)
            lines.append(cells)
        groups.append(DisplayGroup(rows=lines))
    return groups


def visible_columns(groups: list[DisplayGroup], machine_count: int) -> list[tuple[str, str]]:
    """Keep PROJECT, plus every column that some cell actually fills.

    MACHINE is dropped on a single-machine run, where it would repeat one name
    down the whole table and say nothing.
    """
    filled = {key for g in groups for line in g.rows for key, value in line.items() if value}
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
    # pad short text out to the right edge, wrapping text too long to fit.
    table_chrome = 3 * len(cols) + 1  # "│ " + " │ "*(n-1) + " │" per row line
    budget = 0
    dropped_description = False
    if desc_i is not None:
        others = sum(w for i, w in enumerate(widths) if i != desc_i)
        budget = width - others - table_chrome
        # Below DESC_USEFUL_WIDTH the column stops being a column and becomes a
        # ribbon: a one-line summary wraps to four or five rows, and the table
        # grows past three times the height of the report it summarises —
        # measured at 122 lines for 18 repos on an 80-column terminal, and still
        # 122 at 120. Drop the column rather than print that, and say where the
        # text went. This relocates, it does not discard: the HTML carries every
        # description in full, which is the same split the column already lives
        # under. Eight fixed columns simply do not leave room for prose.
        if budget < DESC_USEFUL_WIDTH:
            cols = [c for c in cols if c[1] != "description"]
            headers = [h for h, _ in cols]
            keys = [k for _, k in cols]
            widths.pop(desc_i)
            desc_i = None
            table_chrome = 3 * len(cols) + 1
            dropped_description = True
        else:
            widths[desc_i] = budget

    bar = lambda left, mid, right: left + mid.join("─" * (w + 2) for w in widths) + right
    header_cells = [f"{h:^{w}}" if k in CENTERED_HEADERS else f"{h:<{w}}"
                    for h, k, w in zip(headers, keys, widths)]
    print(bar("┌", "┬", "┐"))
    print("│ " + " │ ".join(header_cells) + " │")
    print(bar("├", "┼", "┤"))
    for group in groups:
        # Each machine's description wraps under that machine's own line, so it
        # stays next to the metrics it explains rather than running down the whole
        # group. Continuation lines carry the wrapped text alone.
        for line in group.rows:
            desc = textwrap.wrap(line.get("description", ""), widths[desc_i]) if desc_i is not None else []
            for i in range(max(1, len(desc))):
                cells = [(desc[i] if i < len(desc) else "") if ci == desc_i
                         else (line.get(keys[ci], "") if i == 0 else "")
                         for ci in range(len(cols))]
                print("│ " + " │ ".join(f"{c:<{w}}" for c, w in zip(cells, widths)) + " │")
    print(bar("└", "┴", "┘"))
    if dropped_description:
        # budget goes negative once the fixed columns alone overrun the target,
        # and "-42 columns left" reads as a bug rather than as a narrow window.
        left = max(0, budget)
        print(f"DESCRIPTION omitted — {left} columns left for it, {DESC_USEFUL_WIDTH} needed. "
              f"The report carries every one in full.")


def conventions_summary(snap: MachineSnapshot) -> str:
    """What every CONV cell in this machine's column was measured against.

    Named once per machine because that is what it belongs to: the step set comes
    from that machine's own dotfiles checkout, and a checkout behind the other one
    reports smaller gaps for the same repos. When it could not be read the sentence
    says so, so an empty column is never mistaken for a fleet that is up to date.
    """
    if snap.conv_error:
        return f"conventions unmeasured — {snap.conv_error}"
    return f"conventions v{snap.conv_latest} ({snap.conv_sha})"


def print_machine_summary(snapshots: list[MachineSnapshot]) -> None:
    now = time.time()
    for snap in snapshots:
        if snap.status != "ok":
            print(f"{snap.name}: NOT REACHED — {snap.error}")
            continue
        # Sub-minute rounds up to "1m" in the shared formatter, and this line is
        # printed seconds after the scan it describes, so it would always say that.
        elapsed = now - snap.scanned_at
        when = f"{compact_age(elapsed)} ago" if elapsed >= 60 else "just now"
        print(f"{snap.name}: {snap.os_label} · {snap.projects_root} · {snap.scanned_count} repos · "
              f"{conventions_summary(snap)} · scanned {when}")


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
  .mmeta {{ color:var(--mut); }}
  .merr {{ color:var(--warn); font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; }}
  main {{ padding:22px 26px 64px; display:grid; gap:14px; grid-template-columns:1fr; }}
  article.repo {{ border:1px solid var(--line); border-radius:9px; background:var(--card); padding:12px 14px; }}
  article.repo > header {{ display:flex; align-items:baseline; gap:9px; margin-bottom:6px; }}
  .rname {{ font-weight:650; font-size:14.5px; }}
  .issues {{ margin-left:auto; color:var(--accent); background:var(--chip);
             border-radius:20px; padding:1px 9px; font-size:11.5px; font-weight:600; white-space:nowrap; }}
  p.desc {{ margin:0 0 9px; font-size:13.5px; }}
  p.desc.pending {{ color:var(--mut); font-style:italic; }}
  /* One column per reached machine; the count is set inline per card, since a
     repo is rendered against however many machines answered. align-items:start,
     not stretch: opening one column's file list would otherwise grow its
     neighbour to match. */
  .mcols {{ display:grid; gap:0 20px; align-items:start; }}
  .mcol {{ min-width:0; }}
  /* Each machine is named once here instead of on every row, so the header has to
     survive scrolling — a column scrolled away from its label is unreadable.
     Horizontal padding is the card's 14px plus its 1px border, which lines these
     tracks up with the columns inside each card. */
  .cols-head {{ position:sticky; top:0; z-index:1; background:var(--bg);
                display:grid; gap:0 20px; padding:10px 15px 8px;
                border-bottom:1px solid var(--line); }}
  .cname {{ font-weight:650; font-size:13.5px; }}
  .cmeta {{ color:var(--mut); font-size:11.5px; overflow-wrap:anywhere; }}
  .mrow {{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; padding:3px 0;
           border-top:1px solid var(--line); font-size:12.5px; }}
  .mpath {{ color:var(--mut); font-size:11.5px;
            font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .m {{ color:var(--mut); }}
  .m b {{ color:var(--fg); font-weight:600; }}
  .m.bad {{ color:var(--warn); }}
  .add {{ color:var(--add); font-weight:600; }}
  .del {{ color:var(--del); font-weight:600; }}
  details {{ margin:5px 0 0 8px; }}
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
  {machines}
</header>
{body}
{script}
"""

# Kept out of PAGE because PAGE goes through str.format, which reads every brace
# in a script as a field and fails on the first one. It arrives through the
# `{script}` slot instead, where its braces are never scanned.
#
# formatInterval is ported verbatim from the What's Next repo's web/src/lib/format.ts
# rather than rewritten, so every surface that shows an interval agrees on where
# the boundaries fall. Recomputing on an interval is the point: a report left open
# — or reopened tomorrow — otherwise keeps asserting the age it had when written.
LIVE_TIME_SCRIPT = """<script>
(() => {
  const formatInterval = (ms) => {
    const min = Math.floor((ms > 0 ? ms : 0) / 60000);
    if (min < 60) return `${Math.max(1, min)}m`;
    const hrs = Math.floor(min / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d`;
    if (days < 365) return `${Math.floor(days / 30)}mo`;
    return `${Math.floor(days / 365)}y`;
  };
  const tick = () => {
    const now = Date.now();
    for (const el of document.querySelectorAll('.rel[data-ts]')) {
      const ts = Number(el.dataset.ts);
      if (!Number.isFinite(ts)) continue;
      el.textContent = formatInterval(now - ts) + (el.dataset.suffix || '');
    }
  };
  tick();
  setInterval(tick, 30000);
  // A backgrounded tab throttles timers hard, so a page returned to after hours
  // would show whatever it last managed to render. Recompute on the way back in.
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
})();
</script>"""


def esc(text: str) -> str:
    return html.escape(str(text))


def failed_machine_card(snap: MachineSnapshot) -> str:
    return (f'<div class="machine bad"><span class="mname">{esc(snap.name)}</span>'
            f'<span class="mmeta">not reached</span>'
            f'<span class="merr">{esc(snap.error)}</span></div>')


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
        parts.append(f'<span class="m">{rel_time(state.oldest_epoch)}</span>')
    parts.append(conventions_metric(state.conventions))
    return "".join(parts)


def conventions_metric(conv: ConventionState | None) -> str:
    """The conventions part of a machine's metrics row, in words.

    The terminal column has room for a count and the report has room for what it
    counts, so this is where "13" becomes "13 conventions to decide". `behind` and
    `undecided` are separated for the same reason the record separates them: a repo
    that has decided nothing has not fallen behind, it has never been asked.
    """
    if conv is None or not conv.anything:
        return ""
    if conv.note:
        return f'<span class="m bad">conventions unknown — {esc(conv.note)}</span>'
    parts = []
    if conv.behind and not conv.recorded:
        parts.append(f'<span class="m" title="no record file — /adopt has never run in this repo">'
                     f'<b>{conv.behind}</b> conventions undecided</span>')
    elif conv.behind:
        parts.append(f'<span class="m" title="adopted through v{conv.through}">'
                     f'<b>{conv.behind}</b> conventions behind</span>')
    if conv.unwired:
        parts.append(f'<span class="m" title="decided in this repo, not wired on this machine">'
                     f'<b>{conv.unwired}</b> unwired here</span>')
    return "".join(parts)


def machine_row_html(state: RepoState | None, repo_name: str, now: float) -> str:
    # Only pending work renders. A machine that is clean, and one with no clone at
    # all, both leave the column empty — the report exists to show what is
    # outstanding, and neither of them is. The table still separates the two, where
    # a blank cell sits between filled neighbours and would read as either.
    if state is None or not state.has_anything:
        return ""
    # The clone path only earns a place when it differs from the repo's own name;
    # otherwise it repeats the card's title on every row.
    path = f'<span class="mpath">{esc(state.path)}</span>' if state.path != repo_name else ""
    out = f'<div class="mrow">{path}{metric_html(state, now)}</div>'
    # The metrics row above already carries both counts, so the summaries name
    # what is inside rather than repeating the number.
    if state.changes:
        entries = (f"{l[:2].replace(' ', '·')}{l[2:]}" for l in state.changes)
        out += f'<details><summary>uncommitted files</summary>{listing_html(entries)}</details>'
    if state.commits:
        out += f'<details><summary>unpushed commits</summary>{listing_html(state.commits)}</details>'
    if state.conventions and state.conventions.pending:
        out += (f'<details><summary>conventions to adopt</summary>'
                f'{listing_html(state.conventions.pending)}</details>')
    return out


def listing_html(entries: Iterable[str]) -> str:
    return '<div class="listing">' + "".join(f"<div>{esc(e)}</div>" for e in entries) + "</div>"


def repo_card(row: RepoRow, reached: list[str], now: float) -> str:
    head = f'<a class="rname" href="https://github.com/{esc(row.slug)}">{esc(row.name)}</a>'
    if row.open_issues:
        label = "1 open issue" if row.open_issues == 1 else f"{row.open_issues} open issues"
        head += f'<a class="issues" href="https://github.com/{esc(row.slug)}/issues">{label}</a>'
    # Each machine's description sits in its own column, on a shared row above the
    # metrics — so a description is never read against a neighbour saying "clean",
    # and a repo busy on both machines explains both. The row is shared rather than
    # per-column so a long description on one side cannot push that side's metrics
    # out of line with the other's.
    cells = []
    for i, machine in enumerate(reached, start=1):
        place = f'style="grid-row:1;grid-column:{i}"'
        text = row.descriptions.get(machine, "")
        if text == PENDING_DESCRIPTION:
            cells.append(f'<p class="desc pending" {place}>description not written</p>')
        elif text:
            cells.append(f'<p class="desc" {place}>{esc(text)}</p>')
        cells.append(f'<div class="mcol" style="grid-row:2;grid-column:{i}">'
                     f'{machine_row_html(row.states.get(machine), row.name, now)}</div>')
    return (f'<article class="repo"><header>{head}</header>'
            f'<div class="mcols" style="grid-template-columns:{track(len(reached))}">'
            f'{"".join(cells)}</div></article>')


def track(count: int) -> str:
    """The column track shared by the sticky header and every card, so the two align."""
    return f"repeat({count},minmax(0,1fr))"


def rel_time(epoch: float, suffix: str = " ago") -> str:
    """A relative timestamp the page keeps current by itself.

    Baking the interval in at render time makes it wrong the moment the file is
    left open — a report generated eight minutes ago went on claiming "8 mins
    ago" indefinitely. The epoch travels in `data-ts` and the script at the foot
    of the page recomputes from it; the text written here is the no-JS fallback,
    correct at the instant of writing. The exact local stamp sits on hover, per
    feedback_relative_timestamps.
    """
    if not epoch:
        return ""
    return (f'<span class="rel" data-ts="{int(epoch * 1000)}" data-suffix="{esc(suffix)}"'
            f' title="{esc(local_stamp(epoch))}">{esc(compact_age(time.time() - epoch))}{esc(suffix)}</span>')


def compact_age(seconds: float) -> str:
    """Format a delta as 5m / 3h / 2d / 4mo / 1y.

    Ported from formatInterval in the What's Next repo (web/src/lib/format.ts)
    rather than rewritten, so every surface that shows an interval agrees on
    where the boundaries fall. LIVE_TIME_SCRIPT carries the same function for the
    page to recompute with; this copy renders the terminal table and the no-JS
    fallback. A delta at or below zero returns empty, which callers read as
    "just now".
    """
    if seconds <= 0:
        return ""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{max(1, minutes)}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 30:
        return f"{days}d"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def column_head(snap: MachineSnapshot, now: float) -> str:
    return (f'<div><div class="cname">{esc(snap.name)}</div>'
            f'<div class="cmeta">'
            f'{esc(snap.os_label)} · {esc(snap.projects_root)} · {snap.scanned_count} repos · '
            f'{esc(conventions_summary(snap))} · scanned {rel_time(snap.scanned_at)}</div></div>')


def write_html(path: Path, rows: list[RepoRow], snapshots: list[MachineSnapshot], owner: str) -> None:
    now = time.time()
    reached = [s for s in snapshots if s.status == "ok"]
    names = [s.name for s in reached]
    total = len({slug for s in reached for slug in s.repos})
    title = f"Repo status — {owner}"
    if rows:
        sub = f"{len(rows)} of {total} repos have pending work, open issues, or conventions to adopt"
        heads = "".join(column_head(s, now) for s in reached)
        body = (f'<main><div class="cols-head" style="grid-template-columns:{track(len(reached))}">'
                f'{heads}</div>' + "".join(repo_card(r, names, now) for r in rows) + "</main>")
    else:
        scanned = " and ".join(f"{s.scanned_count} on {s.name}" for s in reached) or "none"
        sub = "Nothing pending"
        body = (f'<p class="none">Every repo is clean, pushed, current on conventions, and has no open '
                f'issues — {esc(scanned)} scanned. A repo appears here only when it has uncommitted '
                f'changes, unpushed or inbound commits, an open issue, or a convention version still '
                f'to decide.</p>')
    # Reached machines are named by the column headers; only an unreached one still
    # needs a card up here, so its SSH error is stated rather than the machine just
    # missing from a report that otherwise looks complete.
    failed = "".join(failed_machine_card(s) for s in snapshots if s.status != "ok")
    page = PAGE.format(title=esc(title), sub=esc(sub),
                       machines=f'<div class="machines">{failed}</div>' if failed else "", body=body,
                       script=LIVE_TIME_SCRIPT)
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
        print(f"Nothing pending — {scanned} repos scanned, all clean, pushed, current on conventions, "
              f"and without open issues.")
        return
    print_table(groups, visible_columns(groups, len(reached)), width)


def state_to_json(snapshots: list[MachineSnapshot], rows: list[RepoRow]) -> str:
    return json.dumps({
        "machines": [asdict(s) for s in snapshots],
        "repos": [{"slug": r.slug, "descriptions": r.descriptions} for r in rows],
    }, ensure_ascii=False)


def state_from_json(text: str) -> tuple[list[MachineSnapshot], list[RepoRow]]:
    data = json.loads(text)
    snapshots = [MachineSnapshot.from_dict(m) for m in data["machines"]]
    rows = merge(snapshots)
    # A state file written before descriptions became per-machine carries a
    # `description` string where this wants a `descriptions` object. Defaulting
    # to {} would render every cell blank and say nothing — the same silence a
    # scan with genuinely nothing to describe produces, so it has to be named.
    saved, stale = {}, []
    for r in data.get("repos", []):
        if "descriptions" in r:
            saved[r["slug"]] = r["descriptions"]
        elif "description" in r:
            stale.append(r["slug"])
    if stale:
        print(f"WARNING: the state file predates the per-machine description model, so "
              f"{len(stale)} repo(s) lost theirs. Re-run the scan before --report.", file=sys.stderr)
    for row in rows:
        row.descriptions = dict(saved.get(row.slug, {}))
    return snapshots, rows


def apply_descriptions(rows: list[RepoRow], text: str, reached: list[str]) -> None:
    """Fold in `{"<project>": ...}`, keyed by the PROJECT cell.

    A value is either one string, which belongs to the repo's single working
    machine, or `{"<machine>": "<summary>"}` when more than one is working. A
    string given for a repo working on several machines is refused rather than
    guessed at: putting it over one column would assert something unchecked about
    the other, and spanning both is what left a column unexplained.

    A key matching no repo — or no machine — is reported rather than dropped: a
    description going nowhere reads exactly like one that was never written.

    Any machine's folder name for a repo is accepted, not only the one in the
    PROJECT cell. Those differ, and the mismatch lands exactly where it is most
    confusing: a repo checked out as `jsonl-logs-intellij-plugin` here and
    `intellij-jsonl-extension` on the peer takes its title from whichever machine
    lists first — clean or not — while the column you are describing shows the
    other name. Keying by the title alone means reading one name and typing a
    different one. An alias shared by two repos is ignored rather than guessed.
    """
    described = json.loads(text)
    by_name = {r.name: r for r in rows}
    alias_counts: dict[str, int] = {}
    for r in rows:
        for path in {st.path for st in r.states.values() if st}:
            alias_counts[path] = alias_counts.get(path, 0) + 1
    for r in rows:
        for path in {st.path for st in r.states.values() if st}:
            if path not in by_name and alias_counts[path] == 1:
                by_name[path] = r
    problems: list[str] = []
    for name, value in described.items():
        row = by_name.get(name)
        if row is None:
            problems.append(f"no repo named {name}")
            continue
        working = row.working(reached)
        if isinstance(value, dict):
            for machine, desc in value.items():
                if machine in working:
                    row.descriptions[machine] = desc
                else:
                    problems.append(f"{name}: {machine} has no pending work")
        elif len(working) == 1:
            row.descriptions[working[0]] = value
        else:
            problems.append(f"{name} has work on {' and '.join(working) or 'no machine'} — "
                            f'give it {{"<machine>": "<summary>"}}')
    if problems:
        print("WARNING: " + "; ".join(problems) + " — those descriptions were dropped.", file=sys.stderr)


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
        apply_descriptions(rows, text.strip() or "{}", [s.name for s in snapshots if s.status == "ok"])
        render(snapshots, rows, target_width(config))
        owner = rows[0].slug.split("/", 1)[0] if rows else github_user()
        write_html(html_path, rows, snapshots, owner)
        print(f"\nHTML report: file:///{str(html_path).replace(os.sep, '/').lstrip('/')}")
        return 0

    snapshots = gather(config)
    if snapshots is None:
        return 2
    rows = merge(snapshots)
    reached_names = [s.name for s in snapshots if s.status == "ok"]
    for row in rows:
        for machine in row.working(reached_names):
            row.descriptions[machine] = PENDING_DESCRIPTION
    render(snapshots, rows, target_width(config))
    print_detail(rows, multi=sum(s.status == "ok" for s in snapshots) > 1)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state_to_json(snapshots, rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
