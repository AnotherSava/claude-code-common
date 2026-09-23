"""Every hostname a Worker claims carries the project's name, and so does the Worker.

A DNS zone several projects take hostnames in is a shared namespace exactly like a docker bridge or
a flat `conf.d`, and owning the zone is what makes that easy to miss. A Workers custom domain binds
a hostname to exactly one Worker, so the first project to claim `notify.example.com` takes it from
all of them — and the Worker *script* name is the same claim one layer up, account-wide, where a
`wrangler deploy` of a second `notify` overwrites the first project's deployed script outright.

Nothing scarce is being conserved by sharing: a zone allows 100 custom domains and 1,000 routes,
identical on free and paid (learnings/cloudflare-workers-push-to-a-pulling-app.md).

Two assertions, and only the second is free of a word list.

**The script name sits outside the generic set**, read from the same place the compose rule reads it
so the two cannot disagree, plus the function words this fleet's own Workers use. This half inherits
the weakness of every denylist: a function word nobody has written down yet passes. That is stated
rather than papered over — the list is short because it is measured, and widening it on a guess
would make the rule look stronger than it is.

**A route's leftmost label opens with the script name.** This one needs no list. It forces the
hostname to inherit whatever the script name is, so there is exactly one name per Worker to get
right and the first assertion is the whole of the judgement. `starts with` rather than `equals`,
because one Worker may legitimately carry several custom domains.

A pattern claiming the apex or a wildcard is reported on its own terms. It is not a name that could
be prefixed — it is the whole zone, which in a zone shared with other projects is the collision this
rule exists to prevent rather than an instance of it.

This detects and never edits. A hostname is written into the Worker's config, the app that dials it,
whatever holds the secret it authenticates with, and the DNS record Cloudflare created for it; a
rename that misses one of those fails at a TLS handshake or a refused subscribe, far from the edit.
"""

from __future__ import annotations

import importlib.util
import os
import re
from typing import NamedTuple

# <repo>/claude/conventions/rules -> <repo>/claude/scripts/ingress-lint.py
INGRESS_LINT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.realpath(__file__)))), "scripts", "ingress-lint.py")

# Function words the fleet's own Workers are named for, which the compose denylist has no reason to
# carry. Measured rather than imagined: `trips-mail` and `trips-notify` are the two Workers deployed
# when this rule was written, and `notify` is the name CLAUDE.md's own example collides on. A
# function word outside this set is not caught — see the module docstring.
EXTRA_GENERIC = frozenset({"mail", "notify"})

TOML_RE = re.compile(r"^wrangler(?:\..+)?\.toml$", re.I)
JSON_RE = re.compile(r"^wrangler(?:\..+)?\.jsonc?$", re.I)
SKIP_DIRS = frozenset({".git", "node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"})
TABLE_RE = re.compile(r"^\[\[?([A-Za-z0-9_.\-]+)\]\]?$")
KEY_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*=\s*(.*)$")
STRING_RE = re.compile(r"^(['\"])(.*)\1$")


class Route(NamedTuple):
    pattern: str
    line_no: int


class Worker(NamedTuple):
    path: str                # repo-relative, forward slashes, so it reads the same on both machines
    name: str                # the top-level `name`, "" when the file declares none
    name_line: int
    routes: list[Route]


class Finding(NamedTuple):
    kind: str                # "script" or "route" — they are renamed in different places
    path: str
    line_no: int
    subject: str
    reason: str
    instruction: str


def generic_names() -> frozenset[str]:
    """The denylist, read from the ingress lint — never a second copy of it.

    Imported rather than duplicated for the same reason `cotenant-service-names` imports it: that
    file is the commit gate for the neighbouring half of this convention, and a rule that quietly
    fell back to its own copy would keep passing names the gate refuses.
    """
    try:
        spec = importlib.util.spec_from_file_location("ingress_lint", INGRESS_LINT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return frozenset(module.GENERIC) | EXTRA_GENERIC
    except BaseException as exc:
        raise RuntimeError(f"the generic-name list could not be read from claude/scripts/ingress-lint.py "
                           f"({type(exc).__name__}: {exc}), and this rule will not fall back to a second copy "
                           f"of it — the commit gate and this check must not disagree about what generic "
                           f"means") from exc


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def strip_comment(text: str) -> str:
    """Drop a trailing `# …`, leaving a `#` inside quotes alone.

    A quote-aware walk rather than a `split("#")`: a route pattern carries no `#`, but a neighbouring
    value in the same file can, and cutting one mid-value turns a readable key line into a line this
    reader would refuse.
    """
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return text[:index].rstrip()
    return text.rstrip()


def literal(value: str) -> str | None:
    """The contents of a single-line quoted string, or None where this reader cannot read one."""
    match = STRING_RE.match(value.strip())
    return match.group(2) if match else None


def parse_wrangler(text: str, path: str) -> tuple[Worker, list[str]]:
    """Read one wrangler.toml's script name and the hostnames it claims. -> (worker, refusals)

    A line scan and not a TOML parser: this runs under a plain interpreter with no dependency file
    behind it, and `tomllib` arrived in 3.11 while the fleet's baseline is 3.9.

    What makes the scan safe is that it refuses narrowly and for a named reason. Unlike the compose
    reader it does not classify every line — a wrangler file carries many keys none of which can
    hide a claim — but any line that *is* a claim and cannot be read literally comes back as a
    refusal the caller raises on. The inline form `routes = [{ pattern = "…" }]` is the one that
    matters: it is valid wrangler, it is invisible to a reader looking only for `[[routes]]`, and
    read wrongly it would report a repo clean that claims a generic hostname.
    """
    name, name_line, routes, refusals = "", 0, [], []
    table = None

    def refuse(number: int, line: str, why: str) -> None:
        refusals.append(f"{path}:{number}: {line.strip()} — {why}")

    for number, raw in enumerate(text.splitlines(), 1):
        body = strip_comment(raw.strip())
        if not body:
            continue
        table_match = TABLE_RE.match(body)
        if table_match:
            table = table_match.group(1)
            continue
        if body.startswith("["):
            refuse(number, raw, "a table header this reader cannot parse, and the table it opens may hold a route")
            continue
        match = KEY_RE.match(body)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if table is None and key == "name":
            text_value = literal(value)
            if text_value is None:
                refuse(number, raw, "a script name this reader cannot read literally; it is the account-wide claim")
                continue
            name, name_line = text_value, number
        elif table == "routes" and key == "pattern":
            text_value = literal(value)
            if text_value is None:
                refuse(number, raw, "a route pattern this reader cannot read literally")
                continue
            routes.append(Route(text_value, number))
        elif table is None and key in ("route", "routes"):
            # The top-level forms. `route = "…"` is one string; `routes = [ … ]` is an array whose
            # items are bare strings or inline tables, and only a single-line one can be read here.
            if key == "route":
                text_value = literal(value)
                if text_value is None:
                    refuse(number, raw, "a route this reader cannot read literally")
                    continue
                routes.append(Route(text_value, number))
                continue
            stripped = value.strip()
            if not stripped.startswith("[") or not stripped.endswith("]"):
                refuse(number, raw, "a routes array that opens or continues on another line; this reader needs it "
                                    "on one, and an unread array is a hostname claimed with nothing looking at it")
                continue
            found = re.findall(r"pattern\s*=\s*(['\"])(.*?)\1", stripped) or \
                re.findall(r"(['\"])([^'\"]+)\1", stripped)
            if not found:
                refuse(number, raw, "a routes array with no pattern this reader can extract")
                continue
            routes.extend(Route(item[1], number) for item in found)
    return Worker(path, name, name_line, routes), refusals


def find_files(root: str) -> tuple[list[str], list[str]]:
    """Every wrangler TOML and every wrangler JSON/JSONC in the repo, absolute, sorted.

    The JSON forms are collected in order to be refused rather than skipped. They are valid wrangler
    config that this reader does not read, and a repo that moved to one would otherwise come back
    clean for the same reason an empty repo does.
    """
    tomls, jsons = [], []
    # walk-unfiltered, for the reason the compose rule's walk is: a wrangler file kept out of git
    # because it carries an account id is still the file that deploys, so the hostname it claims is
    # live in the zone.
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(files):
            if TOML_RE.match(name):
                tomls.append(os.path.join(base, name))
            elif JSON_RE.match(name):
                jsons.append(os.path.join(base, name))
    return tomls, jsons


def host_label(pattern: str) -> str | None:
    """The leftmost DNS label of a route pattern, or None where the pattern claims no single name.

    A pattern is a hostname with an optional path, and may be a wildcard. `None` is returned for
    every shape that is not one name to be judged — a bare wildcard, an apex — and the caller
    reports those on their own terms rather than prefixing something that has no label to prefix.
    """
    host = pattern.split("/", 1)[0].strip().rstrip(".")
    if not host or host.startswith("*"):
        return None
    labels = host.split(".")
    if len(labels) < 3:
        return None  # an apex like example.com: a claim on the zone itself, not a name inside it
    return labels[0]


def findings_for(worker: Worker, generic: frozenset[str]) -> list[Finding]:
    """Every name in one wrangler file that sits in a namespace another project writes to."""
    findings = []
    if worker.name.casefold() in generic:
        findings.append(Finding(
            "script", worker.path, worker.name_line, worker.name,
            f"{worker.name!r} is a generic name, and a Worker script name is account-wide — a deploy of a "
            f"second {worker.name!r} replaces the first project's script rather than sitting beside it",
            f"the script name becomes {{{{project}}}}-{worker.name}, and every route below it follows"))
    for route in worker.routes:
        label = host_label(route.pattern)
        if label is None:
            findings.append(Finding(
                "route", worker.path, route.line_no, route.pattern,
                f"{route.pattern!r} claims the zone itself rather than one name inside it, so every project "
                f"taking a hostname there is downstream of this Worker",
                "claim a single hostname carrying this project's name instead"))
        elif label.casefold() in generic:
            findings.append(Finding(
                "route", worker.path, route.line_no, route.pattern,
                f"{label!r} is a generic label, and a custom domain binds a hostname to exactly one Worker — "
                f"the first project to claim it takes it from all of them",
                f"the hostname opens with the script name: {worker.name}.{'.'.join(route.pattern.split('.')[1:])}"))
        elif worker.name and not label.casefold().startswith(worker.name.casefold()):
            findings.append(Finding(
                "route", worker.path, route.line_no, route.pattern,
                f"{label!r} does not open with the script name {worker.name!r}, so this Worker has two names to "
                f"keep un-generic instead of one",
                f"the hostname opens with the script name: {worker.name}.{'.'.join(route.pattern.split('.')[1:])}"))
    return findings


def check(root: str) -> list[str]:
    """One line per Worker name or hostname in this repo that another tenant could also claim."""
    generic = generic_names()
    tomls, jsons = find_files(root)
    if jsons:
        raise ValueError(f"{', '.join(rel(root, path) for path in jsons)} is wrangler config in a JSON form this "
                         f"rule does not read, so the Worker names and hostnames it claims were never looked at — "
                         f"which is indistinguishable here from a repo that deploys no Worker at all")
    workers, refusals, unreadable = [], [], []
    for path in tomls:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            unreadable.append(rel(root, path))
            continue
        worker, problems = parse_wrangler(text, rel(root, path))
        workers.append(worker)
        refusals.extend(problems)
    if unreadable:
        raise OSError(f"{len(unreadable)} wrangler file(s) could not be opened ({', '.join(unreadable)}), so the "
                      f"names they claim in the zone were never read")
    if refusals:
        # A claim this reader cannot read literally is a name it would have asserted about without
        # looking. Raised rather than reported as a violation: the name may well be right, and what
        # is wrong is that nobody here can say.
        raise ValueError(f"{len(refusals)} wrangler line(s) carry a name or a route this reader could not read "
                         f"literally, so nothing was concluded about them: " + " | ".join(refusals))
    nameless = [worker.path for worker in workers if not worker.name]
    if nameless:
        raise ValueError(f"{', '.join(nameless)} declares no top-level `name`, so the script this file deploys has "
                         f"no name to judge and the hostnames below it have nothing to be checked against")
    return [f"{finding.path}:{finding.line_no}  {finding.subject}: {finding.instruction} — {finding.reason}"
            for worker in workers for finding in findings_for(worker, generic)]
