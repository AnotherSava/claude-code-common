#!/usr/bin/env python3
"""The convention-adoption engine: the steps on one side, a repo's record on the other.

    python conventions.py steps                        every step: version, slug, title, scope
    python conventions.py status <repo-root>           the gap, and what is still pending there
    python conventions.py record <repo-root> <version> <state> <note>
    python conventions.py audit <repo-root>            re-derive every recorded line
    python conventions.py selftest                     the authoring gate
    python conventions.py probe|apply|verify <version|slug> <repo-root> [--dry-run]

One module owns all of it because the record is the only durable answer to "was
this repo skipped, or missed?", and a second reader of that file drifts from the
first the day one of them gains a column. The `/adopt` skill and the
`conventions-check.py` hook both come through here, so the format lives in one
place; the last three subcommands are pass-throughs that locate a step's script
from its frontmatter, so no caller has to know the file layout either.

`record` runs the step's own `verify` before it will write `applied`, and refuses
on anything but 0. That is what makes "the number was bumped but the work was not
done" unreachable — the one failure nothing later can detect, because every later
reader trusts the record rather than the repo.

`audit` is the opposite direction: it re-derives every line that was written,
because the record is a claim about a moment, not a continuous guarantee. Where a
retired script can no longer justify a pass it prints NOT COVERED rather than
silence, since a check that cannot tell "passed" from "never ran" turns an open
problem into a closed-looking one.

Exit codes, uniform across the subcommands here: 0 ok · 1 bad invocation · 2 the
engine refuses and a human has to fix something (a duplicate version, a record
file that will not parse) · 3 an assertion failed (verify said no, audit found
drift, selftest failed). Step scripts answer on a different table — 0 applies,
1 does not apply, 2 cannot tell, 3 error — and the two must not be confused. The
`probe`/`apply`/`verify` pass-throughs return the step's own code untouched, so
a caller reading one of those is reading the step's table and not this one.

No YAML anywhere: PyYAML is not in the standard library, the hook that imports
this runs under `python -S`, and the record is read with `str.split("\t")` on
both machines.
"""

import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

SKILL_DIR = os.path.dirname(os.path.realpath(__file__))
STEPS_DIR = os.path.join(SKILL_DIR, "steps")
FIXTURES_DIR = os.path.join(STEPS_DIR, "fixtures")
# <repo>/claude/skills/adopt -> <repo>. `realpath` above resolves the ~/.claude/skills symlink, so
# this is the checkout even when the module was reached through the installed path.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))

RECORD_REL = ".claude/conventions.tsv"
LOCAL_REL = ".claude/conventions.local.tsv"
STATES = ("applied", "n/a", "declined")
SCOPES = ("repo", "machine")
# Whose repos adopt these conventions. A clone of someone else's project is exempt with no opt-out
# file anywhere — see `~/.claude/memory/user_github_account.md`.
OWNER = "AnotherSava"
ORIGIN_URL_RE = re.compile(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$")
# The five a step's prose must answer. `Fetch before running` is deliberately not here: it is
# required only of a step that deletes or rewrites a committed file, which no probe can decide.
HEADINGS = ("Applies when", "Does not apply when", "Cannot tell", "Verify", "By hand, after the script")
STEP_TIMEOUT = 120

FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)[ \t]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# ` #` opens a trailing comment, as it does in the YAML this block is written to look like —
# `references/authoring-a-step.md` documents the frontmatter with exactly such comments, and a
# reader that kept them would turn `version: 7   # allocated max+1` into a step with no version.
COMMENT_RE = re.compile(r"[ \t]+#.*$")

RECORD_HEADER = ("# Which convention versions from the claude dotfiles repo this repo has decided.",
                 "# Written only by /adopt, and only after the step's own verify passed in the same run.",
                 "# version\tslug\tstate\tdate\tnote")
LOCAL_HEADER = ("# Machine-scoped convention versions wired for this repo ON THIS MACHINE.",
                "# Gitignored on purpose: a fresh clone has genuinely not done the machine-side work,",
                "# so it must read as pending there rather than inherit the other machine's answer.",
                "# version\tslug\tstate\tdate\tnote")


class StepError(Exception):
    """A step set that cannot be read at all — a duplicate version, a broken frontmatter block.

    Raised rather than returned because every caller's answer is the same: stop. A duplicate
    `version:` in particular must never resolve to a silent winner, since `latest` is derived
    from the set and two steps sharing a number make the derivation arbitrary.
    """


class Step(NamedTuple):
    version: int
    slug: str
    title: str
    scope: str
    prose: str
    script: str | None        # a runnable path, or None when there is nothing to run
    declared_script: str      # the frontmatter value, "" when absent — selftest asserts it exists
    retracted: int | None
    supersedes: int | None


class Record(NamedTuple):
    version: int
    slug: str
    state: str
    date: str
    note: str


class Ledger(NamedTuple):
    committed: dict[int, Record]
    local: dict[int, Record]
    files: tuple[str, ...]    # the record files that exist; empty means this repo has no record
    exempt: str               # the reason, when the repo carries an `exempt` line
    exempt_from: str          # which of the two files carried it — one is gitignored, one travels
    error: str                # the full sentence to print when a line would not parse


# ---------------------------------------------------------------- steps


def _read_frontmatter(path: str) -> dict[str, str]:
    """The `---` block at the head of a step's prose, as flat `key: value` pairs.

    Only the head is read, so the hook pays for a few hundred bytes per step rather than the
    whole prose file. A line inside the block that is neither blank, a comment, nor a
    `key: value` pair aborts instead of being skipped: a mistyped `version : 3` that parses to
    nothing would otherwise drop the step out of the set with no message anywhere.
    """
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as handle:
        if handle.readline().strip() != "---":
            raise StepError(f"{name} does not open with a --- frontmatter block")
        data: dict[str, str] = {}
        for line in handle:
            text = line.rstrip("\r\n")
            if text.strip() == "---":
                return data
            if not text.strip() or text.lstrip().startswith("#"):
                continue
            match = FIELD_RE.match(text)
            if not match:
                raise StepError(f"{name} frontmatter holds a line this reader cannot classify: {text!r}")
            value = COMMENT_RE.sub("", match.group(2)).strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            data[match.group(1).casefold()] = value
    raise StepError(f"{name} frontmatter has no closing ---")


def _int_field(data: dict[str, str], key: str, name: str) -> int | None:
    raw = data.get(key, "")
    if not raw:
        return None
    if not raw.lstrip("v").isdigit():
        raise StepError(f"{name} has {key}: {raw!r}, which is not a version number")
    return int(raw.lstrip("v"))


def _step_from(path: str) -> Step:
    data = _read_frontmatter(path)
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    version = _int_field(data, "version", name)
    if version is None:
        raise StepError(f"{name} declares no version")
    slug, title, scope = data.get("slug", ""), data.get("title", ""), data.get("scope", "")
    if slug != stem:
        raise StepError(f"{name} declares slug: {slug!r}, which does not match its filename")
    if not title:
        raise StepError(f"{name} declares no title")
    if scope not in SCOPES:
        raise StepError(f"{name} declares scope: {scope!r}; it must be one of {', '.join(SCOPES)}")
    retracted, supersedes = _int_field(data, "retracted", name), _int_field(data, "supersedes", name)
    if retracted is not None and supersedes is not None:
        raise StepError(f"{name} carries both retracted: and supersedes:; a reversal and a correction are different things")
    declared = data.get("script", "")
    candidate = os.path.join(STEPS_DIR, declared or f"{slug}.py")
    return Step(version, slug, title, scope, path, candidate if os.path.isfile(candidate) else None,
                declared, retracted, supersedes)


def load_steps() -> list[Step]:
    """Every step in this checkout, ascending by version.

    A duplicate version is a hard stop rather than a last-one-wins tie, because `latest` is
    `max(version)` over this list and two steps sharing a number make every "N versions behind"
    claim downstream arbitrary.
    """
    try:
        names = sorted(n for n in os.listdir(STEPS_DIR) if n.endswith(".md"))
    except OSError as exc:
        raise StepError(f"no readable steps directory at claude/skills/adopt/steps ({exc.strerror})") from exc
    steps = [_step_from(os.path.join(STEPS_DIR, name)) for name in names]
    seen: dict[int, str] = {}
    for step in steps:
        if step.version in seen:
            raise StepError(f"v{step.version} is declared twice: {seen[step.version]}.md and {step.slug}.md")
        seen[step.version] = step.slug
    return sorted(steps, key=lambda s: s.version)


def find_step(steps: list[Step], key: str) -> Step | None:
    """One step by version number or by slug — /adopt walks versions, a human types either."""
    wanted = key.lstrip("v")
    for step in steps:
        if step.slug == key or (wanted.isdigit() and step.version == int(wanted)):
            return step
    return None


def dotfiles_sha() -> str:
    """The short sha of this dotfiles checkout, read from .git without forking.

    Every message that claims a "latest" version names this, so the claim is always qualified by
    the checkout it was derived from — the two machines are routinely at different commits, and a
    behind checkout reporting a repo as current is the one wrong answer this system must not give.
    """
    git_dir = os.path.join(REPO, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()
    except OSError:
        return "unknown"
    if not head.startswith("ref:"):
        return head[:7] or "unknown"
    ref = head.split(":", 1)[1].strip()
    try:
        with open(os.path.join(git_dir, *ref.split("/")), encoding="utf-8") as handle:
            return handle.read().strip()[:7] or "unknown"
    except OSError:
        pass
    try:
        with open(os.path.join(git_dir, "packed-refs"), encoding="utf-8") as handle:
            for line in handle:
                sha, _, name = line.partition(" ")
                if name.strip() == ref:
                    return sha[:7]
    except OSError:
        pass
    return "unknown"


# ---------------------------------------------------------------- the record


def _parse_record_line(text: str) -> Record | str:
    """One record line as a Record, or the reason it is not one."""
    fields = text.split("\t", 4)
    if len(fields) != 5:
        return f"{len(fields)} tab-separated field(s), expected 5 (version, slug, state, date, note)"
    version, slug, state, date, note = fields
    if not version.isdigit():
        return f"{version!r} is not a version number"
    if state not in STATES:
        return f"{state!r} is not one of {', '.join(STATES)}"
    if not DATE_RE.match(date):
        return f"{date!r} is not a YYYY-MM-DD date"
    if not slug:
        return "the slug column is empty"
    return Record(int(version), slug, state, date, note)


def _read_record_file(path: str) -> tuple[dict[int, Record], str, str]:
    """(records, exempt reason, error sentence) for one record file.

    Only a missing file reads as "no records". Every other way of failing to read one — a
    permission bit, a half-written file, bytes that are not UTF-8 — is an error sentence, because
    "the file is not there" and "the file is there and could not be read" are different facts and
    the second one silently loses committed decisions: the next `record` rewrites the file from a
    dict that never held them. `utf-8-sig` because Notepad and PowerShell's `Out-File` write a BOM,
    which would otherwise land as a parse error pointing at the header comment.
    """
    try:
        with open(path, encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        return {}, "", ""
    except (OSError, UnicodeDecodeError) as exc:
        return {}, "", f".claude/{os.path.basename(path)} could not be read ({exc})."
    rel = os.path.basename(path)
    records: dict[int, Record] = {}
    for number, raw in enumerate(lines, 1):
        text = raw.rstrip("\r")
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        if text.split("\t")[0] == "exempt":
            reason = text.split("\t", 1)[1].strip() if "\t" in text else ""
            if not reason:
                return records, "", f".claude/{rel} could not be parsed (line {number}): an exempt line must name its reason."
            return records, reason, ""
        parsed = _parse_record_line(text)
        if isinstance(parsed, str):
            return records, "", f".claude/{rel} could not be parsed (line {number}): {parsed}."
        if parsed.version in records:
            # Two lines for one version is what both machines walking the same pending step
            # produces, and the last one silently won: `status` reported one line for a two-line
            # file and the next `record` deleted the other. `load_steps` refuses a duplicate step
            # version for the same reason — an arbitrary winner is not an answer.
            return records, "", (f".claude/{rel} could not be parsed (line {number}): v{parsed.version} "
                                 f"already has a line above this one, and which of the two decided it is not recoverable.")
        records[parsed.version] = parsed
    return records, "", ""


def read_ledger(root: str) -> Ledger:
    """Both record files for `root`, read once. The only reader of either file."""
    committed_path, local_path = os.path.join(root, *RECORD_REL.split("/")), os.path.join(root, *LOCAL_REL.split("/"))
    committed, exempt, error = _read_record_file(committed_path)
    local, local_exempt, local_error = _read_record_file(local_path)
    files = tuple(p for p in (committed_path, local_path) if os.path.isfile(p))
    exempt_from = RECORD_REL if exempt else (LOCAL_REL if local_exempt else "")
    return Ledger(committed, local, files, exempt or local_exempt, exempt_from, error or local_error)


def parse_error_message(ledger: Ledger) -> str:
    """The sentence shown when a record file will not parse — one wording, two callers."""
    return f"{ledger.error} Conventions state is unknown — /adopt will not run until it is fixed."


def decided(ledger: Ledger) -> dict[int, Record]:
    """Every version with a line in either file. A line anywhere closes contiguity."""
    return {**ledger.committed, **ledger.local}


def adopted_through(steps: list[Step], ledger: Ledger) -> int:
    """Derived, never stored: max(v) such that every step <= v holds a line somewhere.

    Derived because a stored number and the lines beneath it drift apart the moment one is
    edited by hand, and the number is the half everything downstream believes.
    """
    lines, through = decided(ledger), 0
    for step in steps:
        if step.version not in lines:
            break
        through = step.version
    return through


def pending_steps(steps: list[Step], ledger: Ledger) -> list[Step]:
    """Steps this repo holds no line for, in either file."""
    lines = decided(ledger)
    return [step for step in steps if step.version not in lines]


def unwired_machine_steps(steps: list[Step], ledger: Ledger) -> list[Step]:
    """Machine-scoped steps the repo has decided but this machine has not wired.

    The committed record travels and the local one does not, so a repo can arrive already
    carrying a decision whose machine half — a symlink, a per-machine wrapper — does not exist
    here. That is pending work on this machine and nowhere else, which is why it renders as its
    own line rather than as part of the version gap.

    Only an `applied` line counts. An `n/a` or a `declined` for a machine step is a fact about the
    repo — no `.claude/memory/` to point at — so there is nothing for any machine to wire, and
    reading those as unwired would put a permanent bullet in front of every one of them.
    """
    return [s for s in steps if s.scope == "machine" and s.version not in ledger.local
            and s.version in ledger.committed and ledger.committed[s.version].state == "applied"]


def is_repo(root: str) -> bool:
    """Whether a record written here would be tracked by anything. A worktree's `.git` is a file."""
    return os.path.exists(os.path.join(root, ".git"))


def git_directory(root: str) -> str | None:
    """Where this checkout's git metadata lives. A worktree's `.git` is a file pointing elsewhere."""
    path = os.path.join(root, ".git")
    if os.path.isdir(path):
        return path
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("gitdir:"):
            target = line.split(":", 1)[1].strip()
            return target if os.path.isabs(target) else os.path.normpath(os.path.join(root, target))
    return None


def origin_owner(root: str) -> str | None:
    """The account owning `origin`, read out of `.git/config` as text. None when there is none.

    None and "someone else" are different answers: a repo with no remote yet is still one of ours
    and still adopts, while a clone of someone else's project never does.

    This lives here rather than in the hook because `/adopt` asks the same question and has to get
    the same answer. It did not: the hook was correctly silent in the `agterm` clone while `status`
    offered to walk thirteen steps there, which ends in a record file committed to a repo that is
    not ours. One predicate, one answer.
    """
    git_dir = git_directory(root)
    if git_dir is None:
        return None
    # A linked worktree's `.git` file points at `<main>/.git/worktrees/<name>`, which holds no
    # `config` of its own — the remote is two levels up, in the main checkout's `.git`.
    for candidate in (os.path.join(git_dir, "config"),
                      os.path.join(os.path.dirname(os.path.dirname(git_dir)), "config")):
        try:
            with open(candidate, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        section = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                section = stripped.replace(" ", "").casefold()
            elif section == '[remote"origin"]' and stripped.split("=")[0].strip().casefold() == "url":
                match = ORIGIN_URL_RE.search(stripped.split("=", 1)[1].strip())
                return match.group(1) if match else None
        return None
    return None


def is_third_party(root: str) -> str | None:
    """The owner's name when this repo belongs to someone else, else None."""
    owner = origin_owner(root)
    return owner if owner is not None and owner.casefold() != OWNER.casefold() else None


def record_targets(root: str, step: Step, state: str, ledger: Ledger) -> list[tuple[str, dict[int, Record], tuple[str, ...]]]:
    """Which of the two files a line belongs in: (path, the lines already there, that file's header).

    A `scope: repo` step writes one line, to the committed record. A machine-scoped one writes to
    the gitignored local file, because a fresh clone has genuinely not made the symlink or written
    the per-machine wrapper and must show that work as pending there.

    An `applied` machine step writes **both**, and those two lines say different things: the
    committed one is the repo's decision, which travels, and the local one is this machine having
    actually wired it, which does not. That pair is what lets a fresh clone report the step as
    decided-but-not-wired here rather than either re-asking it or inheriting the other machine's
    answer. An `n/a` or a `declined` writes only the committed file — "there is no
    `.claude/memory/` to point at" is a fact about the repo, true on every machine, and burying it
    in the gitignored file would have each machine answer it again.
    """
    committed = (os.path.join(root, *RECORD_REL.split("/")), ledger.committed, RECORD_HEADER)
    local = (os.path.join(root, *LOCAL_REL.split("/")), ledger.local, LOCAL_HEADER)
    if step.scope != "machine":
        return [committed]
    return [local, committed] if state == "applied" else [committed]


def write_record(path: str, step: Step, state: str, note: str, date: str,
                 known: dict[int, Record], header: tuple[str, ...]) -> str:
    """Write one line into one record file, sorted by version. Returns the state it replaced, or "".

    Rewrites the whole file rather than appending so the sort order holds without anyone
    maintaining it, and keeps every comment line it found at the head — the header is the file's
    own statement of what an `applied` line is allowed to mean.

    The lines already in the file arrive as `known`, parsed once by the caller's `read_ledger`,
    rather than being re-read here: a second parse is a second chance to disagree with the first
    about a file this is about to overwrite.
    """
    existing = dict(known)
    replaced = existing[step.version].state if step.version in existing else ""
    existing[step.version] = Record(step.version, step.slug, state, date, " ".join(note.split()))
    comments: list[str] = []
    try:
        with open(path, encoding="utf-8-sig") as handle:
            comments = [line.rstrip("\r\n") for line in handle if line.lstrip().startswith("#")]
    except OSError:
        comments = list(header)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = [f"{r.version}\t{r.slug}\t{r.state}\t{r.date}\t{r.note}" for r in sorted(existing.values())]
    # newline="\n" so the committed record never shows up as a whole-file line-ending diff between
    # the two machines, and a trailing newline so an append from either side is a one-line diff.
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join([*comments, *body]) + "\n")
    return replaced


# ---------------------------------------------------------------- running a step


def run_step(step: Step, command: str, root: str, extra: tuple[str, ...] = ()) -> tuple[int, str, str]:
    """Run one step script and capture it. The only place this module forks.

    PYTHONDONTWRITEBYTECODE keeps a __pycache__ out of the steps directory: a step that imports a
    sibling skill's module would otherwise leave compiled copies in the tree, and a stale one
    reports on source that no longer exists (learnings/python-stale-bytecode-cache.md).
    """
    if not step.script:
        return 3, "", f"v{step.version} {step.slug} has no script to run"
    argv = [sys.executable, step.script, command, root, *extra]
    try:
        done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                              timeout=STEP_TIMEOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return 3, "", f"{step.slug}.py {command} did not finish within {STEP_TIMEOUT}s"
    except OSError as exc:
        return 3, "", f"{step.slug}.py {command} could not be started: {exc}"
    return done.returncode, (done.stdout or "").strip(), (done.stderr or "").strip()


def _indent(text: str, prefix: str = "      ") -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines() if line.strip())


# ---------------------------------------------------------------- subcommands


def _usage(form: str) -> int:
    print(f"usage: conventions.py {form}")
    return 1


def _steps_or_refuse() -> tuple[list[Step], int]:
    try:
        return load_steps(), 0
    except StepError as exc:
        print(f"step set refused: {exc}")
        return [], 2


def cmd_steps() -> int:
    steps, bad = _steps_or_refuse()
    if bad:
        return bad
    print(f"{len(steps)} step(s), latest v{steps[-1].version if steps else 0}, dotfiles at {dotfiles_sha()}")
    for step in steps:
        marks = []
        if not step.script:
            marks.append("judgement")
        if step.retracted is not None:
            marks.append(f"retracted at v{step.retracted}")
        if step.supersedes is not None:
            marks.append(f"supersedes v{step.supersedes}")
        tail = f"  [{', '.join(marks)}]" if marks else ""
        print(f"  v{step.version:<3} {step.slug:<28} {step.scope:<8} {step.title}{tail}")
    return 0


def cmd_status(root: str) -> int:
    steps, bad = _steps_or_refuse()
    if bad:
        return bad
    ledger = read_ledger(root)
    print(f"repo: {root}")
    print(f"dotfiles at {dotfiles_sha()}, latest v{steps[-1].version if steps else 0}")
    if not is_repo(root):
        # Three real project directories on this machine have no `.git`. Walking the steps there
        # would end in a record file no clone ever sees, reported as written — so the walk stops
        # at the same sentence the session-start notice prints, rather than looking normal.
        print("conventions cannot be recorded here: this is not a git repo")
        return 2
    other = is_third_party(root)
    if other is not None:
        print(f"this repo's origin belongs to {other}, not {OWNER}: it adopts nothing, and the "
              f"session-start notice stays silent here")
        return 0
    if ledger.error:
        print(parse_error_message(ledger))
        return 2
    if ledger.exempt:
        print(f"exempt — {ledger.exempt} (from {ledger.exempt_from})")
        return 0
    lines = decided(ledger)
    if not ledger.files:
        print("no record file: this repo has never recorded where it stands")
    else:
        counts = {state: sum(1 for r in lines.values() if r.state == state) for state in STATES}
        print(f"recorded: {len(lines)} line(s) — " + ", ".join(f"{n} {state}" for state, n in counts.items()))
    latest = steps[-1].version if steps else 0
    ahead = sorted(v for v in lines if v > latest)
    if ahead:
        # The hook says this too, but its systemMessage never reaches the transcript, so /adopt reads
        # the gap from here. Without this line a repo recorded against a newer step set reads as
        # current, and the walk runs against a step list older than the record it is trusting.
        print(f"this record names v{', v'.join(str(v) for v in ahead)}, above the newest step in this "
              f"dotfiles checkout (v{latest}): pull the dotfiles repo before adopting anything here")
    pending, unwired = pending_steps(steps, ledger), unwired_machine_steps(steps, ledger)
    print(f"adopted through v{adopted_through(steps, ledger)}; {len(pending)} step(s) pending")
    for step in pending:
        note = f"  (retracted at v{step.retracted} — record n/a)" if step.retracted is not None else ""
        print(f"  v{step.version:<3} {step.slug:<28} {step.scope:<8} {step.title}{note}")
    for step in unwired:
        print(f"  v{step.version:<3} {step.slug:<28} {step.scope:<8} decided in this repo, not wired on this machine")
    return 0


def cmd_record(root: str, key: str, state: str, note: str) -> int:
    steps, bad = _steps_or_refuse()
    if bad:
        return bad
    ledger = read_ledger(root)
    if not is_repo(root):
        print("conventions cannot be recorded here: this is not a git repo, so the record would be "
              "a file nothing tracks and no clone ever sees")
        return 2
    other = is_third_party(root)
    if other is not None:
        print(f"this repo's origin belongs to {other}, not {OWNER}: nothing is recorded in a clone "
              f"of someone else's project")
        return 2
    if ledger.error:
        print(parse_error_message(ledger))
        return 2
    if ledger.exempt:
        print(f"this repo is exempt — {ledger.exempt} (from {ledger.exempt_from}). Nothing is recorded here.")
        return 2
    step = find_step(steps, key)
    if step is None:
        print(f"no step {key!r} in this dotfiles checkout (dotfiles at {dotfiles_sha()})")
        return 2
    if state not in STATES:
        print(f"{state!r} is not a state; use one of {', '.join(STATES)}")
        return 1
    if not note.strip():
        print("a note is required: it is where the reason, or the per-item assertion, stays durable")
        return 1
    if state == "applied":
        if not step.script:
            print(f"v{step.version} {step.slug} has no verify to run, so it can never be recorded applied — "
                  f"record n/a or declined with the answer as the note")
            return 3
        code, out, err = run_step(step, "verify", root)
        if out:
            print(_indent(out, "  "))
        if err:
            print(_indent(err, "  "))
        if code != 0:
            print(f"refusing to record applied: {step.slug}.py verify exited {code}, not 0")
            return 3
    today = datetime.date.today().isoformat()
    for path, known, header in record_targets(root, step, state, ledger):
        replaced = write_record(path, step, state, note, today, known, header)
        where = os.path.relpath(path, root).replace(os.sep, "/")
        print(f"recorded v{step.version} {step.slug} {state} in {where}" + (f" (replacing {replaced})" if replaced else ""))
    return 0


def cmd_audit(root: str) -> int:
    steps, bad = _steps_or_refuse()
    if bad:
        return bad
    ledger = read_ledger(root)
    print(f"repo: {root}")
    print(f"dotfiles at {dotfiles_sha()}, latest v{steps[-1].version if steps else 0}")
    if ledger.error:
        print(parse_error_message(ledger))
        return 2
    if ledger.exempt:
        print(f"exempt — {ledger.exempt} (from {ledger.exempt_from})")
        return 0
    lines, tally = decided(ledger), {"ok": 0, "not covered": 0, "judgement": 0, "FAILED": 0}
    for version in sorted(lines):
        record, step = lines[version], find_step(steps, str(version))
        head = f"  v{version:<3} {record.state:<8} {record.slug:<28}"
        if step is None:
            tally["not covered"] += 1
            print(f"{head} NOT COVERED: no step v{version} in this dotfiles checkout")
            continue
        verdict, detail = _audit_one(step, record, root)
        tally[verdict] += 1
        print(f"{head} {detail}")
    pending = pending_steps(steps, ledger)
    verdicts = ", ".join(f"{n} {name}" for name, n in tally.items() if n) or "nothing to re-derive"
    print(f"{len(lines)} recorded: {verdicts}. {len(pending)} step(s) never decided.")
    return 3 if tally["FAILED"] else 0


def _audit_one(step: Step, record: Record, root: str) -> tuple[str, str]:
    """One recorded line re-derived. Never blocks on a human: a question is reported, not asked."""
    if record.state == "declined":
        return "judgement", "declined by the user — not re-checked"
    if step.retracted is not None and record.state == "n/a":
        return "judgement", f"retracted at v{step.retracted} — not re-checked"
    if not step.script:
        # An `applied` line can only have been written after a verify ran, so a step with no
        # script now once had one: that is a retirement, and a pass it can no longer justify.
        if record.state == "applied":
            return "not covered", "NOT COVERED: the step's script has been retired"
        return "judgement", "judgement — not re-checkable"
    command = "verify" if record.state == "applied" else "probe"
    code, out, err = run_step(step, command, root)
    first = (out or err or "").splitlines()
    # The step's own first line, where it printed one. A script that says nothing about its own
    # refusal gets "said nothing" rather than a dangling dash promising a reason that is not there.
    reason = first[0].strip() if first else "the step printed no reason"
    if record.state == "applied":
        if code == 0:
            return "ok", "ok — still in the target shape"
        if code == 2:
            return "not covered", f"NOT COVERED: {reason}"
        return "FAILED", f"FAILED: verify exited {code} — {reason}"
    if code == 1:
        return "ok", f"ok — still does not apply ({reason})"
    if code == 0:
        return "FAILED", "FAILED: probe now says this step applies here"
    if code == 2:
        # The line was written by a human answering this exact refusal, so the refusal repeating is
        # the expected steady state, not an uncovered check. NOT COVERED stays reserved for a script
        # that can no longer justify a pass it once made; a NOT COVERED nothing can ever clear is
        # where a real one goes unnoticed.
        return "judgement", f"the user's answer to a question the step still cannot settle — {reason}"
    return "FAILED", f"FAILED: probe exited {code} — {reason}"


def cmd_passthrough(command: str, key: str, root: str, extra: tuple[str, ...]) -> int:
    """probe / apply / verify for one step, with the script located from its frontmatter.

    Output is not captured: /adopt shows the step's own words to the user, and a dry run that
    reached the terminal through this module reads exactly as it will when it runs for real.
    """
    steps, bad = _steps_or_refuse()
    if bad:
        return bad
    step = find_step(steps, key)
    if step is None:
        print(f"no step {key!r} in this dotfiles checkout (dotfiles at {dotfiles_sha()})")
        return 2
    if not step.script:
        print(f"v{step.version} {step.slug} is judgement only — read {step.slug}.md and answer its question")
        return 2
    try:
        return subprocess.run([sys.executable, step.script, command, root, *extra],
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=STEP_TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        print(f"{step.slug}.py {command} did not finish within {STEP_TIMEOUT}s")
        return 3
    except OSError as exc:
        print(f"{step.slug}.py {command} could not be started: {exc}")
        return 3


# ---------------------------------------------------------------- selftest


def _check(results: list[bool], ok: bool, label: str, detail: str = "") -> bool:
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok and detail:
        print(_indent(detail))
    return ok


def _snapshot(root: str) -> dict[str, str]:
    """Content hash per file, so "mutated nothing" is an assertion rather than a hope.

    `.git` is skipped: a step that asks git anything at all rewrites an index or a log there,
    and that churn says nothing about the tree the step was pointed at.
    """
    out: dict[str, str] = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in sorted(files):
            path = os.path.join(base, name)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, root).replace(os.sep, "/")] = hashlib.sha1(handle.read()).hexdigest()
    return out


def _rmtree(path: str) -> None:
    """Remove a scratch tree, including the read-only files `git init` leaves in it.

    Loose objects are written mode 444, which on Windows is the read-only attribute and makes
    `DeleteFile` refuse; `ignore_errors=True` would then leave a whole `.git` in the temp
    directory once per fixture per run, silently. Making everything writable first is what the
    `onexc` chmod handler does, without depending on which Python the other machine runs.
    """
    for base, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(base, name), 0o700)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def _seed_fixture(src: str, dest: str) -> str:
    """Copy a fixture and make the copy a real repo, so a step that reads git has git to read.

    Fixtures ship as plain trees — a nested `.git` inside this repo would be a gitlink nobody
    wants — and several steps genuinely need one: `HEAD` holds the pre-migration file a per-item
    assertion is checked against, and `git check-ignore` has no answer outside a work tree. The
    global hooks path and excludes file are pointed at paths that do not exist, so this machine's
    own pre-commit hook and ignore rules cannot reach into the fixture and change what it means.
    """
    shutil.copytree(src, dest)
    if os.path.exists(os.path.join(dest, ".git")):
        return ""
    common = ["-c", f"core.hooksPath={os.path.join(dest, 'no-hooks')}",
              "-c", f"core.excludesFile={os.path.join(dest, 'no-excludes')}",
              "-c", "commit.gpgsign=false", "-c", "user.name=selftest", "-c", "user.email=selftest@localhost"]
    steps = (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "--no-verify", "-m", "fixture"])
    for argv in steps:
        try:
            done = subprocess.run(["git", "-C", dest, *common, *argv], capture_output=True,
                                  encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            return f"git {argv[0]} failed: {exc}"
        if done.returncode != 0:
            return f"git {argv[0]} exited {done.returncode}: {(done.stderr or '').strip()}"
    return ""


def _selftest_before(step: Step, work: str, results: list[bool]) -> None:
    """The `before/` half: a verify that can tell "not in shape", then the apply round trip.

    Whether the apply round trip is owed is read off `probe`, never off `apply`'s own exit code.
    A step with no apply path — where the target shape is reachable only by a human, as a LICENSE
    or a compose rename is — has a `probe` that cannot return 0, so `/adopt` never reaches its
    apply and there is nothing to assert. Inferring the same thing from a non-zero `apply` made a
    step whose apply *crashed* on its own fixture indistinguishable from one that has none, and
    the four assertions that prove the migration works were skipped with the gate still green.
    """
    clean = _snapshot(work)
    code, out, err = run_step(step, "verify", work)
    _check(results, code == 3, f"v{step.version} verify on before/ exits 3, not a vacuous pass (got {code})", out or err)
    probe, probe_out, probe_err = run_step(step, "probe", work)
    _check(results, probe in (0, 1, 2), f"v{step.version} probe on before/ answers 0, 1 or 2, never a traceback (got {probe})", probe_err)
    dry, dry_out, dry_err = run_step(step, "apply", work, ("--dry-run",))
    _check(results, _snapshot(work) == clean, f"v{step.version} verify, probe and apply --dry-run mutate nothing")
    if probe != 0:
        # Printed rather than counted: an assertion that did not run must not add an `ok` to the
        # tally, which is what "not run must not look like passed" is about.
        print(f"  ----  v{step.version} apply round trip NOT ASSERTED: probe on before/ exits {probe}, "
              f"so /adopt never reaches apply in a repo shaped like this")
        print(_indent(probe_out or probe_err))
        return
    if not _check(results, dry == 0, f"v{step.version} apply --dry-run on before/ exits 0 (got {dry})", dry_out or dry_err):
        return
    code, out, err = run_step(step, "apply", work)
    if not _check(results, code == 0, f"v{step.version} apply on before/ exits 0 (got {code})", out or err):
        return
    code, out, err = run_step(step, "verify", work)
    _check(results, code == 0, f"v{step.version} verify after apply exits 0 (got {code})", out or err)
    again, out, err = run_step(step, "apply", work)
    _check(results, again in (0, 3), f"v{step.version} a second apply exits 0 or 3, never a crash (got {again})", err)
    code, out, err = run_step(step, "verify", work)
    _check(results, code == 0, f"v{step.version} verify after the second apply still exits 0 (got {code})", out or err)


def _selftest_fixture(step: Step, results: list[bool]) -> None:
    """Every fixture tree, on copies so the fixtures themselves cannot be damaged.

    The `conformant/` assertions run whatever happened to `before/`: that tree is the path most
    repos in the fleet actually take, and a step whose apply is missing or broken is exactly the
    one whose free `applied` line for the conformant majority still has to be proven.

    Any further directory beside those two is a tree the step must **refuse**: `apply` exits 3 and
    writes nothing. That is idempotence rule 6 — abort rather than skip — and it is the rule a
    fixture is most needed for, since `before/` cannot carry it: `before/` is the tree apply has
    to transform, so a line that stops apply there would turn the gate red.
    """
    base = os.path.join(FIXTURES_DIR, step.slug)
    before, conformant = os.path.join(base, "before"), os.path.join(base, "conformant")
    print(f"  v{step.version} {step.slug}")
    have_before = _check(results, os.path.isdir(before), f"v{step.version} fixtures/{step.slug}/before/ exists")
    have_conformant = _check(results, os.path.isdir(conformant), f"v{step.version} fixtures/{step.slug}/conformant/ exists")
    try:
        refusals = sorted(n for n in os.listdir(base) if n not in ("before", "conformant") and os.path.isdir(os.path.join(base, n)))
    except OSError:
        refusals = []
    scratch = tempfile.mkdtemp(prefix=f"conventions-selftest-{step.slug}-")
    # A `scope: machine` step asserts a path outside the repo — this machine's own Claude state
    # directory — so exercising one here would write into `~/.claude/projects` and leave a link
    # behind pointing at a scratch tree that no longer exists. Every step resolves that directory
    # as `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`, so pointing the variable at the scratch tree
    # sandboxes the machine half exactly as `_seed_fixture` sandboxes git's hooks path and
    # excludes file. A repo-scoped step never reads it and is unaffected.
    sandbox = os.path.join(scratch, "claude-config")
    os.makedirs(os.path.join(sandbox, "projects"))
    outer = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = sandbox
    try:
        if have_before:
            work = os.path.join(scratch, "before")
            failure = _seed_fixture(before, work)
            if _check(results, not failure, f"v{step.version} before/ copied into a scratch repo", failure):
                _selftest_before(step, work, results)
        if have_conformant:
            work = os.path.join(scratch, "conformant")
            failure = _seed_fixture(conformant, work)
            if _check(results, not failure, f"v{step.version} conformant/ copied into a scratch repo", failure):
                if step.scope == "machine":
                    # The machine half of a machine-scoped step belongs to a machine and not to a
                    # committed tree, so no fixture can arrive already carrying it — the path it
                    # asserts is named after wherever the copy happens to sit. Wiring it into the
                    # sandbox above is what makes "already in the target shape" a state this tree
                    # can be in; what `conformant/` then proves is that verify passes on it and
                    # touches nothing, which is the path most repos in the fleet take.
                    code, out, err = run_step(step, "apply", work)
                    _check(results, code == 0, f"v{step.version} conformant/ wired into the sandboxed config dir (got {code})", out or err)
                shape = _snapshot(work)
                code, out, err = run_step(step, "verify", work)
                _check(results, code == 0, f"v{step.version} verify on conformant/ exits 0 (got {code})", out or err)
                _check(results, _snapshot(work) == shape, f"v{step.version} verify on conformant/ mutated nothing")
        for name in refusals:
            work = os.path.join(scratch, name)
            failure = _seed_fixture(os.path.join(base, name), work)
            if _check(results, not failure, f"v{step.version} {name}/ copied into a scratch repo", failure):
                shape = _snapshot(work)
                code, out, err = run_step(step, "apply", work)
                _check(results, code == 3, f"v{step.version} apply on {name}/ refuses with exit 3 (got {code})", out or err)
                _check(results, _snapshot(work) == shape, f"v{step.version} apply on {name}/ wrote nothing")
    finally:
        if outer is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = outer
        _rmtree(scratch)


def _missing_headings(prose: str, wanted: tuple[str, ...] = HEADINGS) -> list[str]:
    try:
        with open(prose, encoding="utf-8") as handle:
            present = {line.strip()[3:].strip() for line in handle if line.startswith("## ")}
    except OSError as exc:
        return [f"unreadable ({exc.strerror})"]
    return [heading for heading in wanted if heading not in present]


def cmd_selftest() -> int:
    """The authoring gate: what has to hold before the fleet runs any of this.

    The pair that matters most is `verify` failing on `before/` and passing on `conformant/`.
    Without the first, a verify that returns 0 on anything at all would hand every repo an
    applied line and the record would say the work was done nowhere it was.
    """
    print(f"steps: claude/skills/adopt/steps (dotfiles at {dotfiles_sha()})")
    results: list[bool] = []
    try:
        steps = load_steps()
    except StepError as exc:
        _check(results, False, "the step set loads", str(exc))
        return 3
    versions = [step.version for step in steps]
    _check(results, bool(steps), f"the steps directory holds at least one step (found {len(steps)})")
    _check(results, versions == list(range(1, len(versions) + 1)),
           f"versions are unique and contiguous from 1 (found {versions})")
    for step in steps:
        if step.declared_script:
            _check(results, step.script is not None, f"v{step.version} declares script: {step.declared_script}, and it exists")
        missing = _missing_headings(step.prose)
        _check(results, not missing, f"v{step.version} {step.slug}.md carries all five headings",
               "missing: " + ", ".join(missing) if missing else "")
        for field, value in (("retracted", step.retracted), ("supersedes", step.supersedes)):
            if value is not None:
                _check(results, value in versions, f"v{step.version} {field}: v{value} names a step that exists")
        older = find_step(steps, str(step.supersedes)) if step.supersedes in versions else None
        if older is not None:
            # Both halves or neither: a correction that does not reach back leaves the wrong step
            # reading as current to anyone who opens it, which is where a repo short of it looks.
            _check(results, not _missing_headings(older.prose, ("Superseded",)),
                   f"v{older.version} carries the ## Superseded section v{step.version} corrects it with")
    for step in steps:
        if step.script:
            _selftest_fixture(step, results)
        elif os.path.isdir(os.path.join(FIXTURES_DIR, step.slug)):
            # Fixtures with no script is a script that went missing — a rename, a bad merge — and
            # it reads downstream as "judgement only", which asks every repo a question and makes
            # `applied` unrecordable forever. A step that is judgement by design ships no fixtures.
            _check(results, False, f"v{step.version} {step.slug} has fixtures but no {step.slug}.py",
                   "a judgement-only step ships no fixtures, so this is a script that has gone missing")
        else:
            print(f"  ----  v{step.version} {step.slug} is judgement only — no script to exercise")
    failed = results.count(False)
    print(f"\n{len(results)} assertion(s), {failed} failed.")
    return 3 if failed else 0


# ---------------------------------------------------------------- dispatch


def main() -> int:
    args = sys.argv[1:]
    command = args[0] if args else ""
    rest = args[1:]
    if command == "steps":
        return cmd_steps()
    if command in ("status", "audit"):
        if len(rest) != 1:
            return _usage(f"{command} <repo-root>")
        handler = cmd_status if command == "status" else cmd_audit
        return handler(os.path.abspath(rest[0]))
    if command == "record":
        if len(rest) < 4:
            return _usage("record <repo-root> <version> <state> <note>")
        return cmd_record(os.path.abspath(rest[0]), rest[1], rest[2], " ".join(rest[3:]))
    if command in ("probe", "apply", "verify"):
        flags = tuple(a for a in rest if a.startswith("--"))
        plain = [a for a in rest if not a.startswith("--")]
        if len(plain) != 2:
            return _usage(f"{command} <version|slug> <repo-root> [--dry-run]")
        return cmd_passthrough(command, plain[0], os.path.abspath(plain[1]), flags)
    if command == "selftest":
        return cmd_selftest()
    return _usage("{steps|status|record|audit|selftest|probe|apply|verify}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Close to the hooks' never-raise guard, and deliberately not identical to it: a hook owes
        # the harness SystemExit(0) whatever happened, while an engine that exited 0 on a crash
        # would report a line it never wrote and a gate that never ran. So the traceback goes to
        # stderr, through the interpreter's own hook rather than an import nothing else needs,
        # and the code stays 3. Nothing reaches the caller as an unhandled exception either way.
        sys.excepthook(*sys.exc_info())
        raise SystemExit(3)
