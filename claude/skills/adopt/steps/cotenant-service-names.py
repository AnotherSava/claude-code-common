#!/usr/bin/env python3
"""v12 — every compose service is named after its project and equals its container.

Compose publishes a *service's* key as a DNS alias on every network the service joins,
so `app`, `db`, `caddy` and friends are claims staked in a namespace the neighbours
also write to. Two projects each calling a service `app` both answer to `app` on the
shared bridge, and the proxy dials whichever the daemon hands back: that is the 41
hours a commercial storefront spent serving a neighbour's application, at HTTP 200,
with every container healthy and the config valid
(learnings/docker-compose-shared-host-co-tenancy.md).

This step **detects and never edits**. A rename reaches `depends_on`, the vhost's
`reverse_proxy` upstream, `BUILD_SERVICES` and `APP_CONTAINER` in an encrypted
`config/publish.env`, and the derived container name a proxy dials — and one missed
reference takes the site down behind an HTTP 200, which is the failure mode this
convention exists to prevent. So `apply` prints the rename and the references it
found and exits 3; a human makes the change, and `verify` is what records it.

    cotenant-service-names.py probe  <repo-root>              0 never · 1 no · 2 ask · 3 error
    cotenant-service-names.py apply  <repo-root> [--dry-run]  3 always, nothing written
    cotenant-service-names.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

Three decisions worth knowing before reading the code.

**The scan is not scoped to services that join an `external:` network**, which is how
`scripts/ingress-lint.py` scopes the same rule. One tenant here is the measured reason:
two of its services declare no `networks:` key at all, and the host's own compose file
joins that tenant's default network to reach them — so the proxy straddles the bridge
those two sit on, and "it is not on the shared network today" is exactly the defence that
does not hold. The real incident had its two claimants of `app` on different bridges
with the proxy across both.

**The generic denylist is imported from that lint rather than copied**, so the gate
that blocks a commit and the check that records a repo cannot disagree about what
generic means. Two names the fleet's own compose files use are added here: `mongo`
and `migrate`.

**The reader refuses rather than skips** (idempotence rule 6). It classifies every
content line as a top-level key, a service key, one of a service's own keys, or a
value belonging to the key above it — and stops on anything else, naming it verbatim.
A YAML merge key is the case that makes this more than fussiness: `<<: *common` can
supply a `container_name` this line scanner cannot see, so a reader that skipped it
would assert a shape it never read.
"""

import importlib.util
import os
import re
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above
import _own_fixtures  # noqa: E402  — path set above, as the Node steps do for their shared module

# Emit UTF-8 whatever the console codepage is: this prints compose lines back verbatim, and a
# non-ASCII byte through Windows' cp1252 default raises rather than prints, turning a finding
# into an exit 3 for a reason that has nothing to do with the repo being checked.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# <repo>/claude/skills/adopt/steps -> <repo>/claude/scripts/ingress-lint.py
INGRESS_LINT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.realpath(__file__))))), "scripts", "ingress-lint.py")
# Names the fleet's compose files use that the lint's list does not carry. `migrate` is a one-shot
# in three repos here and `mongo` is tripit's database, and both are as ownerless on a shared
# bridge as `app` is.
EXTRA_GENERIC = frozenset({"mongo", "migrate"})

COMPOSE_RE = re.compile(r"^(?:docker-)?compose(?:\..+)?\.ya?ml$", re.I)
SKIP_DIRS = frozenset({".git", "node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"})
KEY_RE = re.compile(r"^([A-Za-z0-9_.\-/]+):(?:[ \t]+(.*))?$")
PUBLISH_ENV = "config/publish.env"


class Service(NamedTuple):
    name: str
    container: str | None    # None means the key is absent, which is itself a finding
    line_no: int


class Compose(NamedTuple):
    path: str                # repo-relative, forward slashes, so it reads the same on both machines
    project: str             # the top-level `name:`, "" when the file declares none
    services: list[Service]


class Finding(NamedTuple):
    kind: str                # "service" or "vhost" — they are renamed in different places
    path: str
    line_no: int
    subject: str             # the service key, or the vhost file's basename
    reasons: list[str]       # every rule this one name breaks, so the advice cannot contradict itself
    rename: str              # what it should be called instead


def load_generic() -> tuple[frozenset[str], str]:
    """The denylist, read from `scripts/ingress-lint.py` — or the reason it could not be.

    Imported rather than duplicated: that file is the commit gate for the same rule, and a second
    copy of a list is a copy that drifts. A step that quietly fell back to its own copy would keep
    passing repos the gate refuses, which is worse than saying it cannot judge.
    """
    try:
        spec = importlib.util.spec_from_file_location("ingress_lint", INGRESS_LINT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return frozenset(module.GENERIC) | EXTRA_GENERIC, ""
    except BaseException as exc:
        return frozenset(), (f"the generic-name list could not be read from claude/scripts/ingress-lint.py "
                             f"({type(exc).__name__}: {exc}), and this step will not fall back to a second "
                             f"copy of it — the commit gate and this check must not disagree about what "
                             f"generic means")


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def strip_comment(text: str) -> str:
    """Drop a trailing `# …`, leaving a `#` inside quotes alone.

    A quote-aware walk rather than a `split("#")`: real compose values carry them — an
    `IGNORE_IP` list and a healthcheck command both do — and cutting one mid-value turns a
    readable key line into a line this reader would refuse.
    """
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t"):
            return text[:index].rstrip()
    return text.rstrip()


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_compose(text: str, path: str) -> tuple[Compose, list[str]]:
    """Read one compose file's project name and service keys. -> (compose, refusals)

    A line scan and not a YAML parser, because `conventions.py` reaches these scripts under a
    plain interpreter with no dependency file behind it and PyYAML is not in the standard library.
    What makes the scan safe is that it refuses: every content line is classified as a top-level
    key, a service key, one of a service's immediate keys, or a value belonging to the key above
    it, and anything else stops the step with the line named verbatim.

    Indent is measured rather than assumed to be two spaces. The first line inside `services:`
    fixes the service-key column and the first line inside a service fixes its own key column, so
    a file indented four spaces reads the same and a line landing between the two columns is a
    refusal rather than a guess about which it meant.
    """
    project, services, refusals = "", [], []
    in_services, service_indent, child_indent = False, None, None

    def refuse(number: int, line: str, why: str) -> None:
        refusals.append(f"{path}:{number}: {line.rstrip()}\n    {why}")

    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lead = raw[:len(raw) - len(raw.lstrip())]
        if "\t" in lead:
            refuse(number, raw, "indented with a tab, which YAML does not allow; this reader will not guess a column for it")
            continue
        indent = len(lead)
        body = strip_comment(raw.strip())
        if indent == 0:
            if body in ("---", "..."):
                refuse(number, raw, "a second YAML document in one compose file; which document's services are the project's is not this reader's guess")
                continue
            match = KEY_RE.match(body)
            if not match:
                refuse(number, raw, "a top-level line that is not a `key:` or a `key: value`")
                continue
            key, value = match.group(1), (match.group(2) or "").strip()
            in_services, service_indent, child_indent = False, None, None
            if key == "name":
                project = unquote(value)
            elif key == "services":
                if value:
                    refuse(number, raw, "the services block carries an inline value; this reader walks a block mapping and cannot enumerate a flow one")
                    continue
                in_services = True
            continue
        if not in_services:
            continue
        if service_indent is None:
            service_indent = indent
        if indent < service_indent:
            refuse(number, raw, f"inside the services block but shallower than its first service key at column {service_indent}")
            continue
        if indent == service_indent:
            child_indent = None
            match = KEY_RE.match(body)
            if not match or match.group(2):
                refuse(number, raw, _service_line_reason(body))
                continue
            services.append(Service(match.group(1), None, number))
            continue
        if not services:
            refuse(number, raw, "deeper than the services block's first column before any service key opened")
            continue
        if child_indent is None:
            child_indent = indent
        if indent < child_indent:
            refuse(number, raw, f"between the service key column {service_indent} and its own key column {child_indent}")
            continue
        if indent > child_indent:
            continue  # a value belonging to the key above it — a list item, a flow tail, a block scalar's body
        if body.startswith("<<"):
            refuse(number, raw, "a YAML merge key, which can supply a container_name this line reader cannot see; expanding an anchor needs a real parser")
            continue
        match = KEY_RE.match(body)
        if not match:
            refuse(number, raw, f"at service {services[-1].name!r}'s own key column and not a `key:` or a `key: value`")
            continue
        if match.group(1) == "container_name":
            value = unquote((match.group(2) or "").strip())
            if not value or value.startswith("*"):
                refuse(number, raw, "a container_name whose value is an alias or continues on another line; this reader needs it literally")
                continue
            services[-1] = services[-1]._replace(container=value)
    return Compose(path, project, services), refusals


def _service_line_reason(body: str) -> str:
    """Why a line at the service-key column is not a service key — named, never skipped."""
    if body.startswith("- "):
        return "a list item where a service key belongs; services are a mapping"
    if body.startswith("<<"):
        return "a YAML merge key at the service column, which can name services this line reader cannot see"
    value = (KEY_RE.match(body).group(2) or "").strip() if KEY_RE.match(body) else ""
    if value.startswith("*"):
        return "a service whose whole body is a YAML alias; expanding an anchor needs a real parser, and the anchor can carry a container_name"
    if value.startswith("{"):
        return "a service written as a flow mapping; this reader walks a block mapping"
    if value:
        return "a service key with an inline value; a service is a mapping opened by `key:`"
    return "not a service key"


def find_files(root: str) -> tuple[list[str], list[str]]:
    """Every compose file and every `*.caddy` vhost in the repo, absolute, sorted.

    `Caddyfile` is deliberately not a vhost: it is the base config of a proxy the repo owns, it is
    never copied into somebody else's `conf.d`, and its name is fixed by Caddy — so the basename
    rule below has nothing to say about it.
    """
    composes, vhosts = [], []
    # walk-unfiltered: and it must stay that way. The three Node steps narrow their walk to what git
    # does not hide, because a hidden `package.json` is a scratch clone nobody maintains. The same
    # reasoning inverts here: a `compose.override.yml` or a vhost kept out of git *because it carries
    # host paths* is still the file the box brings up, so its service keys are live on the shared
    # bridge. Narrowing this walk was tried and reverted — it turned probe's question into a silent
    # `verify` pass on exactly the generic-name collision that cost a commercial site 41 hours. The
    # fixture hazard the git filter exists for does not arise here either: `_own_fixtures.prune`
    # below already answers it, by identity rather than by name.
    for base, dirs, files in os.walk(root):
        # This skill's own steps ship compose specimens, one written to be unparseable on purpose, and
        # a check that reports its own test data as findings teaches a reader to skip it. Skipped by
        # resolved path rather than by the name `fixtures`, so a project's real `tests/fixtures/` is
        # still read and a scratch copy of a fixture tree — where the fixture is the repo under test —
        # is read in full.
        dirs[:] = _own_fixtures.prune(base, sorted(d for d in dirs if d not in SKIP_DIRS))
        for name in sorted(files):
            if COMPOSE_RE.match(name):
                composes.append(os.path.join(base, name))
            elif name.endswith(".caddy"):
                vhosts.append(os.path.join(base, name))
    return composes, vhosts


def read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def read_composes(root: str) -> tuple[list[Compose], list[str], list[str]]:
    """(parsed compose files, refusals, files that could not be opened at all)."""
    parsed, refusals, unreadable = [], [], []
    for path in find_files(root)[0]:
        text = read_text(path)
        if text is None:
            unreadable.append(rel(root, path))
            continue
        compose, problems = parse_compose(text, rel(root, path))
        parsed.append(compose)
        refusals.extend(problems)
    return parsed, refusals, unreadable


def suggest(service: Service, project: str, generic: frozenset[str]) -> str:
    """What the service should be called: its container's name where that already reads right.

    Renaming the service to match an existing `container_name` is the learnings file's own fix and
    the smaller edit — `postgres`/`<project>-db` becomes `<project>-db`, and the container keeps the
    name the proxy already dials. A key that already carries the project and is not generic keeps
    its own name, so a service whose only fault is a missing `container_name` is not told to rename
    itself as well. Everything else gets the project pushed onto the front of the key.
    """
    container = service.container or ""
    if container and container.casefold() not in generic and is_prefixed(container, project):
        return container
    if service.name.casefold() not in generic and is_prefixed(service.name, project):
        return service.name
    return f"{project}-{service.name}"


def is_prefixed(name: str, project: str) -> bool:
    """Whether a name belongs to this project: equal to it, or opened by it and a hyphen."""
    return bool(project) and (name == project or name.startswith(f"{project}-"))


def service_findings(composes: list[Compose], generic: frozenset[str]) -> list[Finding]:
    """One finding per offending service, carrying every rule that service breaks.

    One finding rather than one per rule, so the advice cannot contradict itself: a generic name is
    not repaired by pinning `container_name` to that same generic word.
    """
    findings = []
    for compose in composes:
        if not compose.project:
            continue
        for service in compose.services:
            reasons = []
            if service.name.casefold() in generic:
                reasons.append(f"{service.name!r} is a generic name, and compose publishes it as a DNS alias on "
                               f"every network this service joins")
            if not is_prefixed(service.name, compose.project):
                reasons.append(f"{service.name!r} does not carry the project name {compose.project!r}, so nothing "
                               f"about the alias it publishes says whose it is")
            if service.container is None:
                reasons.append(f"no container_name, so the container answers to {service.name!r} and to the derived "
                               f"{compose.project}-{service.name}-1 at once")
            elif service.container != service.name:
                reasons.append(f"container_name is {service.container!r}, so it answers to both that and "
                               f"{service.name!r} — and the service key is the half everyone forgets")
            if reasons:
                findings.append(Finding("service", compose.path, service.line_no, service.name, reasons,
                                        suggest(service, compose.project, generic)))
    return findings


def vhost_findings(root: str, composes: list[Compose], generic: frozenset[str]) -> list[Finding]:
    """A vhost whose basename is generic: the shared `conf.d` is a flat namespace too.

    Asserted as non-generic rather than as project-prefixed, which is what the fleet measures:
    the host repo keeps a draft of a tenant's vhost to be diffed against theirs, so that file
    carries the tenant's name and not the host's own. A repo-local check cannot see
    that two repos picked the same basename either way — refusing the generic ones is the whole of
    the cross-repo protection a single-repo check can offer.
    """
    projects = [c.project for c in composes if c.project]
    replacement = f"{projects[0]}.caddy" if len(set(projects)) == 1 else "{{project-name}}.caddy"
    findings = []
    for path in find_files(root)[1]:
        stem = os.path.basename(path)[: -len(".caddy")]
        if stem.casefold() in generic:
            findings.append(Finding("vhost", rel(root, path), 0, os.path.basename(path),
                                    [f"{stem!r} is a generic basename, and a vhost copied into the proxy's shared "
                                     f"conf.d is separated from its neighbours by nothing else — the same basename "
                                     f"overwrites theirs at the next reload, with a config that validates"],
                                    replacement))
    return findings


def call_sites(root: str, name: str, files: list[str]) -> list[str]:
    """Where a rename has to reach, searched across `files` and nowhere else.

    The caller supplies the file list so apply walks the tree once rather than once per finding.
    It is the compose files, the vhosts and the publish config, and not the whole repo, on purpose:
    a word search for `app` across a
    Next.js tree returns the source directory and nothing useful; these three are where a compose
    service name is actually *dialled*, and they include the derived container name a vhost holds
    (printlab's `printlab-app-1`), which changes the moment a container_name is added.

    Values from `config/publish.env` are never printed. It is a transcrypt-encrypted file that is
    plaintext in the working tree, so the key name and the line number say where to look without
    putting anything from it into a transcript.
    """
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])")
    sites = []
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        where = rel(root, path)
        for number, line in enumerate(text.splitlines(), 1):
            if not pattern.search(line):
                continue
            if where == PUBLISH_ENV:
                key = line.split("=", 1)[0].strip()
                shown = key if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) else "in a comment"
                sites.append(f"{where}:{number}: {shown}")
            else:
                sites.append(f"{where}:{number}: {line.strip()[:110]}")
    return sites


def print_refusals(refusals: list[str]) -> None:
    print(f"{len(refusals)} compose line(s) this step cannot classify as a top-level key, a service key, one of a "
          f"service's own keys, or a value belonging to the key above it:")
    for problem in refusals:
        print(f"  {problem}")
    print("Nothing was read past them and nothing was written. A service this reader cannot see is a name it would "
          "have asserted without looking, which is the whole reason it stops instead.")


def location(finding: Finding) -> str:
    """Where the offending name is written. A vhost's is its own path, so it carries no line."""
    return f"{finding.path}:{finding.line_no}" if finding.kind == "service" else finding.path


def headline(finding: Finding) -> str:
    """The name and what it becomes — or the name alone, where only its container_name is wrong.

    An arrow from a name to itself reads as a no-op and invites a reader to skip the finding. The
    change there is real, and it sits in the instruction line below.
    """
    return f"{finding.subject} -> {finding.rename}" if finding.subject != finding.rename else finding.subject


def instruction(finding: Finding) -> str:
    """The edit itself, in one sentence — the same words in the listing and in apply's detail."""
    if finding.kind != "service":
        return f"rename the file to {finding.rename}, and change whatever copies it into the proxy's conf.d"
    if finding.subject == finding.rename:
        return f"the key is already right; container_name becomes {finding.rename!r} to match it"
    return f"the service key and its container_name both become {finding.rename!r}"


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"  {location(finding)}  {headline(finding)}")
        for reason in finding.reasons:
            print(f"      {reason}")
        print(f"      {instruction(finding)}")


def evidence(root: str) -> list[str]:
    """What says this repo deploys to the shared box, in the words probe reports it with."""
    composes, vhosts = find_files(root)
    found = []
    if composes:
        found.append(f"{len(composes)} compose file(s)")
    if vhosts:
        found.append(f"{len(vhosts)} .caddy vhost(s)")
    if os.path.isfile(os.path.join(root, *PUBLISH_ENV.split("/"))):
        found.append(PUBLISH_ENV)
    return found


def gather(root: str) -> tuple[list[Compose], list[Finding], list[str], str]:
    """Everything the three subcommands read. -> (composes, findings, refusals, blocking reason)

    The blocking reason is non-empty when the shape cannot be observed at all, and it is what
    separates verify's exit 2 from its exit 3: a repo with no compose file has nothing to be
    asserted against, while a repo with one and a generic service key has a definite answer.
    """
    generic, missing = load_generic()
    if missing:
        return [], [], [], missing
    composes, refusals, unreadable = read_composes(root)
    if unreadable:
        return composes, [], refusals, f"{len(unreadable)} compose file(s) could not be opened: {', '.join(unreadable)}"
    if refusals:
        return composes, [], refusals, ""
    if not composes:
        return composes, [], refusals, "there is no compose file in this repo, so there is no service name to assert"
    nameless = [c.path for c in composes if not c.project]
    if nameless:
        return composes, [], refusals, (f"{', '.join(nameless)} declares no top-level `name:`, so the compose project "
                                        f"name is derived from whatever directory the stack is brought up in and the "
                                        f"prefix every service should carry has no stable value to check against")
    if not any(c.services for c in composes):
        return composes, [], refusals, (f"{len(composes)} compose file(s) and no service key in any of them, so there "
                                        f"is nothing here for this convention to be true or false about")
    findings = service_findings(composes, generic) + vhost_findings(root, composes, generic)
    return composes, findings, refusals, ""


def cmd_verify(root: str) -> int:
    composes, findings, refusals, blocked = gather(root)
    if refusals:
        print_refusals(refusals)
        return 3
    if blocked:
        print(blocked)
        return 2
    if findings:
        print(f"{len(findings)} name(s) in this repo are not in the shape this convention requires:")
        print_findings(findings)
        return 3
    total = sum(len(c.services) for c in composes)
    print(f"{total} service(s) across {len(composes)} compose file(s): each carries its compose project's name, is "
          f"outside the generic set, and equals its own container_name")
    vhosts = find_files(root)[1]
    print(f"{len(vhosts)} .caddy vhost basename(s) outside the generic set" if vhosts
          else "no .caddy vhost in this repo, so the shared conf.d half had nothing to assert")
    return 0


def cmd_probe(root: str) -> int:
    """Never 0: this step has no apply, so /adopt must never be sent to one.

    Exit 1 needs positive evidence and gets it here — no compose file, no vhost and no publish
    config together say this repo deploys nothing to the shared box today. `audit` re-runs probe
    for every `n/a` line, so the next tenant surfaces as a finding rather than as a silence.
    """
    composes, findings, refusals, blocked = gather(root)
    if refusals:
        print_refusals(refusals)
        return 3
    present = evidence(root)
    if not present:
        print("no compose file, no .caddy vhost and no config/publish.env: this repo deploys nothing to the shared "
              "box today, so it claims no name in a namespace another project writes to")
        return 1
    if blocked:
        print(f"{blocked}. This repo does carry {', '.join(present)}, so whether the convention applies is a question "
              f"rather than a no.")
        return 2
    if not findings:
        print(f"nothing offending found across {', '.join(present)} — this repo's shape is what verify asserts, and "
              f"verify is what records it")
        return 2
    print(f"{len(findings)} name(s) here sit in a namespace this repo shares with other tenants, and renaming a "
          f"compose service reaches call sites no probe can enumerate for you:")
    print_findings(findings)
    print("Run this step's apply to see the references each rename has to reach. This step never edits a compose "
          "file: a rename that misses one reference takes the site down behind an HTTP 200.")
    return 2


def cmd_apply(root: str, dry_run: bool) -> int:
    """Always 3. A machine can find and name this deviation; it must never make it itself.

    `--dry-run` and a real run print the same thing, because nothing is ever written either way.
    What is printed is the rename and the references found for it, which is the half a human
    cannot cheaply reconstruct — and the reason a rename is dangerous is exactly that the set of
    references is wider than the file being edited.
    """
    composes, findings, refusals, blocked = gather(root)
    if refusals:
        print_refusals(refusals)
        return 3
    if blocked:
        print(f"{blocked}, so there is nothing for this step to describe. Nothing was written.")
        return 3
    if not findings:
        print("every service name here already carries its project and equals its container_name, and no vhost "
              "basename is generic. Nothing to do, and nothing was written.")
        return 3
    print(f"{len(findings)} rename(s) a human makes, by hand. This step writes nothing: a compose service name is "
          f"dialled from places a repo-wide search cannot safely enumerate, and one reference left behind serves a "
          f"neighbour's application at HTTP 200 with every healthcheck green.")
    composes, vhosts = find_files(root)
    env = os.path.join(root, *PUBLISH_ENV.split("/"))
    searched = [*composes, *vhosts, *([env] if os.path.isfile(env) else [])]
    for finding in findings:
        print(f"\n{location(finding)}  {headline(finding)}")
        for reason in finding.reasons:
            print(f"    {reason}")
        print(f"    {instruction(finding)}")
        sites = call_sites(root, finding.subject, searched)
        if sites:
            print(f"    {len(sites)} reference(s) to {finding.subject!r} that the rename has to reach:")
            for site in sites:
                print(f"      {site}")
        else:
            print(f"    no reference to {finding.subject!r} in this repo's compose files, .caddy vhosts or "
                  f"{PUBLISH_ENV} — which is not the same as none anywhere")
    print(f"\nSearched this repo's compose files, its .caddy vhosts and {PUBLISH_ENV}, and nothing else. A deploy "
          f"script, a Dockerfile, a runbook or the box's own systemd units can name a service too, and "
          f"{PUBLISH_ENV} reads as ciphertext in a transcrypt-locked checkout.")
    print("On the box, after the edit: `docker rm -f <old-container>` then "
          "`docker compose up -d --no-deps <new-service-name>`, so one-shot siblings do not re-run. Volumes are "
          "named after the compose project and not the service, so renaming a service keeps the data; renaming the "
          "project does not.")
    print("Then re-run this step's verify, which is what records the repo.")
    return 3


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
