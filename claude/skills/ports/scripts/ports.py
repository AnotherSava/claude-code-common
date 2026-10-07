#!/usr/bin/env python3
"""Hand out and record the TCP ports the projects on this machine take.

Nothing recorded who owned which number. Five projects declared a dev port in a globally-gitignored
`config/deploy.env`, others pinned theirs in a package script, a Rust default or a compose file, and
the deploy skill's entire allocation rule was a regex guess over a package.json with `3000` as its
fallback — which is printlab's dev port. Two numbers then collided per the 2026-10-05 survey,
and the one that cost a day was a `tailscale serve` mapping fronting a dev server from the port that
server had to bind.

So one record, committed in the dotfiles repo, keyed by use case:

    ports.py allocate --use-case <slug> --owner <repo> --notes <text> [--port N] [--front-for N]
    ports.py amend --use-case <slug> [--notes <text>] [--pinned <why>] [--front-for N]
    ports.py get --use-case <slug>         # the recorded port, exit 1 if the use case has none
    ports.py list [--scope S] [--status S]
    ports.py release --use-case <slug>
    ports.py check [--live] [--repo PATH]

`allocate` assigns and `amend` corrects, and they are the only writers. `allocate` is idempotent on
the use case and never changes a claim it finds, so a launch script may call it on every run; what a
recorded claim says is changed by `amend` instead. Both print the port alone on stdout so a shell
script can take the answer inline. Diagnostics go to stderr.

Three scopes, because only one of them is a namespace where sharing is a defect:

  machine    a port on THIS machine's TCP space, at any address. Uniqueness is enforced here, and a
             `tailscale serve` front port belongs to it: the mapping holds the wildcard address, so
             while it exists no local process can bind that number.
  remote     a port on another host — the shared VPS, the desktop box's media servers. Recorded so a
             number someone will recognise has an owner; never checked for uniqueness.
  container  a port inside a Docker network, where four apps sharing 3000 is correct. Recorded so the
             four are not read as a collision.

Liveness is an oracle in neither direction, which is why allocation reads both the record and the
machine. Nineteen file-claimed ports had no process behind them at the time of the survey, so probing
alone would reassign a port a project owns but is not running; four live listeners were claimed by no
file anywhere, so the record alone would hand out a port the OS already holds.

Writing the registry dirties the dotfiles repo. That is the point — it is the first cross-repo record
of these numbers — but it means an allocation made while working in some other project leaves a diff
behind in this one, to be committed by the session that owns it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

import file_lock  # noqa: E402  — sibling skill module, reachable only after the path insert above
import port_probe  # noqa: E402

# `$CLAUDE_PORTS_REGISTRY` points the tool at another registry, which is how the conventions gate and
# this skill's own tests get a deterministic one instead of whatever this machine happens to hold —
# the same role `$GIT_CONFIG_GLOBAL` plays for the gitignore rule.
REGISTRY = Path(os.environ.get("CLAUDE_PORTS_REGISTRY") or Path(__file__).resolve().parents[1] / "registry.json")
# Machine-local, so the lock does not sit as an untracked file inside the committed skill directory.
LOCK = Path.home() / ".claude" / "ports-state" / "registry.lock"
VERSION = 1

# Where a new claim is drawn from. Chosen around the dev ports already in use (3939 onward) so every
# allocated number reads as one of this fleet's, and clear of the exclusions below.
POOL_LOW, POOL_HIGH = 3900, 3999

SCOPES = ("machine", "remote", "container")
STATUSES = ("assigned", "reserved")
MACHINES = ("macos", "windows")

# https://fetch.spec.whatwg.org/#port-blocking — every browser refuses these with ERR_UNSAFE_PORT, and
# Next exits before binding one. A port here is unusable for anything a browser must reach.
BLOCKED = frozenset({
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79, 87, 95, 101, 102, 103,
    104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137, 138, 139, 143, 161, 179, 389, 427, 465, 512,
    513, 514, 515, 526, 530, 531, 532, 540, 548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719,
    1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6679, 6697,
    10080,
})

# Below 1024 needs root. The ephemeral range is where the kernel hands out source ports, so a long-lived
# listener parked there can lose a race at boot — RoboForm was observed on 49188 and 51671, and both
# numbers move between runs, which is why no claim records them.
PRIVILEGED_HIGH = 1023
EPHEMERAL_LOW, EPHEMERAL_HIGH = 49152, 65535

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED = ("port", "use_case", "owner", "scope", "status", "notes")
OPTIONAL = ("pinned", "front_for", "machines")


def _note(text: str) -> None:
    print(f"NOTE: {text}", file=sys.stderr)


def needs_pinning(port: int) -> Optional[str]:
    """Why `port` is a number nobody should be handed by accident, or None.

    A claim on one of these is legitimate — the discard port is claimed precisely because nothing can
    listen there — but it has to say so, which is what `pinned` records.
    """
    if port in BLOCKED:
        return "blocked by the WHATWG port-blocking set, so every browser refuses the URL"
    if port <= PRIVILEGED_HIGH:
        return "below 1024, so binding it needs root"
    if EPHEMERAL_LOW <= port <= EPHEMERAL_HIGH:
        return "inside the ephemeral range the kernel allocates source ports from"
    return None


# ── the registry ──────────────────────────────────────────────────────────────


def read_registry() -> Dict:
    """The registry as written, or raise. An unreadable registry is never an empty one.

    A missing file would otherwise read as "nothing is claimed", which is the answer that hands out a
    port five projects are already using.
    """
    with REGISTRY.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ValueError(f"{REGISTRY} is not a registry: expected an object with a `claims` list")
    return data


def write_registry(data: Dict) -> None:
    """Replace the registry atomically, claims sorted so a diff shows one added object."""
    data["claims"] = sorted(data["claims"], key=lambda c: (c.get("port", 0), c.get("use_case", "")))
    handle, tmp = tempfile.mkstemp(dir=str(REGISTRY.parent), prefix="registry.", suffix=".tmp")
    try:
        # Text mode translates "\n" to CRLF on Windows, which rewrites every line ending of a file the
        # repo keeps LF on disk (core.autocrlf=input).
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        # mkstemp creates at 0600 and os.replace carries the mode onto the registry, which is a committed
        # file that every other copy in the repo has at 0644.
        os.chmod(tmp, 0o644)
        os.replace(tmp, str(REGISTRY))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _by_use_case(data: Dict, use_case: str) -> Optional[Dict]:
    for claim in data["claims"]:
        if claim.get("use_case") == use_case:
            return claim
    return None


def _machine_ports(data: Dict) -> Dict[int, Dict]:
    """Port -> claim, for the one scope where two claims on a number is a defect."""
    return {c["port"]: c for c in data["claims"] if c.get("scope") == "machine" and isinstance(c.get("port"), int)}


# ── allocate ──────────────────────────────────────────────────────────────────


def _pick_port(data: Dict) -> Tuple[Optional[int], List[str]]:
    """The lowest pool port that is neither claimed nor live, plus what was stepped over and why.

    The live check is what the record cannot supply: a port the OS or an unregistered program holds
    answers "unclaimed" here and `EADDRINUSE` to whoever is handed it.
    """
    claimed = _machine_ports(data)
    skipped = []
    for port in range(POOL_LOW, POOL_HIGH + 1):
        if port in claimed:
            continue
        reason = needs_pinning(port)
        if reason:
            skipped.append(f"{port} is {reason}")
            continue
        answer = port_probe.verdict(port)
        if not answer.free:
            skipped.append(f"{answer.summary}, and no claim records it")
            continue
        return port, skipped
    return None, skipped


def allocate(args: argparse.Namespace) -> int:
    with file_lock.locked(LOCK):
        data = read_registry()
        existing = _by_use_case(data, args.use_case)
        if existing is not None:
            if args.port is not None and args.port != existing["port"]:
                _note(f"use case '{args.use_case}' already holds port {existing['port']}, so {args.port} was not "
                      f"assigned. Release it first if the number really has to change.")
                return 1
            # Refusing beats applying: this branch runs on every server launch through dev-port.mjs, so a
            # writer here would rewrite the registry at each start. `notes` is deliberately not among the
            # flags checked — dev-port.mjs sends a generic one every time, so a hand-written note differs
            # from it by design, and `amend` is where a note is corrected.
            differs = [field for field, value in (("pinned", args.pinned), ("front_for", args.front_for))
                       if value is not None and value != existing.get(field)]
            if differs:
                flags = ", ".join(f"--{field.replace('_', '-')}" for field in differs)
                _note(f"use case '{args.use_case}' already holds port {existing['port']}, and allocate never "
                      f"changes a claim it found, so {flags} had no effect. `amend --use-case "
                      f"{args.use_case}` is what changes what a recorded claim says.")
                return 1
            print(existing["port"])
            return 0

        if not SLUG.match(args.use_case):
            _note(f"'{args.use_case}' is not a use-case slug (lowercase words joined by single hyphens).")
            return 1
        if args.scope == "machine" and args.port is None and args.pinned:
            _note("--pinned says a number cannot be changed, so it needs the --port it is pinned to.")
            return 1

        if args.port is not None:
            port = args.port
            held = _machine_ports(data).get(port) if args.scope == "machine" else None
            if held is not None:
                _note(f"port {port} is already '{held['use_case']}' ({held['owner']}), so it was not assigned to "
                      f"'{args.use_case}'.")
                return 1
            reason = needs_pinning(port)
            if reason and not args.pinned:
                _note(f"port {port} is {reason}. Pass --pinned '<why this number and no other>' to record it anyway.")
                return 1
        else:
            if args.scope != "machine":
                _note(f"a {args.scope}-scope claim names a port on something this machine does not allocate, so "
                      f"--port is required.")
                return 1
            port, skipped = _pick_port(data)
            for line in skipped:
                _note(f"stepped over {line}")
            if port is None:
                _note(f"every port in {POOL_LOW}-{POOL_HIGH} is claimed or held, so nothing was assigned. Widen the "
                      f"pool in ports.py or release a use case that is finished with.")
                return 1

        claim = {"port": port, "use_case": args.use_case, "owner": args.owner, "scope": args.scope,
                 "status": "assigned", "notes": args.notes}
        if args.pinned:
            claim["pinned"] = args.pinned
        if args.front_for is not None:
            claim["front_for"] = args.front_for
        data["claims"].append(claim)
        write_registry(data)

    _note(f"recorded port {port} for '{args.use_case}' in {REGISTRY}. That file is committed — the dotfiles repo "
          f"now has an uncommitted change.")
    print(port)
    return 0


def amend(args: argparse.Namespace) -> int:
    """Change what an existing claim says, leaving the number it holds alone.

    Its own command rather than a flag on `allocate`, which is called on every launch and so has to stay a
    read; and rather than release-then-allocate, which is two lock acquisitions with the number unclaimed
    in between, where `_pick_port` can hand it to the next caller.
    """
    if args.notes is None and args.pinned is None and args.front_for is None:
        _note("amend changes what a claim says, so it needs at least one of --notes, --pinned, --front-for.")
        return 1
    with file_lock.locked(LOCK):
        data = read_registry()
        claim = _by_use_case(data, args.use_case)
        if claim is None:
            _note(f"no use case '{args.use_case}' is recorded, so nothing was amended. `list` shows the keys this "
                  f"registry holds, and `allocate` is what records a new one.")
            return 1
        changed = []
        for field, value in (("notes", args.notes), ("pinned", args.pinned), ("front_for", args.front_for)):
            if value is None or claim.get(field) == value:
                continue
            was = f"{claim[field]!r} -> " if field in claim else ""
            changed.append(f"{field}: {was}{value!r}")
            claim[field] = value
        problems = check_registry(data)
        if problems:
            _note("the registry would not pass its own checker with that change, so nothing was written:")
            for line in problems:
                _note(f"  {line}")
            return 1
        if changed:
            write_registry(data)

    if changed:
        for line in changed:
            _note(f"amended '{args.use_case}' — {line}")
        _note(f"{REGISTRY} is committed, so the dotfiles repo now has an uncommitted change.")
    else:
        _note(f"'{args.use_case}' already says exactly that, so nothing was written.")
    print(claim["port"])
    return 0


def release(args: argparse.Namespace) -> int:
    with file_lock.locked(LOCK):
        data = read_registry()
        claim = _by_use_case(data, args.use_case)
        if claim is None:
            _note(f"no use case '{args.use_case}' is recorded, so nothing was released.")
            return 1
        if claim.get("status") == "reserved":
            _note(f"'{args.use_case}' is reserved ({claim['owner']}), which is a record of what this machine does "
                  f"not control. Releasing it would hand port {claim['port']} to something else.")
            return 1
        data["claims"].remove(claim)
        write_registry(data)
    print(f"released port {claim['port']} from '{args.use_case}'")
    return 0


def get(args: argparse.Namespace) -> int:
    claim = _by_use_case(read_registry(), args.use_case)
    if claim is None:
        _note(f"no use case '{args.use_case}' is recorded.")
        return 1
    print(claim["port"])
    return 0


def show_list(args: argparse.Namespace) -> int:
    data = read_registry()
    rows = [c for c in data["claims"]
            if (args.scope is None or c.get("scope") == args.scope)
            and (args.status is None or c.get("status") == args.status)]
    if not rows:
        print(f"no claims match (scope={args.scope or 'any'}, status={args.status or 'any'})")
        return 0
    width = max(len(str(c["port"])) for c in rows)
    for claim in sorted(rows, key=lambda c: (c["port"], c["use_case"])):
        marks = []
        if claim.get("front_for") is not None:
            marks.append(f"fronts {claim['front_for']}")
        if claim.get("pinned"):
            marks.append("pinned")
        if claim.get("machines"):
            marks.append("/".join(claim["machines"]))
        suffix = f"  [{', '.join(marks)}]" if marks else ""
        print(f"{str(claim['port']).rjust(width)}  {claim['scope']:<9} {claim['status']:<8} "
              f"{claim['use_case']}  ({claim['owner']}){suffix}")
    print(f"{len(rows)} claim(s)")
    return 0


# ── check ─────────────────────────────────────────────────────────────────────


def check_registry(data: Dict) -> List[str]:
    """Everything wrong with the registry as a document: -> problems."""
    problems = []
    seen_use_cases = set()
    seen_machine: Dict[int, str] = {}
    for index, claim in enumerate(data["claims"]):
        where = f"claim #{index}"
        if not isinstance(claim, dict):
            problems.append(f"{where} is not an object")
            continue
        where = f"claim '{claim.get('use_case', index)}'"
        for field in REQUIRED:
            if field not in claim:
                problems.append(f"{where} has no '{field}'")
        unknown = set(claim) - set(REQUIRED) - set(OPTIONAL)
        if unknown:
            problems.append(f"{where} carries unknown field(s) {', '.join(sorted(unknown))}")
        use_case = claim.get("use_case")
        if not isinstance(use_case, str) or not SLUG.match(use_case):
            problems.append(f"{where}: '{use_case}' is not a use-case slug (lowercase words joined by hyphens)")
        elif use_case in seen_use_cases:
            problems.append(f"use case '{use_case}' appears twice; a use case is the registry's key")
        else:
            seen_use_cases.add(use_case)
        if claim.get("scope") not in SCOPES:
            problems.append(f"{where}: scope '{claim.get('scope')}' is not one of {', '.join(SCOPES)}")
        if claim.get("status") not in STATUSES:
            problems.append(f"{where}: status '{claim.get('status')}' is not one of {', '.join(STATUSES)}")
        if not str(claim.get("notes") or "").strip():
            problems.append(f"{where}: notes is empty, so the record does not say why this number")
        for machine in claim.get("machines") or []:
            if machine not in MACHINES:
                problems.append(f"{where}: machine '{machine}' is not one of {', '.join(MACHINES)}")

        port = claim.get("port")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            problems.append(f"{where}: '{port}' is not a port number")
            continue
        reason = needs_pinning(port)
        if reason and not claim.get("pinned"):
            problems.append(f"{where}: port {port} is {reason}, so it needs a 'pinned' field saying why this "
                            f"number and no other")
        if claim.get("scope") == "machine":
            if port in seen_machine:
                problems.append(f"port {port} is claimed by both '{seen_machine[port]}' and '{use_case}'. Two use "
                                f"cases cannot share a machine port — a `tailscale serve` front included, since "
                                f"the mapping holds the wildcard address.")
            else:
                seen_machine[port] = str(use_case)

    for claim in data["claims"]:
        front_for = claim.get("front_for") if isinstance(claim, dict) else None
        if front_for is None:
            continue
        if front_for not in seen_machine:
            problems.append(f"claim '{claim.get('use_case')}' fronts port {front_for}, which no machine claim "
                            f"records. A front port with no origin outlives the server it was for.")
    return problems


def check_live(data: Dict) -> List[str]:
    """What this machine takes that the registry does not record: -> notices, never violations.

    One direction only. A claimed port with nothing behind it is the normal state of every project that
    is not running at this moment, so reporting those is a wall of lines whose content is always the
    same — and a reader who skips the wall skips the findings in it. The other direction is actionable:
    a listener or a serve mapping nothing claims is a number the allocator believes is free.

    A machine-specific holder is still worth a line, since the registry is shared between a macOS and a
    Windows box and `machines` is how a claim says which one it applies to.
    """
    from tailnet_publish import serve_ports  # inline to avoid circular import

    notices = []
    claimed = _machine_ports(data)
    unclaimed: Dict[int, port_probe.Holder] = {}
    ephemeral = 0
    for holder in port_probe.listeners():
        port = port_probe.port_of(holder)
        if port in claimed:
            continue
        if EPHEMERAL_LOW <= port <= EPHEMERAL_HIGH:
            ephemeral += 1
            continue
        unclaimed.setdefault(port, holder)
    for port, holder in sorted(unclaimed.items()):
        notices.append(f"port {port} is held by {holder.command or 'pid'} {holder.pid} on {holder.address} and no "
                       f"claim records it")
    if ephemeral:
        notices.append(f"{ephemeral} listener(s) sit in the ephemeral range ({EPHEMERAL_LOW}-{EPHEMERAL_HIGH}), "
                       f"which the allocator never hands out, so none of them is recorded or needs to be")
    for port, target in sorted(serve_ports().items()):
        if port not in claimed:
            notices.append(f"port {port} is fronted on the tailnet to {target or 'something this cannot read'} with "
                           f"no claim recording it. A serve mapping holds the wildcard address too, so a local "
                           f"server handed this number will fail to bind with nothing in any process listing.")
    return notices


def _deploy_env_value(repo: Path, key: str) -> Optional[str]:
    """One `KEY=value` from a repo's `config/deploy.env`, trailing comment and quotes removed.

    The deploy script's own reader takes everything after the first `=`, so `DEV_PORT=3939  # pinned`
    would make the port the string `3939  # pinned`. Read the same file the same way and the check
    would pass on a value no `lsof` could use.
    """
    try:
        with (repo / "config" / "deploy.env").open(encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith(f"{key}="):
                    continue
                return line.split("=", 1)[1].split("#", 1)[0].strip().strip("\"'")
    except OSError:
        return None
    return None


def _deploy_env_literals(repo: Path) -> List[Tuple[str, int]]:
    """Every port a repo's `config/deploy.env` still pins: -> [(key, port)].

    That file is per-machine and gitignored, so it is the one place a migration cannot be checked
    into and the one place a stale override survives unnoticed. Two keys can carry a port: `DEV_PORT`,
    which the deploy script no longer reads at all, and `DEV_CMD`, where a `-p 3939` left in the
    command overrides the `PORT` the script exports — the duplicate one line lower, which dropping
    `DEV_PORT` alone leaves in place. Found by the what-is-next session on 2026-10-05, removing both.
    """
    found = []
    for key in ("DEV_PORT", "DEV_CMD"):
        raw = _deploy_env_value(repo, key)
        if raw is None:
            continue
        for pattern in LITERAL_PATTERNS:
            match = pattern.search(raw if key == "DEV_CMD" else f"PORT={raw}")
            if match:
                found.append((key, int(match.group(1))))
                break
    return found


# The files that decide where a server actually listens. Scanning wider than this is what makes the
# check unreadable: a README telling a human to open `localhost:3940`, an `.env.example` default, a test
# asserting a URL and a compose healthcheck on a container-internal port are all literals that cannot be
# resolved at launch and all correct to leave. Measured across the fleet 2026-10-05: ten launch-path
# literals in total against 134 in prose, examples and tests.
LAUNCH_GLOBS = (
    "package.json", "*/package.json",
    "scripts/*", "*/scripts/*",
    "docker-compose*.yml", "*/docker-compose*.yml", "*/*/docker-compose*.yml",
    "vite.config.*", "*/vite.config.*",
    "src-tauri/src/config.rs",
    "build.gradle.kts",
)

# What a port literal looks like in one of those files. Each pattern is a way of telling a process which
# port to listen on, never a way of telling a reader where to point a browser.
LITERAL_PATTERNS = (
    re.compile(r"(?:^|\s)(?:-p|--port)[ =]+(\d{2,5})\b"),
    re.compile(r"^\s*(?:export\s+)?PORT=(\d{2,5})\b"),
    re.compile(r"\b\w*_?port\"?:\s*(\d{2,5})\b"),
    re.compile(r"\"127\.0\.0\.1:(\d{2,5}):\d{2,5}\""),
    re.compile(r"-D[\w.-]*port=(\d{2,5})\b"),
)


def _launch_path_files(repo: Path) -> List[Path]:
    """Every launch-determining file this repo would commit, or raise when git will not say.

    Ignored files are excluded, not untracked ones: a `package.json` inside a gitignored `node_modules/`
    or a scratch `tmp/` is nobody's declaration, and two repos in this fleet have their only manifest
    inside a virtualenv. A file merely untracked is a different thing — it is on its way into the commit
    this check gates, and the index at that moment does not hold it. `/commit` unstages everything at
    skill load before running the gate, so a resolver added by a migration is invisible to `--cached`
    alone: the rule then reported a port nothing resolves and told the reader to copy in a file already
    sitting in `scripts/`, which is what every v15 adoption hit.
    """
    result = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others",
                             "--exclude-standard", "--", *LAUNCH_GLOBS],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files in {repo} exited {result.returncode}: {result.stderr.strip()}")
    return [repo / name for name in result.stdout.split("\0") if name]


def _launch_path_texts(repo: Path) -> List[Tuple[Path, str]]:
    """Every launch-determining file this repo would commit, with its text.

    Raises on one that will not read as text. A scanner that skips what it cannot classify is a scanner
    whose verification is scoped to its own blind spots.
    """
    texts = []
    for path in _launch_path_files(repo):
        try:
            texts.append((path, path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            continue  # in the index but not checked out — a sparse checkout, nothing to read
        except (OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"{path} is a launch-path file here and will not read as text ({exc}), so "
                               f"whether it hardcodes a port could not be established")
    return texts


def launch_path_literals(repo: Path) -> List[Tuple[Path, int, int, str]]:
    """Every port literal in a launch-determining file: -> [(file, line number, port, the line)]."""
    found = []
    for path, text in _launch_path_texts(repo):
        for number, line in enumerate(text.splitlines(), 1):
            for pattern in LITERAL_PATTERNS:
                match = pattern.search(line)
                if match:
                    found.append((path, number, int(match.group(1)), line.strip()))
                    break
    return found


# What a launch-determining file mentions when the repo resolves a port at launch: the shared resolver the
# per-repo `scripts/dev.mjs` shim imports, or the allocator called directly by a script of its own.
RESOLVER_MARKERS = ("dev-port.mjs", "ports.py")

# The allocator's own directory, whose files hold every marker above as implementation.
ALLOCATOR_DIR = "claude/skills/ports/"


def _owned_by(claim: Dict, name: str) -> bool:
    """Is `claim` this repo's? A claim several repos share spells its owners comma-separated.

    Whole tokens, never a substring: `name in str(claim["owner"])` let the repo named `travel` own
    `travel-map`'s pinned claim, and a pinned claim is what exempts a port literal from the
    `ports-from-registry` rule — so one repo's pin silenced the finding in another. Measured against
    this registry on 2026-10-06.
    """
    return name in {part.strip() for part in str(claim.get("owner", "")).split(",")}


def _resolves_at_launch(repo: Path) -> bool:
    """Does a launch-determining file in `repo` ask the registry for a port?

    Read from the repo rather than assumed from the version record: a repo can record v15 and then
    lose the shim to a revert or a bad merge, and the record would still say it adopted.

    Scoped to the same files the literal scan reads, because only those decide where a server listens.
    A marker counted anywhere in the tree is also counted in the sentence a CLAUDE.md or README writes
    when it documents this skill — so the finding goes quiet on the repos that have started paying
    attention, and a doc line reads as a resolver that no process runs.

    The allocator's own directory is excluded, so the dotfiles repo — which contains every one of these
    markers by definition — is answered on the same evidence as anywhere else rather than passing for
    holding the implementation.
    """
    for path, text in _launch_path_texts(repo):
        if path.relative_to(repo).as_posix().startswith(ALLOCATOR_DIR):
            continue
        if any(marker in text for marker in RESOLVER_MARKERS):
            return True
    return False


def _worktree_root(repo: Path) -> Path:
    """The checkout `repo` sits in, so a path inside a project is read as that project.

    Handed a subdirectory, the scan would otherwise look for a resolver only under it and report the
    repo's port as one nothing asks for — `tripit/web` did exactly that, because `scripts/dev.mjs` is at
    the root. A linked worktree resolves to its OWN root rather than the main one, which is deliberate:
    the content under review is the one in that worktree, while the repo's *name* comes from the main
    worktree instead (see `_repo_name`). The two questions take different roots.
    """
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    top = result.stdout.strip() if result.returncode == 0 else ""
    return Path(top) if top else repo


def _repo_name(repo: Path) -> str:
    """This repo's name as a claim's `owner` spells it: the MAIN worktree's directory name.

    Not `repo.name`, which is whichever directory the caller pointed at. A linked worktree — which a
    forked sub-skill creates for every run — and a `--repo <subdirectory>` both have a basename no owner
    matches, and the consequences run both ways at one count and one exit status: every pinned literal
    is reported as pinned to some other repo, while the genuine finding about a port nothing resolves
    disappears, because the claim no longer reads as this repo's.

    `git worktree list --porcelain` names the main worktree on its first line from any position inside
    the repo, a bare one included. Two shapes it still gets wrong, measured 2026-10-06: a clone sitting
    in a directory named differently from its owner, and a repo created with `--separate-git-dir`. Both
    fall through to the directory name, which is as close as anything here can get — the registry also
    records an owner for a project that is not a git repo at all, so no git-derived identity covers
    every claim.
    """
    result = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    first = result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else ""
    return Path(first[len("worktree "):].strip()).name if first.startswith("worktree ") else repo.name


def check_repo(data: Dict, repo: Path) -> Tuple[List[str], List[str]]:
    """Does this repo get every port it owns from the registry: -> (problems, notices).

    Two halves, and the second is why the first is worth anything. A literal in a launch-determining
    file is a second copy of a number the registry owns, and the copy is what the process reads — so
    each one has to be a `pinned` claim this repo owns, recording that an outside party, a compiled-in
    default or a vendor fixed it.

    The other half is a port the registry hands this repo that nothing here asks for. An absent literal
    on its own proves nothing: a repo with no `-p` flag and no resolver is not resolving the port, it is
    taking its framework's default and drifting upward on a collision. Measured 2026-10-05, printlab and
    what-is-next both reported zero literals in exactly that state. So an unpinned claim this repo owns
    requires either a literal already reported above or a file here that asks for the number.

    A claim carrying `front_for` is exempt: a tailnet front port is allocated by `deploy-dev-server.sh`
    at the moment it publishes, and the repo it belongs to never names it.
    """
    repo = _worktree_root(repo.resolve())
    name = _repo_name(repo)
    claims = _machine_ports(data)
    problems, notices = [], []
    literal_ports = set()

    for path, number, port, line in launch_path_literals(repo):
        literal_ports.add(port)
        claim = claims.get(port)
        relative = path.relative_to(repo).as_posix()
        if claim is not None and claim.get("pinned") and _owned_by(claim, name):
            continue
        if claim is None:
            problems.append(f"{relative}:{number} hardcodes port {port}, which no claim records: {line}. Either "
                            f"resolve it at launch (`node scripts/dev.mjs <command>`) or record why it cannot move "
                            f"— `ports.py allocate --use-case {name}-<what-listens> --owner {name} --port {port} "
                            f"--pinned '<why this number and no other>' --notes '<what listens>'`.")
        elif not claim.get("pinned"):
            problems.append(f"{relative}:{number} hardcodes port {port}, which the registry assigns to "
                            f"'{claim['use_case']}' without pinning it: {line}. An unpinned number is the "
                            f"registry's to hand out at launch, so this copy is the one that would go stale.")
        else:
            problems.append(f"{relative}:{number} hardcodes port {port}, which is pinned to "
                            f"'{claim['use_case']}' ({claim['owner']}) rather than to this repo: {line}.")

    owned = sorted((c for c in claims.values()
                    if _owned_by(c, name) and not c.get("pinned") and c.get("front_for") is None
                    and c["port"] not in literal_ports and c.get("status") == "assigned"),
                   key=lambda c: c["port"])
    if owned and not _resolves_at_launch(repo):
        ports = ", ".join(f"{c['port']} ('{c['use_case']}')" for c in owned)
        problems.append(f"the registry assigns this repo port {ports} and no launch-determining file here asks for "
                        f"it, so "
                        f"nothing resolves it: the server takes its framework's default instead and drifts upward "
                        f"on a collision. Copy `dev.mjs` from conventions/versions/015-ports-from-registry/ into "
                        f"scripts/, point the dev script at it, and drop any port literal — or record the number "
                        f"`--pinned` if it genuinely cannot be resolved at launch.")

    # A notice rather than a problem: the file is gitignored and per-machine, so no commit here can fix
    # it and the rule must not fail a repo for one machine's leftovers. Its absence says nothing either
    # way, which is why only a present key is worth a word.
    for key, port in _deploy_env_literals(repo):
        dead = ("The deploy script reads the registry now, so that line is a dead copy"
                if key == "DEV_PORT" else
                "A `-p` in DEV_CMD overrides the PORT the deploy script exports, so this is the copy that wins")
        notices.append(f"{repo}/config/deploy.env still pins port {port} in {key}. {dead}; removing it keeps the "
                       f"number in one place. That file is per-machine, so the other machine's copy needs the "
                       f"same edit.")
    return problems, notices


def check(args: argparse.Namespace) -> int:
    try:
        data = read_registry()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ports: the registry could not be read — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    problems = check_registry(data)
    notices: List[str] = []
    if args.repo:
        found, said = check_repo(data, Path(args.repo))
        problems += found
        notices += said
    if args.live:
        notices += check_live(data)

    # The summary leads and every finding follows it, problems and notices alike. Printing notices first
    # put two kinds of per-repo output on either side of the summary line, so the one above it read as
    # belonging to a previous command — reported by the what-is-next session on 2026-10-05.
    def report() -> None:
        for problem in problems:
            print(f"  {problem}\n")
        for notice in notices:
            print(f"  {notice}\n")

    if problems:
        print(f"ports: {len(problems)} problem(s) across {len(data['claims'])} claim(s)\n")
        report()
        return 1
    # Never a bare "clean" while a notice is standing: a live listener nothing claims is a gap in the
    # record whatever the document says, and a per-machine override is one no commit here can close.
    if notices:
        print(f"ports: no problems in the registry, with {len(notices)} line(s) below reporting what it does not "
              f"cover ({len(data['claims'])} claim(s) checked)\n")
        report()
        return 0
    print(f"ports: clean ({len(data['claims'])} claim(s) checked)")
    return 0


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Allocate and record this machine's TCP ports.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("allocate", help="record a port for a use case, assigning one if it has none")
    p.add_argument("--use-case", required=True, help="the registry's key: lowercase words joined by hyphens")
    p.add_argument("--owner", required=True, help="the repo or app the use case belongs to")
    p.add_argument("--notes", required=True,
                   help="why this number, for whoever reads the record later; recorded when the claim is "
                        "created, and changed afterwards by `amend`")
    p.add_argument("--scope", default="machine", choices=SCOPES)
    p.add_argument("--port", type=int, help="a specific number, for a port fixed outside this machine")
    p.add_argument("--pinned", help="why the number cannot be changed (an OAuth redirect, a URL restriction)")
    p.add_argument("--front-for", type=int, help="the origin port this one proxies to via `tailscale serve`")

    p = sub.add_parser("amend", help="change what a recorded claim says, leaving the port it holds alone")
    p.add_argument("--use-case", dest="use_case", required=True, help="the registry's key")
    p.add_argument("--notes", help="replace the note")
    p.add_argument("--pinned", help="replace the reason the number cannot be changed")
    p.add_argument("--front-for", type=int, help="replace the origin port this one proxies to")

    # `--use-case` on every command that takes one, matching `allocate`. A positional here and on
    # `release` made them disagree with `allocate` on how the registry's own key is named, which costs a
    # round trip to discover — reported by the what-is-next session on 2026-10-05.
    p = sub.add_parser("get", help="the port recorded for a use case")
    p.add_argument("--use-case", dest="use_case", required=True, help="the registry's key")

    p = sub.add_parser("list", help="the claims, newest-port last")
    p.add_argument("--scope", choices=SCOPES)
    p.add_argument("--status", choices=STATUSES)

    p = sub.add_parser("release", help="drop an assigned use case's claim")
    p.add_argument("--use-case", dest="use_case", required=True, help="the registry's key")

    p = sub.add_parser("check", help="the registry as a document, and optionally against this machine")
    p.add_argument("--live", action="store_true", help="also report what listens here that no claim records")
    p.add_argument("--repo", help="also check whether one repo gets every port it owns from the registry")

    args = parser.parse_args(argv)
    if args.cmd == "check":
        return check(args)
    try:
        read_registry()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _note(f"the registry at {REGISTRY} could not be read — {type(exc).__name__}: {exc}")
        return 1
    return {"allocate": allocate, "amend": amend, "get": get, "list": show_list,
            "release": release}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
