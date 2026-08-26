#!/usr/bin/env python3
"""Fail a change that would let one project on a shared host hijack another's name.

Two rules, both hard failures:

  COMPOSE  a service that joins an `external: true` network must set container_name, it must equal the
           service key, and that name must not be generic.
  CADDY    a reverse_proxy upstream must never be a bare compose service name, and must never be generic.

Why: docker compose publishes a service's NAME as a DNS alias on EVERY network the service joins, shared
external ones included. Two projects each with a service called "app" therefore both answer to "app" on the
shared bridge, and a proxy attached to it resolves whichever the daemon hands back. In August 2026 that put a
commercial storefront on a neighbour's application for 41 hours — HTTP 200 throughout, every healthcheck
green, the config valid. Nothing detects this after the fact except an identity assertion; this prevents it
instead, at the moment the name is written.

Deliberately stdlib-only, with a hand-rolled reader for the small YAML subset it needs: Claude Code hooks run
`python -S`, which drops site-packages, so PyYAML is not importable there.

Usage:  ingress-lint.py [path ...]      # files or repo roots; defaults to the current directory
Exit:   0 clean, 1 violations found, 2 nothing to check
"""

import os
import re
import sys

# Names no single project may own on a bridge it shares with others.
GENERIC = {
    "app", "web", "api", "db", "database", "redis", "postgres", "mysql", "proxy", "nginx", "caddy",
    "traefik", "worker", "admin", "main", "site", "server", "backend", "frontend", "cache", "queue",
}

COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


# ----------------------------------------------------------------------------- tiny YAML subset reader
def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def read_compose(text: str) -> tuple[dict, set]:
    """-> ({service: {"container_name": str|None, "networks": [str]}}, {external network names})

    Understands only what the rules need: two levels of mapping plus list items. Anything it cannot parse it
    ignores, which biases toward false negatives — a lint that blocks commits must not invent violations.
    """
    services: dict[str, dict] = {}
    external: set[str] = set()

    section = None          # "services" | "networks" | other
    cur_name = None         # current service/network key
    cur_list = None         # which key's list we are accumulating
    net_indent = None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw.rstrip()
        ind = _indent(line)
        body = line.strip()

        if ind == 0:
            section = body[:-1] if body.endswith(":") else None
            cur_name = cur_list = None
            continue

        if section not in ("services", "networks"):
            continue

        # A key at 2 spaces names a service or a network.
        if ind == 2 and body.endswith(":"):
            cur_name = body[:-1].strip()
            cur_list = None
            if section == "services":
                services.setdefault(cur_name, {"container_name": None, "networks": []})
            continue

        if cur_name is None:
            continue

        if section == "networks":
            if re.match(r"external:\s*(true|yes)\s*$", body, re.I):
                external.add(cur_name)
            continue

        # ---- inside a service
        m = re.match(r"container_name:\s*(\S+)", body)
        if m:
            services[cur_name]["container_name"] = m.group(1).strip("'\"")
            continue

        if re.match(r"networks:\s*$", body):
            cur_list, net_indent = "networks", ind
            continue

        if re.match(r"networks:\s*\[(.*)\]", body):
            inner = re.match(r"networks:\s*\[(.*)\]", body).group(1)
            services[cur_name]["networks"] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            continue

        if cur_list == "networks":
            if body.startswith("- "):
                services[cur_name]["networks"].append(body[2:].strip().strip("'\""))
                continue
            # A mapping form (`networks:` then `  edge:`) still names the network.
            if ind > net_indent and body.endswith(":"):
                services[cur_name]["networks"].append(body[:-1].strip())
                continue
            cur_list = None

    return services, external


# ----------------------------------------------------------------------------- rules
def lint_compose(path: str) -> tuple[list[str], dict]:
    with open(path, encoding="utf-8") as fh:
        services, external = read_compose(fh.read())

    problems = []
    for name, svc in sorted(services.items()):
        joined = svc["networks"] or ["default"]
        shared = [n for n in joined if n in external]
        if not shared:
            continue
        where = ", ".join(shared)
        cn = svc["container_name"]
        # One finding per service, so the advice cannot contradict itself: a generic name is not fixed by
        # pinning container_name to that same generic name.
        if name in GENERIC:
            suggestion = cn if (cn and cn not in GENERIC) else f"<project>-{name}"
            problems.append(
                f"{path}: service '{name}' joins shared network(s) {where}, and '{name}' is generic. Compose "
                f"publishes the service key as an alias there, so the first project to claim it wins a race "
                f"nobody controls. Rename the service to '{suggestion}' and set container_name to match."
            )
        elif cn is None:
            problems.append(
                f"{path}: service '{name}' joins shared network(s) {where} without a container_name, so its "
                f"container gets a project-derived name while it also answers to '{name}'. Add "
                f"container_name: {name} so it owns exactly one name."
            )
        elif cn != name:
            problems.append(
                f"{path}: service '{name}' joins {where} but its container_name is '{cn}', so it answers to "
                f"BOTH names on that bridge — and the service key is the one everyone forgets. Rename the "
                f"service to '{cn}'."
            )
    return problems, services


def _site_addresses(line: str) -> list[str]:
    """The address list of a site-block opener, or [] if this line does not open one.

    A site block is `<addr>[, <addr>...] {` at column 0. Directives inside a block are indented in every
    convention we ship, and a keyless `{` is handled by its own rule, so requiring a non-empty prefix is enough.
    """
    m = re.match(r"^([^\s{][^{]*?)\s*\{\s*$", line)
    if not m:
        return []
    return [a.strip() for a in m.group(1).split(",") if a.strip()]


def lint_caddy_tenant(path: str) -> list[str]:
    """Refuse the constructs that let one tenant reach beyond its own hostnames.

    These are the site-address and snippet namespaces — shared, flat, and resolved from files this repo does not
    control, exactly like the DNS-alias namespace that caused the outage. A repo-local check cannot see that two
    repos claim the SAME hostname (that needs the on-box verifier), but it can refuse every construct whose only
    use is reaching past your own names. Verified against Caddy 2.11.4; each of these ADAPTS CLEANLY, which is
    why nothing downstream catches them.
    """
    problems, depth = [], 0
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    # These are TENANT rules. The proxy owner's own layer is where global options and snippet definitions are
    # supposed to live, so applying them there would flag the very constructs that close the tenant hole.
    # Two ways a file belongs to the host layer:
    #   - it imports the shared conf.d directory, which only a base config does;
    #   - it sits in a host-owned fragment dir (snippets.d/, global.d/), which is where a multi-host proxy repo
    #     keeps the capability definitions tenants merely `import` by name.
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    if "snippets.d" in parts or "global.d" in parts:
        return []
    if re.search(r"^[ \t]*import[ \t]+[^\s]*conf\.d", text, re.MULTILINE):
        return []

    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].rstrip()
            stripped = line.strip()
            if not stripped:
                continue

            if depth == 0:
                # R4 — a snippet DEFINITION. Redeclaring one another file already defines is a hard error that
                # refuses the whole config for every tenant on the box.
                if re.match(r"^\(([^)]+)\)\s*\{\s*$", stripped):
                    name = re.match(r"^\(([^)]+)\)", stripped).group(1)
                    problems.append(
                        f"{path}:{n}: defines snippet '({name})'. Snippet names are shared across every file the "
                        f"proxy imports; redeclaring one refuses the WHOLE config, for every tenant. Only the "
                        f"host's base config should define snippets — import them, do not declare them."
                    )
                # R1 — a keyless block is Caddy's GLOBAL options block. Where the base config has none, a
                # tenant's is accepted and applies box-wide, with validate green and nothing in any log.
                elif stripped == "{":
                    problems.append(
                        f"{path}:{n}: opens a keyless block, which Caddy reads as GLOBAL options. From a file in "
                        f"a shared conf.d that sets options for every project on the host. Global options belong "
                        f"to the host's base config only."
                    )
                else:
                    for addr in _site_addresses(stripped):
                        bare = re.sub(r"^https?://", "", addr)
                        # R3 — a port-only address becomes the catch-all for every unnamed hostname.
                        if re.match(r"^:\d+$", bare):
                            problems.append(
                                f"{path}:{n}: site address '{addr}' is port-only, so it catches EVERY hostname "
                                f"the proxy has no named block for — including other tenants'. Name your hosts."
                            )
                        # R2 — a path in a site address silently outranks a neighbour's bare hostname for that
                        # path, so two individually valid files hijack one hostname.
                        # NB: do not strip the trailing slash first — `h.example/` IS the path form, and it is
                        # the exact construct that shadows a neighbour's plain `h.example` block.
                        elif "/" in bare:
                            problems.append(
                                f"{path}:{n}: site address '{addr}' carries a path. A path-carrying address wins "
                                f"over a plain hostname block for that path, so this can shadow a neighbour's "
                                f"hostname from a file that adapts cleanly. Match paths inside the block instead."
                            )

            depth += stripped.count("{") - stripped.count("}")
            depth = max(depth, 0)
    return problems


def lint_caddy(path: str, services: dict) -> list[str]:
    problems = lint_caddy_tenant(path)
    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].strip()
            m = re.match(r"(?:reverse_proxy|to)\s+(.+)$", line)
            if not m:
                continue
            for target in m.group(1).split():
                if target.startswith("{") or target.startswith("unix/") or "://" in target:
                    continue
                host = target.rsplit(":", 1)[0] if re.search(r":\d+$", target) else target
                if not host or "." in host or host[0].isdigit() or host in ("localhost",):
                    continue
                if host in GENERIC:
                    problems.append(
                        f"{path}:{n}: dials '{host}', a generic name. On a host whose proxy straddles several "
                        f"bridges this resolves to whichever container claimed it — dial a container name."
                    )
                    continue
                svc = services.get(host)
                if svc is not None and svc["container_name"] != host:
                    problems.append(
                        f"{path}:{n}: dials '{host}', which is a compose SERVICE name in this repo, not a "
                        f"container name. Service names are unique only within their project; dial "
                        f"'{svc['container_name'] or 'the container name'}' instead."
                    )
    return problems


# ----------------------------------------------------------------------------- driver
def collect(paths: list[str]) -> tuple[list[str], list[str]]:
    composes, caddys = [], []
    for p in paths:
        if os.path.isfile(p):
            (composes if os.path.basename(p) in COMPOSE_NAMES else caddys).append(p)
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".next", "dist", "build"}]
            for f in files:
                full = os.path.join(root, f)
                if f in COMPOSE_NAMES:
                    composes.append(full)
                elif f.endswith(".caddy") or f == "Caddyfile":
                    caddys.append(full)
    return sorted(composes), sorted(caddys)


def repo_root_of(path: str) -> str | None:
    """The nearest ancestor holding a .git, or None outside a repo."""
    current = os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path))
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def context_services(report_paths: list[str]) -> dict:
    """Every compose service declared in the repos containing the files being reported on.

    Checked separately from what gets reported because the Caddy rule is cross-file: deciding whether an
    upstream is a compose SERVICE name needs the repo's compose files, and a caller that names one `.caddy`
    file — a hook receiving a single changed path, say — supplies none of them. Without this the rule cannot
    fire and the lint quietly degrades to the denylist half, which is worse than not running: it still prints
    "clean".
    """
    services: dict = {}
    for root in {r for p in report_paths if (r := repo_root_of(p))}:
        for compose in collect([root])[0]:
            try:
                with open(compose, encoding="utf-8") as fh:
                    found, _ = read_compose(fh.read())
                services.update(found)
            except OSError:
                continue
    return services


def lint(paths: list[str]) -> tuple[list[str], int]:
    """The whole check, as a function: -> (problems, files scanned).

    Separate from `main` so callers that are not a terminal can have the findings without the printing —
    specifically the PostToolUse hook, which has to put them in a JSON field on stdout and would otherwise
    reimplement this orchestration and drift from it.
    """
    composes, caddys = collect(paths)

    # Findings are reported only for the files named, but judged with the whole repo's services in view.
    problems: list[str] = []
    services: dict = context_services(composes + caddys)
    for path in composes:
        found, svc = lint_compose(path)
        problems += found
        services.update(svc)
    for path in caddys:
        problems += lint_caddy(path, services)

    return problems, len(composes) + len(caddys)


def main(argv: list[str]) -> int:
    problems, scanned = lint(argv or ["."])
    if scanned == 0:
        print("nothing to check (no compose or Caddy files found)", file=sys.stderr)
        return 2

    if problems:
        print(f"ingress-lint: {len(problems)} violation(s) across {scanned} file(s)\n")
        for p in problems:
            print(f"  {p}\n")
        return 1

    print(f"ingress-lint: clean ({scanned} file(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
