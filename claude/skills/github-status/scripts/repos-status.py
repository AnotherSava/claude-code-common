#!/usr/bin/env python3
"""repos-status — scan every GitHub-owned clone on this machine and on its peer,
and report which ones have pending work.

A machine is scanned by walking PROJECTS_ROOT for git repos whose `origin`
belongs to GITHUB_USER, fetching each one, auto-pulling the clean ones that are
behind, and counting open issues via `gh`. The peer machine is scanned by piping
*this same file* into its interpreter over SSH (`ssh host "python - --json"`), so
the two ends can never run different versions of the scan and nothing has to be
installed or kept in sync on the far side.

Each clone is also read against the convention versions the dotfiles repo
defines, so a repo that is behind on them is reported even when its tree is
clean — a version gap is outstanding work in that repo, and nothing else in this
report would ever mention it.

Results merge on the repo's `OWNER/REPO` origin slug — the only identity that
survives a different clone path on each machine. A machine gets a line under a
repo only where it has a clone of it: one holding nothing to report is marked
`clean`, and one that could not be reached is named once in the summary as `not
reached`. A machine with no clone of that repo gets no line, so which machines a
repo's block lists is itself the answer to where the repo exists.

Output is a box table on stdout with per-repo detail sections, plus a
self-contained HTML report written to the repo's gitignored tmp/.

Modes:
  (default)         scan both machines, print the table and the detail sections,
                    and write the state file that --report reads
  --json            scan THIS machine only and print its snapshot as JSON; this
                    is what the peer invocation runs over SSH
  --report          re-read the state file, fold in the per-repo descriptions
                    read from stdin, print the final table, write the HTML, and
                    store what was applied in the state file and both caches, so
                    re-running it renders and stores the same thing again
  --repo PATH|SLUG  scope the whole run to ONE repo, on every machine — the
                    repo-status skill's mode. A path (default `.`) is resolved to
                    its origin slug here, so the peer finds its own clone of the
                    same repo whatever it calls the folder. Scoping also keeps the
                    repo in the report when it has nothing pending: the fleet run
                    answers "what needs attention" and drops a quiet repo, while
                    this one answers "how does this repo stand", where `clean` is
                    the answer rather than an absence of one. Renders as a block
                    per machine rather than as a table (see render_single), and to
                    the terminal only — no HTML, and --html is refused
  --width N         target total table width (also accepted via GHS_WIDTH)
  --descriptions P  read the descriptions from P instead of stdin
  --html PATH       where to write the HTML report
  --state PATH      where the state file lives
  --cache PATH      where THIS machine's description cache lives
  --no-cache        ignore the stored descriptions, on both machines, and mark
                    every working machine for a fresh one

A description is reused whenever the work it was written from is byte-identical,
which each machine decides for its OWN clones from a content digest rather than a
date. Every machine caches only what it owns: the peer resolves its clones during
the scan and the answer rides back inside the snapshot, and `--report` writes each
machine's new descriptions back to that machine. So a repo is described once
however many machines report on it, and switching machines starts warm.

The scan around it is not cached: its cost is the per-repo `git fetch` and `gh
issue list`, and both ask the remote something no local state can answer.

Environment:
  PROJECTS_ROOT — directory to scan (overrides config/config.env)
  GITHUB_USER   — origin-URL owner to filter by (default AnotherSava)
  ROOT_DEPTH    — find -maxdepth value (default 4)
  GHS_WIDTH     — target table width (else terminal width, then 120)
  GHS_ONLY_SLUG — `OWNER/REPO` to scope the run to; what --repo resolves to, and
                  how the scope reaches the scan several calls below main()

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

import hashlib
import html
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields
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

# Past this size a file is folded into the work digest by (size, mtime) rather
# than by its bytes — see compute_work_digest for what that costs.
DIGEST_CONTENT_LIMIT = 8_000_000

# Bumped when the digest's inputs or the file's shape change, which invalidates
# every stored entry at once: an old digest and a new one are not comparable, and
# a description kept against one would be reused on work it was never written from.
CACHE_VERSION = 2



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


def compute_work_digest(repo: Path, head: str, entries: list[tuple[str, str]],
                        commits: list[str], untracked: list[str]) -> str:
    """Hash everything a one-line description of this clone's pending work is written from.

    Two equal digests mean that work is byte-identical, so the description
    written against the first is still true of the second and the reader that
    would write it again can be skipped. A modification date cannot stand in for
    this in either direction: `git status` reports a deleted file with no mtime
    left to read, while touching a file moves its mtime without changing a line.

    Both halves of the pending state go in. `git diff HEAD` covers tracked text
    edits, staged ones included, but it renders a modified binary as the same
    "Binary files differ" line whatever the new bytes are — so the working-tree
    content of every named path is hashed as well, which is also what covers
    untracked files. A file past DIGEST_CONTENT_LIMIT is folded in by size and
    mtime instead; that misses a change only if an edit preserves both.
    """
    h = hashlib.sha256()
    h.update(head.encode())
    for line in commits:
        h.update(b"\0c" + line.encode())
    for code, path in entries:
        h.update(b"\0p" + code.encode() + path.encode())
    diff = subprocess.run(["git", "-C", str(repo), "diff", "HEAD"], capture_output=True)
    h.update(b"\0d" + diff.stdout)
    # Porcelain names an untracked directory as one entry; ls-files has already
    # expanded it, so the union covers the directory's files without walking it here.
    for rel in sorted({path for _, path in entries} | set(untracked)):
        h.update(b"\0f" + rel.encode())
        full = repo / rel
        try:
            if not full.is_file():
                h.update(b"-")  # deleted in the workdir, or the directory form of an untracked entry
                continue
            stat = full.stat()
            if stat.st_size > DIGEST_CONTENT_LIMIT:
                h.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
                continue
            with full.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            h.update(b"?")
    return h.hexdigest()


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

# `OWNER/REPO` as --repo accepts it literally: exactly one slash, and neither half
# a path segment `.`/`..` could occupy. A value of this shape that is ALSO an
# existing directory is read as the directory, since that is what the user is
# standing in and a coincidental match would silently report a different repo.
SLUG_SHAPE = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")


def origin_slug(repo: Path) -> str | None:
    """Return 'OWNER/REPO' parsed from the repo's `origin` URL, or None."""
    m = ORIGIN_SLUG.search(git(["remote", "get-url", "origin"], repo))
    return f"{m['owner']}/{m['repo']}" if m else None


def only_slug() -> str | None:
    """The one repo this run is scoped to, or None for a whole-fleet run.

    Read from the environment rather than passed down, because the scan that
    consults it runs several calls below the argument parsing and, on the peer,
    in a different process on a different machine. `--no-cache` and the width
    already travel this way for the same reason.
    """
    return os.environ.get("GHS_ONLY_SLUG") or None


def resolve_repo_scope(value: str) -> str | None:
    """Turn a --repo value into the `OWNER/REPO` slug both machines merge on.

    A slug is taken as given; anything else is read as a path and asked for its
    `origin`. The slug is what crosses to the peer because the clone path does
    not survive the hop — the same repo is `claude` here and could be
    `claude-code-common` there, and a path would find nothing or, worse, find a
    different repo that happens to sit at that path.
    """
    if SLUG_SHAPE.fullmatch(value) and not Path(value).exists():
        return value
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        print(f"ERROR: --repo {value}: no such directory, and not an OWNER/REPO slug.", file=sys.stderr)
        return None
    slug = origin_slug(path)
    if not slug:
        print(f"ERROR: --repo {value}: {path} has no GitHub `origin` remote to identify it by.", file=sys.stderr)
    return slug


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
    """How far one clone is from the convention versions, as `/adopt` would read it.

    Per machine rather than per repo, even though the record itself is one committed
    file that travels with the clone: what it is measured against is that machine's
    own dotfiles checkout, and the two checkouts are routinely at different commits.
    """

    behind: int = 0  # versions above the repo's own number — the "N versions behind" count
    adopted: int = 0  # the committed record: the highest version this repo has adopted
    recorded: bool = True  # whether a record file exists at all; False means /adopt never ran there
    pending: list[str] = field(default_factory=list)  # "v3 <title>", ascending
    note: str = ""  # why the numbers above cannot be trusted; empty when they can

    @property
    def anything(self) -> bool:
        """Whether this clone has something to say. A note counts: an unreadable
        record is an open question, and a blank cell would read as `current`."""
        return bool(self.behind or self.note)


def conventions_module() -> tuple[ModuleType | None, str]:
    """The convention engine from this machine's dotfiles, or None and the reason it is missing.

    Loaded by path rather than by name: the peer runs this script from stdin, where
    there is no `__file__` to hang a relative import off, and `skill_dir()` already
    falls back to the conventional install path for exactly that case.

    Reading the record here rather than re-implementing it is the same rule the
    session-start hook follows — two readers of one format drift the day either
    changes shape, and this one would drift silently, on a machine nobody is
    watching.

    Every filesystem touch sits inside the handler, the existence probe included.
    `is_file()` answers False for a path that is merely absent, but it raises for one
    the OS refuses to walk — and such a path is what the Windows peer had: a link in
    `~/.claude` created without elevation, which Windows declines to follow at all
    (WinError 448), a symlink as readily as a junction. That escaped this function,
    took the peer's whole snapshot down, and
    printed the machine as NOT REACHED when the one thing it could not read was its
    CONV column.
    """
    path = skill_dir().parent.parent / "conventions" / "engine.py"
    name = "ghs_conventions"
    try:
        if not path.is_file():
            # The state a peer is actually in when this fires: its dotfiles checkout predates the
            # conventions engine. Saying so beats a bare path, which reads as a broken install.
            return None, f"no convention engine at {path} — this machine's dotfiles checkout may be behind"
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
        return None, f"the convention engine could not be loaded ({exc})"


def read_conventions(module: ModuleType, versions: list, repo: Path) -> ConventionState | None:
    """One clone's standing against `versions`, or None where the question does not apply.

    None is returned for a repo that was never going to hold a record — someone
    else's project, or one carrying an `exempt` line — so the column stays empty
    there rather than asserting a gap. Every other way of failing to reach a number
    fills `note` instead, because a blank cell and `current` are the same blank.

    The count comes from the engine's own `pending` rather than from arithmetic on the
    integer here: how far an adopted number reaches is the engine's rule, and a second
    copy of it in a report nobody is watching would drift silently.
    """
    root = str(repo)
    try:
        if module.is_third_party(root) is not None:
            return None
        record = module.read_record(root)
        if record.error:
            return ConventionState(note=module.parse_error_message(record))
        if record.exempt:
            return None
        newest = versions[-1].number
        if record.number > newest:
            # This machine's dotfiles checkout is the behind one, so its version set is
            # older than the record it is reading and the count below would be wrong.
            return ConventionState(note=f"records v{record.number}, above the newest version in this "
                                        f"machine's dotfiles checkout (v{newest}) — pull the dotfiles "
                                        f"repo there")
        # Ascending, as the engine hands them over and as the session-start notice renders them:
        # the list is read as the order /adopt will walk, and a version out of place reads as one
        # that can be taken on ahead of the rest.
        waiting = module.pending(root)
        return ConventionState(behind=len(waiting), adopted=record.number, recorded=record.present,
                               pending=[f"v{v.number} {v.title}" for v in waiting])
    except BaseException as exc:
        return ConventionState(note=f"the convention record could not be read ({exc})")


# ── per-machine state ─────────────────────────────────────────────────────────


_WARNED_RETIRED: set[str] = set()


def _warn_retired(names: list[str]) -> None:
    """Say once per run that a stored field is no longer read, however many repos carry it.

    Once, because the fact is about the payload rather than about a repo: every repo in a state
    file written by an older script carries the same retired key, and a line each buries the table
    under twenty identical warnings. Both readers of that shape reach here — `--report` loading this
    machine's state file, and a peer still running the older script over SSH.
    """
    fresh = sorted(set(names) - _WARNED_RETIRED)
    if not fresh:
        return
    _WARNED_RETIRED.update(fresh)
    print(f"WARNING: stored state carries {', '.join(fresh)}, which this version no longer reads. "
          f"Re-run the scan rather than trusting a number that came from it.", file=sys.stderr)


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
    # Content hash of the pending work — see compute_work_digest. Empty where the clone has none.
    # Defaulted, like `conventions` below, so a state file written before this field existed still
    # loads under `--report`; an empty digest never matches a cached one, so it re-describes.
    work_digest: str = ""
    # The description that clone's own machine already holds for exactly this digest, looked up there
    # during the scan and empty when it holds none. Resolved on the machine that owns the clone, so a
    # repo only the peer has still arrives described — it rides back inside the snapshot like every
    # other field here. This is the cache being read, not a second place descriptions are kept: what
    # the report finally shows lives in RepoRow.descriptions, and the cache is rewritten from those.
    cached_description: str = ""
    # None where the repo holds no record and never will — see read_conventions. Defaulted so a
    # state file written before this field existed still loads under `--report`.
    conventions: ConventionState | None = None

    @property
    def has_work(self) -> bool:
        """Anything git has to report about this clone — what puts it in the table.
        Deliberately excludes the convention gap, which the table asks about separately."""
        return bool(self.uncommitted or self.unpushed or self.behind)

    @property
    def has_own_work(self) -> bool:
        """Work this clone is holding — what a description is written from.

        Narrower than `has_work` by the `behind` term alone, and that term is the
        difference between the two questions. Incoming commits are another machine's
        work, REMOTE already counts them, and the auto-pull has usually applied them
        by the time the report prints. So a clone that is only behind leaves a
        description nothing to say: `git status --porcelain` and
        `git log @{upstream}..HEAD` both come back empty, print_detail emits no
        section for it, and the placeholder asks for a summary of work that is not
        there. Measured 2026-09-18 on a clone reporting `behind: 2, pulled: True`
        with every other count zero.

        An unadopted convention version is excluded for its own reason: it is work
        nobody has started rather than work half done, so there is nothing to
        summarize there either.
        """
        return bool(self.uncommitted or self.unpushed)

    @property
    def has_conventions_gap(self) -> bool:
        return bool(self.conventions and self.conventions.anything)

    @property
    def has_anything(self) -> bool:
        """Whether this clone has anything outstanding at all — what `clean` denies."""
        return self.has_work or self.has_conventions_gap

    @classmethod
    def from_dict(cls, d: dict) -> "RepoState":
        """Rebuild one clone's state, tolerating a state file written against an older shape.

        A key this dataclass no longer has is dropped and named rather than raising: `unwired` was
        written into every serialized ConventionState until machine-scoped versions were retired, so
        a state file from before that change would otherwise abort `--report` with a TypeError far
        from its cause. Named, because a silently dropped field is a number quietly reading 0.
        """
        conv = d.pop("conventions", None)
        state = None
        if conv:
            known = {f.name for f in fields(ConventionState)}
            dropped = sorted(set(conv) - known)
            _warn_retired(dropped)
            state = ConventionState(**{k: v for k, v in conv.items() if k in known})
        return cls(conventions=state, **d)


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
    # The convention version set this machine measured its repos against. Stated next to the
    # machine rather than next to each repo, because every gap in that machine's column is
    # relative to it and the two checkouts are routinely at different commits.
    conv_latest: int = 0  # newest version in this machine's dotfiles checkout
    conv_sha: str = ""  # that checkout's short sha
    # Why no repo here carries a gap; empty only once a scan has measured them. The default is a
    # sentence rather than "" because `--report` re-reads a state file that may predate this
    # field, and defaulting to no-error there renders `conventions v0` — a machine that was never
    # asked, reading exactly like a fleet that is up to date.
    conv_error: str = "this scan predates the convention check; re-run it"
    # Where this machine keeps the descriptions of its own clones. Reported rather than derived,
    # because the machine running the report has to write the peer's descriptions back to the peer
    # and cannot know where that machine's checkout puts its tmp/.
    cache_path: str = ""

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
    head_sha = git(["rev-parse", "HEAD"], repo)
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
    untracked = git_z(["ls-files", "--others", "--exclude-standard", "-z"], repo)
    for path in untracked:
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

    # Computed for every clone rather than only the dirty ones: a clone whose tree is
    # clean can still be holding unpushed commits, which `has_own_work` counts and a
    # description is owed for. On a clean tree this reads an empty diff and no files.
    digest = compute_work_digest(repo, head_sha, entries, commits, untracked)

    return RepoState(
        path=rel, branch=branch, unpushed=unpushed, behind=behind, pulled=False,
        uncommitted=len(entries), lines_added=lines_added, lines_deleted=lines_deleted,
        oldest_epoch=min(candidates) if candidates else 0.0,
        changes=[f"{code} {path}" for code, path in entries], commits=commits, open_issues=None,
        work_digest=digest,
    )


def discover_owned(projects_root: Path, github_user: str, depth: int) -> list[tuple[Path, str, str]]:
    """Return [(repo_path, rel_to_root, slug)] for repos whose origin matches github_user.

    A scoped run keeps only the one repo. The walk still happens — it is a
    `git remote get-url` per repo, against the fetch, the `gh` call and the
    convention read the scope removes — and it is what lets the peer find its own
    clone under whatever path it keeps it at.
    """
    wanted = only_slug()
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
        if slug and (wanted is None or slug == wanted):
            owned.append((repo, rel, slug))
    return owned


def scan_machine(name: str, projects_root: Path, github_user: str, depth: int) -> MachineSnapshot:
    """Fetch, read, auto-pull and issue-count every owned repo on this machine."""
    owned = discover_owned(projects_root, github_user, depth)
    print(f"[{name}] fetching {len(owned)} repos...", file=sys.stderr)
    fetch_all([repo for repo, _, _ in owned])

    states = {slug: collect_state(repo, rel) for repo, rel, slug in owned}
    by_slug = {slug: repo for repo, _, slug in owned}

    # Each machine answers for its own clones, so the digest is compared here, where it was
    # computed, rather than by whoever collates the two. A repo the peer alone has therefore
    # arrives already described, and neither machine ever re-reads work the other has read.
    if not os.environ.get("GHS_NO_CACHE"):
        cached = load_cache(cache_file())
        for slug, state in states.items():
            entry = cached.get(slug, {})
            if state.work_digest and entry.get("digest") == state.work_digest:
                state.cached_description = entry.get("description", "")

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

    # Conventions last: it is the only part that reads a second tool, and a failure there
    # must cost the machine its gap numbers and nothing else.
    module, conv_error = conventions_module()
    latest, sha, versions = 0, "", []
    if module is not None:
        try:
            versions = module.load_versions()
            latest, sha = (versions[-1].number if versions else 0), module.dotfiles_sha()
        except BaseException as exc:
            versions, conv_error = [], f"the convention versions could not be read ({exc})"
        if not versions and not conv_error:
            # An empty version set would leave every repo measuring as current, which is the one
            # reading a machine with no versions to measure against must not produce.
            conv_error = "this machine's dotfiles checkout defines no convention versions"
    if versions:
        print(f"[{name}] reading the convention record of {len(states)} repo(s)...", file=sys.stderr)
        for repo, _, slug in owned:
            states[slug].conventions = read_conventions(module, versions, repo)

    return MachineSnapshot(
        # as_posix so a Windows root renders with forward slashes in the report, matching
        # how it is written in config.env and how every repo path is rendered.
        name=name, os_label=os_label(), projects_root=projects_root.as_posix(),
        scanned_at=time.time(), scanned_count=len(owned), repos=states,
        conv_latest=latest, conv_sha=sha, conv_error=conv_error, cache_path=cache_file().as_posix(),
    )


# ── the peer machine ──────────────────────────────────────────────────────────


def peer_name(peer_ssh: str) -> str:
    """Display name for a peer that never answered: the host, minus any domain."""
    host = peer_ssh.rsplit("@", 1)[-1]
    return host.split(".", 1)[0] or host


def peer_interpreter(config: Path) -> str:
    """The interpreter name on the peer, for both hops that cross to it — the scan
    and the description-cache write. A Windows peer has `python` and no `python3`,
    and a Homebrew macOS one the reverse, so the default is only the second guess.
    """
    return config_value(config, "PEER_PYTHON") or "python3"


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
    # --no-cache has to cross the hop: the peer resolves its own clones' descriptions, so a
    # refresh asked for here would otherwise refresh only half the report.
    remote_argv = "--json --no-cache" if os.environ.get("GHS_NO_CACHE") else "--json"
    # So does the scope, and as the slug rather than the path: an unscoped peer would scan its
    # whole fleet to have every repo but one discarded at the merge, spending the minutes the
    # scope exists to save. The slug is already `OWNER/REPO` — metacharacter-free under both a
    # POSIX shell and the cmd.exe a Windows sshd hands this string to.
    if wanted := only_slug():
        remote_argv += f" --repo {wanted}"
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={PEER_CONNECT_TIMEOUT}",
           peer_ssh, f"{peer_python} - {remote_argv}"]
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
    def conventions_behind(self) -> int:
        """The widest gap any machine reports, for ordering the ageless block of the table."""
        return max((st.conventions.behind for st in self.states.values() if st and st.conventions), default=0)

    def working(self, reached: list[str]) -> list[str]:
        """The reached machines a description is owed for — those holding work of their
        own. A clone that is merely behind is in the table on its REMOTE count and is
        not one of them; see `RepoState.has_own_work`."""
        return [m for m in reached if (st := self.states.get(m)) and st.has_own_work]


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
    # or convention versions still to adopt there. Sort by AGE ascending — freshest
    # pending work first, oldest last — which sorting the epoch descending achieves,
    # since age = now - epoch. A repo with no pending work has no age at all, so the
    # whole ageless tail would otherwise sit in discovery order; the widest convention
    # gap breaks that tie, putting the repos furthest behind at the top of it.
    #
    # None of that filtering applies to a scoped run. "Which repos need attention"
    # is a question about a set, so a quiet repo is noise in it; "how does THIS repo
    # stand" was asked about one repo, and `nothing outstanding` is the answer to it
    # rather than a reason to print an empty table.
    if only_slug() is None:
        rows = [r for r in rows if r.has_work or r.open_issues or r.conventions_gap]
    rows.sort(key=lambda r: (-r.sort_epoch, -r.conventions_behind))
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


def machine_cell(name: str, state: RepoState) -> str:
    """The MACHINE cell, carrying `clean` when the machine has no metrics.

    A blank cell there sits between filled neighbours in a fixed grid and would
    read as a missing value, so a clone with nothing to report says so in a word.

    Two kinds of machine have no row at all rather than a word: one with no clone,
    and one that was never reached. Neither has anything to report on this repo,
    and the summary above the table names an unreachable machine once, with its
    error, which beats repeating it under every repo.

    A clone behind on conventions is not clean: its CONV cell is filled, and the
    two sitting on one line would contradict each other.
    """
    return name if state.has_anything else f"{name} clean"


def conventions_cell(state: ConventionState | None) -> str:
    """The CONV cell: how many versions this clone has still to adopt.

    `?` where the record could not be read at all — the number is unknown there, and
    leaving it blank would say `current`, which is the one answer nothing has checked.
    The report spells both out in words; this column only has room for the count.
    """
    if state is None or not state.anything:
        return ""
    return "?" if state.note else str(state.behind)


def build_groups(rows: list[RepoRow], reached: list[str]) -> list[DisplayGroup]:
    now = time.time()
    groups: list[DisplayGroup] = []
    for row in rows:
        lines: list[dict[str, str]] = []
        for machine in reached:
            state = row.states.get(machine)
            # A machine with no clone gets no line. Every other cell on it would be
            # empty, so the line carried one word — the machine's name and `absent` —
            # and spent a row of the table saying where the repo is not. The reader
            # can already see that: a repo cloned on one machine renders one line, and
            # which machine it names is the same fact the dropped line was stating.
            if state is None:
                continue
            first = not lines
            cells = {
                "project": row.name if first else "",
                "machine": machine_cell(machine, state),
                "branch": "", "unpushed": "", "remote": "", "local": "", "age": "",
                "conventions": conventions_cell(state.conventions),
                "description": row.descriptions.get(machine, ""),
                "issues": str(row.open_issues) if first and row.open_issues else "",
            }
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
    GHS_WIDTH line in config.env, then the detected terminal width (see
    `skills/shared/terminal_width.py`; 120 when no ancestor process has a tty).

    The DESCRIPTION column stretches to consume whatever this width leaves after
    the fixed columns, so the table spans the full target width.
    """
    val = config_value(config, "GHS_WIDTH")
    if val and val.isdigit():
        return int(val)
    # Imported here rather than at the top for the same reason the convention engine is: the peer
    # runs this script from stdin, where a relative import has no `__file__` to hang off. Only the
    # rendering side ever asks for a width — the peer answers in JSON — so this never runs there,
    # and the peer needs no copy of the module to scan successfully.
    sys.path.insert(0, str(skill_dir().parent / "shared"))
    from terminal_width import terminal_columns  # inline: see above

    return terminal_columns(120)


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

    Named once per machine because that is what it belongs to: the version set comes
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

    Only for the machines whose description is still the placeholder. A clone
    whose digest matched the cache already has its line, so printing its diff
    again would be raw material for work nobody is going to do.

    Porcelain status is XY where X (staged) / Y (unstaged) may be a space — swap
    spaces for a center dot so the columns line up visually.
    """
    def unwritten(row: RepoRow, machine: str) -> bool:
        return row.descriptions.get(machine) == PENDING_DESCRIPTION

    dirty = [(r, m, s) for r in rows for m, s in r.states.items() if s and s.changes and unwritten(r, m)]
    if dirty:
        print("\nUncommitted changes:")
        for row, machine, state in dirty:
            print(f"\n{row.name}{f' [{machine}]' if multi else ''}:")
            for line in state.changes:
                print(f"  {line[:2].replace(' ', '·')}{line[2:]}")

    pending = [(r, m, s) for r in rows for m, s in r.states.items() if s and s.commits and unwritten(r, m)]
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
    counts, so this is where "13" becomes "13 conventions to adopt". `unadopted` and
    `behind` are separated for the same reason the record separates them: a repo with
    no record file has not fallen behind, it has never been asked.
    """
    if conv is None or not conv.anything:
        return ""
    if conv.note:
        return f'<span class="m bad">conventions unknown — {esc(conv.note)}</span>'
    if not conv.recorded:
        return (f'<span class="m" title="no record file — /adopt has never run in this repo">'
                f'<b>{conv.behind}</b> conventions unadopted</span>')
    return (f'<span class="m" title="this repo is at v{conv.adopted}">'
            f'<b>{conv.behind}</b> conventions behind</span>')


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
                f'to adopt.</p>')
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

    The resolve is what makes the answer the same on both sides of the SSH hop.
    The peer runs this script from stdin, where `script_path()` is None and
    `skill_dir()` falls back to the literal ~/.claude/skills/... path — whose
    parents are ~/.claude and ~, neither of which holds a .git. Walking that
    unresolved would put the peer's artifacts beside the skill while the same
    machine running the report itself put them in the repo's tmp/, so a file
    written to one would be read from the other and never found.
    """
    base = skill_dir().resolve()
    for parent in base.parents:
        if (parent / ".git").exists():
            return parent / "tmp"
    return base / "tmp"


def this_machine_name(config: Path) -> str:
    """What this machine calls itself in the report — the name its snapshot and its
    descriptions are keyed by. Resolved in one place because `--report` has to pick
    its own column out of a state file the scan wrote."""
    return config_value(config, "MACHINE_NAME") or socket.gethostname().split(".", 1)[0]


def cache_file() -> Path:
    """Where THIS machine keeps the descriptions of its OWN clones.

    Resolved here rather than passed down, for the reason `config_file` is: the
    peer runs this script from stdin and has to find its own paths, and the scan
    that reads the cache is several calls below the one that parsed `--cache`.
    GHS_CACHE is how that flag reaches it, the same way `--width` travels as
    GHS_WIDTH.
    """
    return Path(os.environ.get("GHS_CACHE") or tmp_dir() / "github-status-descriptions.json")


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
    return scan_machine(this_machine_name(config), root, github_user(), int(os.environ.get("ROOT_DEPTH", "4")))


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

    with ThreadPoolExecutor(max_workers=2) as ex:
        local = ex.submit(scan_this_machine, config)
        remote = ex.submit(scan_peer, peer_ssh, peer_interpreter(config), source)
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


def machine_facts(state: RepoState) -> list[str]:
    """What is worth saying about one clone, in reading order, with every fact that
    sits at its default left out.

    A single-repo report is read by someone who asked about this repo, so the
    interesting content is whatever is NOT ordinary: `main`, an upstream with
    nothing either way, and a current convention record are the expected answers and
    say nothing by being printed. What remains is short enough to read as a sentence.

    Returning [] means the clone is entirely ordinary — the caller says `clean`
    rather than printing an empty line, because silence about a machine the user
    named is the one thing this report must not do.
    """
    facts: list[str] = []
    if state.branch not in DEFAULT_BRANCHES:
        facts.append(f"on {state.branch}")
    if state.uncommitted:
        lines = format_lines(state.lines_added, state.lines_deleted)
        facts.append(f"{state.uncommitted} uncommitted" + (f" ({lines})" if lines else ""))
    if state.unpushed:
        facts.append(f"{state.unpushed} unpushed")
    if state.behind:
        facts.append(f"{state.behind} inbound{' (pulled)' if state.pulled else ''}")
    if state.oldest_epoch:
        facts.append(f"oldest {compact_age(time.time() - state.oldest_epoch)} ago")
    if (conv := state.conventions) and conv.anything:
        facts.append(conv.note or f"{conv.behind} convention{'s' if conv.behind != 1 else ''} behind")
    return facts


def pack_facts(facts: list[str], width: int) -> list[str]:
    """Group facts into lines of at most `width`, breaking only between them.

    Wrapping this line by words would split `4 inbound (pulled)` across two lines
    and leave `(pulled)` reading as a fact of its own, so the break points are the
    separators and nothing else. A single fact wider than the budget — a long branch
    name, a convention note — takes a line of its own and is allowed to overrun it:
    truncating it would hide the part that made it worth printing.
    """
    lines: list[str] = []
    current = ""
    for fact in facts:
        joined = f"{current} · {fact}" if current else fact
        if current and len(joined) > width:
            lines.append(current)
            current = fact
        else:
            current = joined
    if current:
        lines.append(current)
    return lines


def render_single(snapshots: list[MachineSnapshot], rows: list[RepoRow], width: int) -> None:
    """One repo, as a short block per machine rather than as a row of a table.

    The fleet table's columns exist to align many repos against each other; with one
    repo every column is a header over a single value, and most of them are blank.
    So this drops the grid and the machine summary, and prints only what is true and
    not ordinary — see `machine_facts` for which facts that excludes.
    """
    row = rows[0]
    repo = row.slug.split("/", 1)[1]
    # The clone path and the GitHub repo name disagree often enough to be worth both
    # (`claude` is `claude-code-common`), and saying one twice is worth neither.
    title = row.slug if row.name == repo else f"{row.name} — {row.slug}"
    if row.open_issues:
        title += f" · {row.open_issues} open issue{'s' if row.open_issues != 1 else ''}"
    elif row.open_issues is None:
        # Not the same as zero, and printing nothing would assert the zero.
        title += " · open issues unknown"
    print(title)
    print()

    label_width = max(len(s.name) for s in snapshots)
    for snap in snapshots:
        label = f"  {snap.name:<{label_width}}  "
        # Every line of a machine's entry hangs under the same indent, so the label
        # column stays clear however many lines the entry runs to. The budget is
        # what is left of the terminal after that indent.
        indent = " " * len(label)
        budget = max(20, width - len(label))
        emit = lambda lines: [print((label if i == 0 else indent) + text) for i, text in enumerate(lines)]
        if snap.status != "ok":
            emit(textwrap.wrap(f"not reached — {snap.error}", budget))
            continue
        state = row.states.get(snap.name)
        if state is None:
            emit(["no clone here"])
            continue
        emit(pack_facts(machine_facts(state), budget) or ["clean"])
        if (desc := row.descriptions.get(snap.name, "")) and desc != PENDING_DESCRIPTION:
            for line in textwrap.wrap(desc, budget):
                print(indent + line)


def render(snapshots: list[MachineSnapshot], rows: list[RepoRow], width: int) -> None:
    # A scoped run always has its one row — `main` exits before here when it found none —
    # so the "nothing pending" branch below is unreachable for it and would be wrong if it
    # were not: a clean repo is that report's answer, not an absence of one.
    if only_slug() is not None:
        render_single(snapshots, rows, width)
        return
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


def load_cache(path: Path) -> dict[str, dict[str, str]]:
    """Read one machine's description cache: slug -> {"digest", "description"}.

    There is no machine key inside, because a cache file holds only the clones of
    the machine it sits on. The entry then lives next to the thing it describes,
    so whichever machine runs the report finds it — the one whose clone it is
    always has it, and the other reads it off that machine's snapshot.

    A missing, unreadable or older-format file reads as an empty cache rather
    than an error. Every entry in it is re-derivable by describing the clone
    again, so the worst a bad file costs is the reading it was meant to save.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def cache_entries(rows: list[RepoRow], machine: str) -> dict[str, dict[str, str]]:
    """One machine's cache entries as the rows define them: every description
    written for its clones, against the digest of the work it describes.

    An unwritten description is not stored: the placeholder is what the report
    shows when nobody has written one yet.
    """
    entries: dict[str, dict[str, str]] = {}
    for row in rows:
        state = row.states.get(machine)
        text = row.descriptions.get(machine, "")
        if state and state.work_digest and text and text != PENDING_DESCRIPTION:
            entries[row.slug] = {"digest": state.work_digest, "description": text}
    return entries


def cache_payload(entries: dict[str, dict[str, str]]) -> str:
    return json.dumps({"version": CACHE_VERSION, "entries": entries}, ensure_ascii=False, indent=1)


def save_local_cache(path: Path, rows: list[RepoRow], machine: str) -> None:
    """Write this machine's cache file.

    A whole-fleet run rebuilds it from the rows rather than merging into what was
    loaded, so a repo that went clean and a superseded digest drop out without a
    prune of their own — this side has just seen every one of that machine's repos,
    so what it writes is the complete cache.

    A SCOPED run has seen exactly one, and that sentence stops being true of it.
    Rebuilding there would replace a warm cache with a single entry and say nothing,
    so every other repo would be re-read on the next fleet run — the same silent
    erasure a `--report` re-render caused in 2026-09-19, arriving by a different
    door. So a scoped run merges: the repo it looked at overwrites, and the ones it
    never looked at carry through untouched, because having no opinion about a repo
    is not evidence that its entry is stale.
    """
    entries = cache_entries(rows, machine)
    if only_slug() is not None:
        entries = load_cache(path) | entries
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache_payload(entries), encoding="utf-8")


def peer_write_program(remote_path: str, payload: str, merge: bool) -> bytes:
    """A standalone program that writes one file on the peer, destination and
    contents both inlined as literals so neither has to survive a shell.

    Any string put through `json.dumps` is also a valid Python string literal —
    JSON's escapes are a subset of Python's — and it escapes every non-ASCII
    character, so the program is pure ASCII whatever a description contains and the
    far side cannot decode its own source wrongly. The directory is created here
    rather than by a second remote command, which is what makes one hop enough.

    `merge` is what a scoped run needs and is why the merge runs THERE rather than
    here: this side has seen one of the peer's repos and holds no copy of the
    entries for the rest, so it cannot compose the union it wants written. The far
    side can — it is sitting on the file. A version mismatch or an unreadable file
    merges into nothing, matching `load_cache`: every entry is re-derivable, so the
    worst a bad file costs is the reading it was meant to save.
    """
    keep = ("prior = {}\n"
            "try:\n"
            "    old = json.loads(p.read_text(encoding='utf-8'))\n"
            f"    if isinstance(old, dict) and old.get('version') == {CACHE_VERSION}:\n"
            "        prior = old.get('entries') or {}\n"
            "except Exception:\n"
            "    pass\n"
            "fresh = json.loads(text)\n"
            "fresh['entries'] = {**prior, **fresh['entries']}\n"
            "text = json.dumps(fresh, ensure_ascii=False, indent=1)\n") if merge else ""
    return ("import json, pathlib\n"
            f"p = pathlib.Path({json.dumps(remote_path)})\n"
            f"text = {json.dumps(payload)}\n"
            + keep +
            "p.parent.mkdir(parents=True, exist_ok=True)\n"
            "p.write_text(text, encoding='utf-8')\n").encode("ascii")


def save_peer_cache(peer_ssh: str, peer_python: str, remote_path: str, rows: list[RepoRow], machine: str) -> str:
    """Write the peer's own clones' descriptions back to the peer, and return what
    went wrong, or "" on success.

    The destination path and the payload both ride on stdin, inside a program sent
    to `<peer_python> -` exactly as the scan's hop sends this script. Nothing
    variable reaches the remote command string, and that is the whole design:
    sshd hands that string to whatever shell the peer defaults to, which on Windows
    is cmd.exe. There `'…'` quotes nothing, `mkdir` has no `-p` and rejects `/` as a
    separator, `cat` does not exist, and `&`, `|`, `<`, `>`, `^` and `%` are
    metacharacters. An earlier `mkdir -p '<dir>' && cat > '<path>'` therefore failed
    on every run against a Windows peer with "The syntax of the command is
    incorrect.", while the same line works against a POSIX one — so the cache warmed
    in one direction only. Bare metacharacter-free tokens tokenize identically under
    both shells, which is why the scan hop never had the problem.

    On a whole-fleet run the file is replaced whole, because this side has just seen
    every one of that machine's repos, so what it writes is the complete cache
    rather than a patch needing a merge. A scoped run has seen one of them and asks
    the far side to merge instead — see `peer_write_program`.
    """
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={PEER_CONNECT_TIMEOUT}", peer_ssh,
           f"{peer_python} -"]
    try:
        with tempfile.TemporaryFile() as fin, tempfile.TemporaryFile() as ferr:
            fin.write(peer_write_program(remote_path, cache_payload(cache_entries(rows, machine)),
                                         merge=only_slug() is not None))
            fin.seek(0)
            done = subprocess.run(cmd, stdin=fin, stdout=subprocess.DEVNULL, stderr=ferr, timeout=PEER_CONNECT_TIMEOUT + 30)
            if done.returncode != 0:
                ferr.seek(0)
                return ferr.read().decode("utf-8", "replace").strip() or f"ssh exited {done.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)
    return ""


def store_descriptions(snapshots: list[MachineSnapshot], rows: list[RepoRow],
                       local: str, peer_ssh: str | None, peer_python: str) -> None:
    """Send each machine's descriptions to the machine whose clones they describe.

    Which is the whole point of splitting the cache: a line written here about a
    clone that lives on the peer is stored there, so a report run from that machine
    tomorrow already has it and neither side ever reads the same diff twice.

    A peer that cannot be written to is named rather than swallowed. Nothing is
    lost that a re-read would not recover, but the silent version of this failure
    is a cache that never warms while every run reports work reused.
    """
    save_local_cache(cache_file(), rows, local)
    for snap in snapshots:
        if snap.name == local or snap.status != "ok":
            continue
        if not peer_ssh or not snap.cache_path:
            print(f"WARNING: {snap.name}'s descriptions were not stored — "
                  f"{'no PEER_SSH is configured' if not peer_ssh else 'it did not report where its cache lives'}. "
                  f"They will be written again next run.", file=sys.stderr)
            continue
        if problem := save_peer_cache(peer_ssh, peer_python, snap.cache_path, rows, snap.name):
            print(f"WARNING: {snap.name}'s descriptions could not be stored on it ({problem}). "
                  f"They will be written again next run.", file=sys.stderr)


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

    # Both travel as environment rather than as arguments, because the scan that reads them runs
    # several calls below this one and, in peer mode, on the other machine entirely.
    if c := flag_value(argv, "--cache"):
        os.environ["GHS_CACHE"] = c
    if "--no-cache" in argv:
        os.environ["GHS_NO_CACHE"] = "1"

    # The scope is resolved to a slug here, on the machine that has the path, and
    # every reader below — including the peer's own process — sees only the slug.
    if "--repo" in argv:
        scope = resolve_repo_scope(flag_value(argv, "--repo") or ".")
        if scope is None:
            return 2
        os.environ["GHS_ONLY_SLUG"] = scope

    # A scoped run writes NO HTML: one repo's worth of it is a page to open and scroll
    # for something the table beside it already said in one line, and the fleet report
    # carries that repo anyway. It still needs a state file, which `--report` reads —
    # under its own name, since sharing the fleet run's would leave a one-repo state
    # file for the next `--report` to render and store both machines' caches from.
    stem = f"repo-status-{only_slug().replace('/', '-')}" if only_slug() else "github-status"
    state_path = Path(flag_value(argv, "--state") or tmp_dir() / f"{stem}-state.json")
    html_path = Path(flag_value(argv, "--html") or tmp_dir() / "github-status.html")
    if only_slug() and flag_value(argv, "--html"):
        print("ERROR: --html is not available with --repo — a scoped run reports to the "
              "terminal only.", file=sys.stderr)
        return 2

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
        reached_names = [s.name for s in snapshots if s.status == "ok"]
        apply_descriptions(rows, text.strip() or "{}", reached_names)
        store_descriptions(snapshots, rows, this_machine_name(config), config_value(config, "PEER_SSH"), peer_interpreter(config))
        # The state file is this run's working set and this mode is what fills it in, so what was
        # just applied belongs back in it. Without this write it goes on saying `<analyze below>`
        # for every cell described here, and a second --report — one to re-render at another
        # width, say — reads those placeholders, renders them, and rebuilds both machines' caches
        # from them. Measured 2026-09-19: one such re-render replaced a twelve-entry cache with an
        # empty one, said nothing, and the next scan reported every description as still to write.
        state_path.write_text(state_to_json(snapshots, rows), encoding="utf-8")
        render(snapshots, rows, target_width(config))
        if only_slug() is None:
            owner = rows[0].slug.split("/", 1)[0] if rows else github_user()
            write_html(html_path, rows, snapshots, owner)
            print(f"\nHTML report: file:///{str(html_path).replace(os.sep, '/').lstrip('/')}")
        return 0

    snapshots = gather(config)
    if snapshots is None:
        return 2
    rows = merge(snapshots)
    # A scoped run that matched nothing must say so. Without this it renders an empty
    # table, which is indistinguishable from the repo being found and having nothing
    # outstanding — the one answer a scoped run exists to give, and so the one it must
    # never give by accident.
    if (wanted := only_slug()) and not rows:
        reached = ", ".join(s.name for s in snapshots if s.status == "ok") or "no machine"
        print(f"ERROR: {wanted} was not found on {reached}.\n"
              f"It has to sit under that machine's PROJECTS_ROOT, within ROOT_DEPTH levels,\n"
              f"with `origin` owned by {github_user()} — and not be one of the hard exclusions "
              f"({', '.join(sorted(EXCLUDED))}).", file=sys.stderr)
        return 2
    reached_names = [s.name for s in snapshots if s.status == "ok"]
    # A description is a pure function of the work it describes, so an unchanged digest means last
    # run's line is still true and this clone does not have to be read again. Each machine resolved
    # that for its own clones during the scan; nothing is looked up here. Everything the scan itself
    # costs — the fetch, the `gh` call — asks the remote a question no local state could answer, and
    # is not cached at all.
    reused = 0
    for row in rows:
        for machine in row.working(reached_names):
            state = row.states.get(machine)
            text = state.cached_description if state else ""
            row.descriptions[machine] = text or PENDING_DESCRIPTION
            reused += bool(text)
    render(snapshots, rows, target_width(config))
    to_write = sum(1 for r in rows for m in r.working(reached_names)
                   if r.descriptions.get(m) == PENDING_DESCRIPTION)
    if reused or to_write:
        print(f"\nDescriptions: {reused} reused from the cache, {to_write} still to write.")
    print_detail(rows, multi=sum(s.status == "ok" for s in snapshots) > 1)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state_to_json(snapshots, rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
