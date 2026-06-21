#!/usr/bin/env python3
"""repos-status — scan PROJECTS_ROOT for git repos owned by GITHUB_USER,
fetch each one's origin, and report each repo's branch, last-pushed date,
unpushed count, behind count, and uncommitted state. Prints a table to
stdout plus per-repo detail sections for uncommitted and unpushed work.

Each run performs `git fetch --quiet` per repo in parallel before reading
state, so `last_pushed` / `unpushed` / `behind` reflect the current remote.

After collecting state, repos with inbound commits (`REMOTE > 0`) and no
uncommitted changes (`LOCAL` empty) are auto-pulled with `git pull
--ff-only --quiet`. Successful pulls are marked with a trailing `✓` in
the REMOTE column (the original behind count is preserved for display).

Each owned repo's open-issue count is fetched via `gh issue list` (in
parallel, pinned to the repo's own origin) and shown in the ISSUES column;
a repo with open issues but no pending git work still earns a row. Repos
with no open issues, issues disabled, or where `gh` is unavailable/unauthed
leave the cell blank.

The table fills a target width (--width / GHS_WIDTH, else the terminal,
else 120); the DESCRIPTION column is elastic, taking the leftover width and
wrapping long text across lines.

Modes:
  (default)        scan PROJECTS_ROOT and print the report
  --render [FILE]  skip the scan and render a final table from a JSON spec
                   read from FILE (or stdin) — used by SKILL.md step 3 to
                   draw the table with DESCRIPTION cells filled in
  --width N        target total table width (also accepted via GHS_WIDTH)

Environment:
  PROJECTS_ROOT — directory to scan (overrides config/config.env)
  GITHUB_USER   — origin-URL owner to filter by (default AnotherSava)
  ROOT_DEPTH    — find -maxdepth value (default 4)
  GHS_WIDTH     — target table width (else terminal width, then 120)

If PROJECTS_ROOT is not set and config/config.env is missing, exits with
status 2 — the github-status SKILL.md is expected to prompt the user and
create the config file before invoking.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

EXCLUDED: set[str] = {"notion", "claude-mermaid-fix"}


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


@dataclass
class Repo:
    project: str
    branch: str
    last_pushed: str
    sort_iso: str
    unpushed: str
    behind: str
    uncommitted: int
    changes: list[str]  # raw porcelain lines ("M  path", "?? path", " D path"…)
    unpushed_commits: list[str]  # "hash subject" lines for @{upstream}..HEAD
    oldest_epoch: float  # Unix timestamp of oldest pending file mtime or unpushed commit; 0 if none
    lines_added: int  # tracked-only: sum of additions in `git diff HEAD --numstat`
    lines_deleted: int  # tracked-only: sum of deletions in `git diff HEAD --numstat`
    pulled: bool = False  # set True if `git pull --ff-only` succeeded after state collection
    open_issues: int | None = None  # open-issue count via `gh`; None if gh unavailable/failed


def git(args: list[str], cwd: Path) -> str:
    """Run git; return stdout with trailing newlines removed.

    NOTE: we cannot use .strip() — porcelain output's first line can legally
    start with a space (X=' ' for unstaged-only changes), and a blanket strip
    would corrupt the column alignment.
    """
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


def find_repos(root: Path, depth: int) -> list[Path]:
    """Walk `root` up to `depth` levels and return directories containing `.git`.

    Mirrors the previous `find -maxdepth <depth> -name .git` semantics in
    pure Python — works identically on Linux, macOS, and Windows (where
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
    """Run `git fetch --quiet` in one repo. Swallow failures (offline, dead remote)."""
    subprocess.run(
        ["git", "-C", str(repo), "fetch", "--quiet"],
        capture_output=True, timeout=30,
    )


def fetch_all(repos: list[Path]) -> None:
    if not repos:
        return
    with ThreadPoolExecutor(max_workers=min(16, len(repos))) as ex:
        list(ex.map(fetch_one, repos))


def pull_one(repo: Path) -> bool:
    """Attempt fast-forward pull. Return True on success.

    --ff-only refuses to create a merge commit if the branch has diverged
    (local has unpushed commits AND remote has inbound commits), so this
    is safe to run unconditionally on the eligible set.
    """
    r = subprocess.run(
        ["git", "-C", str(repo), "pull", "--ff-only", "--quiet"],
        capture_output=True, timeout=60,
    )
    return r.returncode == 0


def pull_eligible(repo_rows: list[tuple[Path, "Repo"]]) -> None:
    """Pull repos with inbound commits and no uncommitted changes.

    Sets `row.pulled = True` for each repo where the fast-forward pull
    succeeded. The row's `behind` field is intentionally NOT updated, so
    the REMOTE column keeps showing the original count alongside the ✓ mark.
    """
    eligible = [(p, r) for p, r in repo_rows
                if r.behind not in {"", "0"} and r.uncommitted == 0]
    if not eligible:
        return
    print(f"Pulling {len(eligible)} clean repo(s)...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=min(16, len(eligible))) as ex:
        results = list(ex.map(lambda pr: pull_one(pr[0]), eligible))
    for (_, row), ok in zip(eligible, results):
        row.pulled = ok


ORIGIN_SLUG = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def origin_slug(repo: Path) -> str | None:
    """Return 'OWNER/REPO' parsed from the repo's `origin` URL, or None."""
    m = ORIGIN_SLUG.search(git(["remote", "get-url", "origin"], repo))
    return f"{m['owner']}/{m['repo']}" if m else None


def open_issue_count(repo: Path) -> int | None:
    """Return the count of open issues (PRs excluded) on the repo's OWN fork.

    Targets the `origin` slug explicitly with `--repo` — without it, `gh`
    auto-resolves a fork to its `upstream` parent and would report the
    parent's issues instead of the user's. Returns None on any failure — gh
    not installed, not authenticated, origin not on GitHub, issues disabled
    on the fork, or unparseable output — so the caller can leave the ISSUES
    cell blank rather than show a bogus 0 or someone else's count.
    """
    slug = origin_slug(repo)
    if not slug:
        return None
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


def fill_issue_counts(repo_rows: list[tuple[Path, "Repo"]]) -> None:
    """Populate `row.open_issues` for each (path, row) pair, in parallel.

    Run over every owned repo, not just the pending-work set — a repo with
    open issues but a clean, pushed tree earns a place in the table on issues
    alone, so its count must be known before the display filter is applied.
    """
    if not repo_rows:
        return
    print(f"Counting open issues for {len(repo_rows)} repo(s)...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=min(16, len(repo_rows))) as ex:
        results = list(ex.map(lambda pr: open_issue_count(pr[0]), repo_rows))
    for (_, row), count in zip(repo_rows, results):
        row.open_issues = count


def discover_owned(projects_root: Path, github_user: str, depth: int) -> list[tuple[Path, str]]:
    """Return [(repo_path, rel_to_root)] for repos whose origin matches github_user."""
    owner_pat = re.compile(rf"github\.com[:/]{re.escape(github_user)}/")
    owned: list[tuple[Path, str]] = []
    for repo in find_repos(projects_root, depth):
        # Forward slashes everywhere (PurePath.as_posix) — on Windows the native
        # separator is a backslash, which mangles when the project name round-
        # trips through JSON / shell heredocs in the SKILL's --render step.
        rel = repo.relative_to(projects_root).as_posix()
        if rel in EXCLUDED:
            continue
        origin = git(["remote", "get-url", "origin"], repo)
        if owner_pat.search(origin):
            owned.append((repo, rel))
    return owned


def collect_state(repo: Path, rel: str) -> Repo:
    branch = git(["symbolic-ref", "--short", "HEAD"], repo) or "(detached)"
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], repo)
    unpushed_commits: list[str] = []
    candidates: list[float] = []
    if upstream:
        sort_iso = git(["log", "-1", "--format=%cI", upstream], repo)
        last_pushed = git(["log", "-1", "--format=%cs", upstream], repo)
        unpushed = git(["rev-list", "--count", f"{upstream}..HEAD"], repo)
        behind = git(["rev-list", "--count", f"HEAD..{upstream}"], repo)
        if unpushed not in {"", "0"}:
            log = git(["log", f"{upstream}..HEAD", "--format=%h %s"], repo)
            unpushed_commits = [l for l in log.splitlines() if l]
            # %ct = committer epoch; last line is oldest commit since log is newest-first.
            cts = git(["log", f"{upstream}..HEAD", "--format=%ct"], repo).splitlines()
            if cts:
                candidates.append(float(cts[-1]))
    else:
        sort_iso = "0000-00-00T00:00:00"
        last_pushed = ""
        unpushed = ""
        behind = ""
    changes = [l for l in git(["status", "--porcelain"], repo).splitlines() if l]
    for line in changes:
        path = line[3:]
        if " -> " in path:  # rename: "old -> new" — use new
            path = path.split(" -> ", 1)[1]
        try:
            candidates.append((repo / path).stat().st_mtime)
        except (FileNotFoundError, OSError):
            pass  # deleted in workdir; no mtime recoverable
    oldest_epoch = min(candidates) if candidates else 0.0

    # Line-count diff across tracked files (staged + unstaged combined). Binary
    # files show "-\t-\tpath" in --numstat and are skipped.
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
    for path in git(["ls-files", "--others", "--exclude-standard"], repo).splitlines():
        if not path:
            continue
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

    return Repo(rel, branch, last_pushed, sort_iso, unpushed, behind, len(changes), changes, unpushed_commits, oldest_epoch, lines_added, lines_deleted)


# (header, key, value_fn) for every potentially-visible column.
# `key` is the visibility identifier (matched in `visible_columns`).
# Widths are computed dynamically at render time as max(header_len, max value
# length) — the box border already adds 1 space of padding on each side via
# "│ {cell} │", so we don't need any extra padding math.
# Rows are filtered to those with pending work and sorted by AGE ascending
# (freshest first) — see filter + sort in `main`.
COLUMN_SPECS = [
    ("PROJECT",     "project",     lambda r: r.project),
    ("BRANCH",      "branch",      lambda r: r.branch),
    ("UNPUSHED",    "unpushed",    lambda r: r.unpushed if r.unpushed not in ("", "0") else ""),
    ("REMOTE",      "remote",      lambda r: (f"{r.behind} ✓" if r.pulled else r.behind) if r.behind not in ("", "0") else ""),
    ("LOCAL",       "local",       lambda r: format_local(r.uncommitted, r.lines_added, r.lines_deleted)),
    ("AGE",         "age",         lambda r: human_age(time.time() - r.oldest_epoch) if r.oldest_epoch else ""),
    ("ISSUES",      "issues",      lambda r: str(r.open_issues) if r.open_issues else ""),
    ("DESCRIPTION", "description", lambda r: "<analyze below>" if (r.unpushed_commits or r.changes) else "—"),
]


def visible_columns(show_branch: bool, show_unpushed: bool, show_remote: bool,
                    show_local: bool, show_age: bool, show_issues: bool, show_description: bool):
    skip = set()
    if not show_branch:
        skip.add("branch")
    if not show_unpushed:
        skip.add("unpushed")
    if not show_remote:
        skip.add("remote")
    if not show_local:
        skip.add("local")
    if not show_age:
        skip.add("age")
    if not show_issues:
        skip.add("issues")
    if not show_description:
        skip.add("description")
    return [c for c in COLUMN_SPECS if c[1] not in skip]


# Column keys whose HEADER renders centered (values stay left-aligned).
CENTERED_HEADERS = {"unpushed", "remote", "local", "age", "issues"}

# Minimum width the DESCRIPTION column is allowed to shrink to before we stop
# honoring the total-width budget — below this, wrapping produces unreadable
# one-or-two-word ribbons, so we let the table overflow instead.
DESC_MIN_WIDTH = 18


def target_width() -> int:
    """Total table width to fill. Resolved in order: GHS_WIDTH env var, the
    GHS_WIDTH line in config.env, then the detected terminal width (120 if
    that can't be queried — e.g. stdout is a pipe under the Bash tool).

    The DESCRIPTION column stretches to consume whatever this width leaves
    after the fixed columns, so the table spans the full target width.
    """
    config = Path(__file__).resolve().parent.parent / "config" / "config.env"
    val = config_value(config, "GHS_WIDTH")
    if val and val.isdigit():
        return int(val)
    return shutil.get_terminal_size((120, 24)).columns


def print_table(rows, cols) -> None:
    headers = [h for h, _, _ in cols]
    keys = [k for _, k, _ in cols]
    value_lists = [[str(fn(r)) for r in rows] for (_, _, fn) in cols]
    # Column width = max(header, longest value). The "│ {cell} │" rendering
    # already provides one space of padding on each side, so no extra math.
    widths = [max(len(h), max((len(v) for v in vs), default=0))
              for h, vs in zip(headers, value_lists)]

    # DESCRIPTION is the elastic column: it takes whatever width is left after
    # the fixed columns so the table fills the full target width — expanding to
    # pad short text out to the right edge, wrapping text too long to fit. The
    # floor keeps it readable on very narrow screens (the table overflows the
    # target instead of crushing the column below it).
    n = len(cols)
    table_chrome = 3 * n + 1  # "│ " + " │ "*(n-1) + " │" per row line
    desc_i = keys.index("description") if "description" in keys else None
    if desc_i is not None:
        others = sum(w for i, w in enumerate(widths) if i != desc_i)
        budget = target_width() - others - table_chrome
        widths[desc_i] = max(budget, DESC_MIN_WIDTH, len(headers[desc_i]))

    # Per cell, the list of physical lines it occupies (wrapping only ever
    # splits the description column; every other cell is a single line).
    def cell_lines(ci: int, value: str) -> list[str]:
        if ci == desc_i and len(value) > widths[ci]:
            return textwrap.wrap(value, widths[ci]) or [""]
        return [value]

    bar = lambda left, mid, right: left + mid.join("─" * (w + 2) for w in widths) + right
    header_cells = [
        f"{h:^{w}}" if k in CENTERED_HEADERS else f"{h:<{w}}"
        for h, k, w in zip(headers, keys, widths)
    ]
    print(bar("┌", "┬", "┐"))
    print("│ " + " │ ".join(header_cells) + " │")
    print(bar("├", "┼", "┤"))
    for ri in range(len(rows)):
        col_lines = [cell_lines(ci, value_lists[ci][ri]) for ci in range(n)]
        for line in range(max(len(c) for c in col_lines)):
            cells = [c[line] if line < len(c) else "" for c in col_lines]
            print("│ " + " │ ".join(f"{cells[ci]:<{widths[ci]}}" for ci in range(n)) + " │")
    print(bar("└", "┴", "┘"))


def print_changes_detail(rows: list[Repo]) -> None:
    """For each repo with uncommitted work, list every porcelain entry.

    Porcelain status is XY where X (staged) / Y (unstaged) may be a space —
    swap spaces for a center dot so columns line up visually.
    """
    dirty = [r for r in rows if r.changes]
    if not dirty:
        return
    print("\nUncommitted changes:")
    for r in dirty:
        print(f"\n{r.project}:")
        for line in r.changes:
            code = line[:2].replace(" ", "·")
            print(f"  {code}{line[2:]}")


def print_unpushed_detail(rows: list[Repo]) -> None:
    """For each repo with unpushed commits, list `git log @{upstream}..HEAD`.

    Claude is expected to read this section and produce one-line descriptions
    per repo (see SKILL.md step 3). The DESCRIPTION table column is just a
    pointer; the actual prose comes from the model, not the script.
    """
    pending = [r for r in rows if r.unpushed_commits]
    if not pending:
        return
    print("\nUnpushed commits (for Claude to summarize per repo):")
    for r in pending:
        print(f"\n{r.project} ({len(r.unpushed_commits)}):")
        for line in r.unpushed_commits:
            print(f"  {line}")


def config_value(config_file: Path, key: str) -> str | None:
    """Resolve a setting: the `key` env var first, else its `KEY=value` line
    in config.env. Returns None if neither is present."""
    if val := os.environ.get(key):
        return val
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def resolve_projects_root(config_file: Path) -> str | None:
    return config_value(config_file, "PROJECTS_ROOT")


def render_from_json(text: str) -> None:
    """Render a final table from a JSON spec (used by SKILL.md step 3).

    Lets the skill hand back the rows with DESCRIPTION cells filled in and
    reuse this script's wrapping/width-budget renderer instead of hand-drawing
    a box table. Input shape:

        {"columns": ["project", "local", "issues", "description"],
         "rows": [{"project": "claude", "local": "20 (+669/-52)",
                   "issues": "", "description": "..."}, ...]}

    `columns` lists column keys in display order; each row is a dict keyed by
    those same keys. Unknown keys fall back to an upper-cased header.
    """
    data = json.loads(text)
    header_by_key = {k: h for h, k, _ in COLUMN_SPECS}
    cols = [(header_by_key.get(k, k.upper()), k, lambda r, k=k: str(r.get(k, ""))) for k in data["columns"]]
    print_table(data["rows"], cols)


def main() -> int:
    # Windows consoles default to a legacy codepage (e.g. cp1251) that can't
    # encode the Unicode box-drawing characters used in the table, nor decode
    # UTF-8 JSON on stdin (--render mode). Force UTF-8 on all three streams so
    # the script works identically across platforms.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    # Explicit width: `--width N` overrides detection/config for this run (the
    # skill detects the real terminal width and passes it, since a piped stdout
    # hides it from get_terminal_size). Fed through GHS_WIDTH so target_width
    # picks it up uniformly.
    argv = sys.argv[1:]
    if "--width" in argv:
        i = argv.index("--width")
        if i + 1 < len(argv) and argv[i + 1].isdigit():
            os.environ["GHS_WIDTH"] = argv[i + 1]

    # Render-only mode: read a JSON table spec and print it, skipping the whole
    # scan — used by SKILL.md step 3 to draw the final filled table. Reads the
    # file path given after --render, or stdin if none is supplied.
    if "--render" in sys.argv[1:]:
        rest = sys.argv[sys.argv.index("--render") + 1:]
        text = Path(rest[0]).read_text(encoding="utf-8") if rest and not rest[0].startswith("-") else sys.stdin.read()
        render_from_json(text)
        return 0

    github_user = os.environ.get("GITHUB_USER", "AnotherSava")
    depth = int(os.environ.get("ROOT_DEPTH", "4"))
    skill_dir = Path(__file__).resolve().parent.parent
    config_file = skill_dir / "config" / "config.env"

    projects_root = resolve_projects_root(config_file)
    if not projects_root:
        print(
            f"ERROR: PROJECTS_ROOT is not set and {config_file} is missing.\n"
            "Run the github-status skill (/github-status) — it will prompt for\n"
            "the projects root and write the config file before invoking this.",
            file=sys.stderr,
        )
        return 2

    pr_path = Path(projects_root).expanduser()
    if not pr_path.is_dir():
        print(f"ERROR: PROJECTS_ROOT does not exist: {pr_path}", file=sys.stderr)
        return 2

    owned = discover_owned(pr_path, github_user, depth)
    print(f"Fetching {len(owned)} repos...", file=sys.stderr)
    fetch_all([repo for repo, _ in owned])

    repo_rows = [(repo, collect_state(repo, rel)) for repo, rel in owned]
    pull_eligible(repo_rows)
    # Issue counts for every owned repo — a repo can earn a table row on open
    # issues alone, so the count must be known before the display filter.
    fill_issue_counts(repo_rows)
    # Keep repos with something to report: uncommitted local changes, unpushed
    # commits, remote-inbound commits (including ones we just auto-pulled —
    # surfaced once with the ✓ marker, then drop out next run), or open issues.
    rows = [
        r for _, r in repo_rows
        if r.unpushed_commits or r.changes or r.behind not in ("", "0") or r.open_issues
    ]
    # Sort by AGE ascending: freshest pending work first, oldest at bottom.
    # Sorting by oldest_epoch descending achieves this since age = now - epoch.
    rows.sort(key=lambda r: r.oldest_epoch, reverse=True)

    show_branch = any(r.branch not in {"main", "master"} for r in rows)
    show_unpushed = any(r.unpushed not in {"", "0"} for r in rows)
    show_remote = any(r.behind not in {"", "0"} for r in rows)
    show_local = any(r.uncommitted for r in rows)
    show_age = any(r.oldest_epoch for r in rows)
    show_issues = any(r.open_issues for r in rows)
    show_description = any(r.unpushed_commits or r.changes for r in rows)
    cols = visible_columns(show_branch, show_unpushed, show_remote, show_local, show_age, show_issues, show_description)

    print_table(rows, cols)
    print_changes_detail(rows)
    print_unpushed_detail(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
