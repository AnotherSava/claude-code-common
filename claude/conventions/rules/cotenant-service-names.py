"""Every compose service is named after its project and equals its container.

Compose publishes a *service's* key as a DNS alias on every network the service joins, so `app`,
`db`, `caddy` and friends are claims staked in a namespace the neighbours also write to. Two
projects each calling a service `app` both answer to `app` on the shared bridge, and the proxy
dials whichever the daemon hands back: that is the 41 hours a commercial storefront spent serving a
neighbour's application, at HTTP 200, with every container healthy and the config valid
(learnings/docker-compose-shared-host-co-tenancy.md).

This detects and never edits, here and in the migration alike. A rename reaches `depends_on`, the
vhost's `reverse_proxy` upstream, `BUILD_SERVICES` and `APP_CONTAINER` in an encrypted
`config/publish.env`, and the derived container name a proxy dials — and one missed reference takes
the site down behind an HTTP 200, which is the failure mode this convention exists to prevent.

Three decisions worth knowing before reading the code.

**The scan is not scoped to services that join an `external:` network**, which is how
`scripts/ingress-lint.py` scopes the same rule. One tenant here is the measured reason: two of its
services declare no `networks:` key at all, and the host's own compose file joins that tenant's
default network to reach them — so the proxy straddles the bridge those two sit on, and "it is not
on the shared network today" is exactly the defence that does not hold. The real incident had its
two claimants of `app` on different bridges with the proxy across both.

**The generic denylist is imported from that lint rather than copied**, so the gate that blocks a
commit and the rule that reports a repo cannot disagree about what generic means. Two names the
fleet's own compose files use are added here: `mongo` and `migrate`.

**The reader refuses rather than skips.** It classifies every content line as a top-level key, a
service key, one of a service's own keys, or a value belonging to the key above it — and raises on
anything else, naming the line verbatim. A YAML merge key is the case that makes this more than
fussiness: `<<: *common` can supply a `container_name` this line scanner cannot see, so a reader
that skipped it would report a shape it never read.
"""

import importlib.util
import os
import re
from typing import NamedTuple

# <repo>/claude/conventions/rules -> <repo>/claude/scripts/ingress-lint.py
INGRESS_LINT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.realpath(__file__)))), "scripts", "ingress-lint.py")
# Names the fleet's compose files use that the lint's list does not carry. `migrate` is a one-shot
# in three repos here and `mongo` is one tenant's database, and both are as ownerless on a shared
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


def generic_names() -> frozenset[str]:
    """The denylist, read from the ingress lint — never a second copy of it.

    Imported rather than duplicated: that file is the commit gate for the same rule, and a second
    copy of a list is a copy that drifts. A rule that quietly fell back to its own copy would keep
    passing repos the gate refuses, which is worse than refusing to judge.
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

    A quote-aware walk rather than a `split("#")`: real compose values carry them — an `IGNORE_IP`
    list and a healthcheck command both do — and cutting one mid-value turns a readable key line
    into a line this reader would refuse.
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


def parse_compose(text: str, path: str) -> tuple[Compose, list[str]]:
    """Read one compose file's project name and service keys. -> (compose, refusals)

    A line scan and not a YAML parser, because the checker reaches this under a plain interpreter
    with no dependency file behind it and PyYAML is not in the standard library. What makes the scan
    safe is that it refuses: every content line is classified as a top-level key, a service key, one
    of a service's immediate keys, or a value belonging to the key above it, and anything else comes
    back as a refusal the caller raises on.

    Indent is measured rather than assumed to be two spaces. The first line inside `services:` fixes
    the service-key column and the first line inside a service fixes its own key column, so a file
    indented four spaces reads the same and a line landing between the two columns is a refusal
    rather than a guess about which it meant.
    """
    project, services, refusals = "", [], []
    in_services, service_indent, child_indent = False, None, None

    def refuse(number: int, line: str, why: str) -> None:
        refusals.append(f"{path}:{number}: {line.strip()} — {why}")

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


def find_files(root: str) -> tuple[list[str], list[str]]:
    """Every compose file and every `*.caddy` vhost in the repo, absolute, sorted.

    A `Caddyfile` is deliberately not a vhost: it is the base config of a proxy the repo owns, it is
    never copied into somebody else's `conf.d`, and its name is fixed by Caddy — so the basename
    rule below has nothing to say about it.
    """
    composes, vhosts = [], []
    # walk-unfiltered: and it must stay that way. The Node rules narrow their walk to what git does
    # not hide, because a hidden `package.json` is a scratch clone nobody maintains. The same
    # reasoning inverts here: a `compose.override.yml` or a vhost kept out of git *because it carries
    # host paths* is still the file the box brings up, so its service keys are live on the shared
    # bridge. Narrowing this walk was tried and reverted — it turned a finding into a silent pass on
    # exactly the generic-name collision that cost a commercial site 41 hours.
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(files):
            if COMPOSE_RE.match(name):
                composes.append(os.path.join(base, name))
            elif name.endswith(".caddy"):
                vhosts.append(os.path.join(base, name))
    return composes, vhosts


def read_composes(root: str) -> tuple[list[Compose], list[str], list[str]]:
    """(parsed compose files, refusals, files that could not be opened at all)."""
    parsed, refusals, unreadable = [], [], []
    for path in find_files(root)[0]:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            unreadable.append(rel(root, path))
            continue
        compose, problems = parse_compose(text, rel(root, path))
        parsed.append(compose)
        refusals.extend(problems)
    return parsed, refusals, unreadable


def is_prefixed(name: str, project: str) -> bool:
    """Whether a name belongs to this project: equal to it, or opened by it and a hyphen."""
    return bool(project) and (name == project or name.startswith(f"{project}-"))


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


def service_findings(composes: list[Compose], generic: frozenset[str]) -> list[Finding]:
    """One finding per offending service, carrying every rule that service breaks.

    One finding rather than one per rule, so the advice cannot contradict itself: a generic name is
    not repaired by pinning `container_name` to that same generic word.
    """
    findings = []
    for compose in composes:
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

    Asserted as non-generic rather than as project-prefixed, which is what the fleet measures: the
    host repo keeps a draft of a tenant's vhost to be diffed against theirs, so that file carries
    the tenant's name and not the host's own. A repo-local check cannot see that two repos picked
    the same basename either way — refusing the generic ones is the whole of the cross-repo
    protection a single-repo check can offer.
    """
    projects = [compose.project for compose in composes if compose.project]
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


def location(finding: Finding) -> str:
    """Where the offending name is written. A vhost's is its own path, so it carries no line."""
    return f"{finding.path}:{finding.line_no}" if finding.kind == "service" else finding.path


def headline(finding: Finding) -> str:
    """The name and what it becomes — or the name alone, where only its container_name is wrong.

    An arrow from a name to itself reads as a no-op and invites a reader to skip the finding. The
    change there is real, and it sits in the instruction.
    """
    return f"{finding.subject} -> {finding.rename}" if finding.subject != finding.rename else finding.subject


def instruction(finding: Finding) -> str:
    """The edit itself, in one sentence."""
    if finding.kind != "service":
        return f"rename the file to {finding.rename}, and change whatever copies it into the proxy's conf.d"
    if finding.subject == finding.rename:
        return f"the key is already right; container_name becomes {finding.rename!r} to match it"
    return f"the service key and its container_name both become {finding.rename!r}"


def check(root: str) -> list[str]:
    """One line per name in this repo that sits in a namespace another tenant also writes to."""
    generic = generic_names()
    composes, refusals, unreadable = read_composes(root)
    if unreadable:
        raise OSError(f"{len(unreadable)} compose file(s) could not be opened ({', '.join(unreadable)}), so the "
                      f"names they publish on the shared bridge were never read")
    if refusals:
        # A line this reader cannot classify is a service it would have asserted about without
        # looking, which is why it stops instead. Raised rather than reported as a violation: the
        # names may well be right, and what is wrong is that nobody here can say.
        raise ValueError(f"{len(refusals)} compose line(s) could not be classified as a top-level key, a service "
                         f"key, one of a service's own keys, or a value belonging to the key above it, so nothing "
                         f"was read past them: " + " | ".join(refusals))
    if not composes:
        # No compose file, so this repo brings nothing up on the shared bridge and claims no name in
        # a namespace another project writes to. Read off a walk of the whole tree, not off one path.
        return []
    nameless = [compose.path for compose in composes if not compose.project]
    if nameless:
        raise ValueError(f"{', '.join(nameless)} declares no top-level `name:`, so the compose project name is "
                         f"derived from whatever directory the stack is brought up in and the prefix every "
                         f"service should carry has no stable value to check against")
    findings = service_findings(composes, generic) + vhost_findings(root, composes, generic)
    return [f"{location(finding)}  {headline(finding)}: {instruction(finding)} — {'; '.join(finding.reasons)}"
            for finding in findings]
