#!/usr/bin/env python3
"""Fail a change that would let one project on a shared host hijack another's name.

Two rules, both hard failures:

  COMPOSE  a service that joins an `external: true` network must set container_name, it must equal the
           service key, and that name must not be generic.
  CADDY    a reverse_proxy upstream must never be a bare compose service name, and must never be generic.

Those two are this file's own and apply anywhere. A third set — landlord's tenancy rules R1-R7, about what a
vhost may claim inside a shared conf.d — is NOT implemented here: this file delegates to landlord's
`bin/vhost-lint.py`, the copy its on-box gate enforces, and only for the one file `VHOST_SRC` in
`config/publish.env` names. Three situations then report NOT CHECKED rather than skipping quietly: an absent
landlord checkout, a repo that declares no `VHOST_SRC` at all — where nothing knows whether the rules even
apply — and a `VHOST_SRC` naming a file that does not exist, where they ran against nothing. Set
`$CLAUDE_LANDLORD` if the checkout is not a sibling of the repo being linted.

Why: docker compose publishes a service's NAME as a DNS alias on EVERY network the service joins, shared
external ones included. Two projects each with a service called "app" therefore both answer to "app" on the
shared bridge, and a proxy attached to it resolves whichever the daemon hands back. In August 2026 that put a
commercial storefront on a neighbour's application for 41 hours — HTTP 200 throughout, every healthcheck
green, the config valid. Nothing detects this after the fact except an identity assertion; this prevents it
instead, at the moment the name is written.

Deliberately stdlib-only, with a hand-rolled reader for the small YAML subset it needs: Claude Code hooks run
`python -S`, which drops site-packages, so PyYAML is not importable there.

Tests: claude/tests/ingress-lint.py

Usage:  ingress-lint.py [path ...]      # files or repo roots; defaults to the current directory
Exit:   0 clean, 1 violations found, 2 nothing to check
        A rule set that could not RUN is not a violation and does not change the exit status — it is printed
        as NOT CHECKED, and exit 0 then reads "no violations in what ran", never "clean".
"""

import importlib.util
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


def _publish_env_value(repo_root: str, key: str) -> str | None:
    """One `KEY=value` from the repo's `config/publish.env`, or None.

    Deliberately not a shell source: that file's `IDENTITY_CHECK` is a semicolon-separated PROGRAM, not a
    value, so sourcing it would execute ssh. A line-wise read of one key cannot.
    """
    try:
        with open(os.path.join(repo_root, "config", "publish.env"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        return None
    return None


def _find_landlord(repo_root: str) -> str | None:
    """The landlord checkout holding the authoritative tenancy rules, or None.

    `$CLAUDE_LANDLORD` first, then a sibling of this repo — the layout every machine here already has. A
    directory only counts once `bin/vhost-lint.py` is actually in it, so a stale variable pointing at a moved
    or half-deleted checkout reads as absent rather than as a broken import.
    """
    candidates = [os.environ.get("CLAUDE_LANDLORD"), os.path.join(os.path.dirname(repo_root), "landlord")]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "bin", "vhost-lint.py")):
            return candidate
    return None


def lint_caddy_tenant(path: str) -> tuple[list[str], list[str]]:
    """Refuse the constructs that let one tenant reach beyond its own hostnames: -> (problems, notices).

    The rules are landlord's R1-R7 and live in its `bin/vhost-lint.py`, which is the authoritative copy and the
    one its gate enforces on the box. This function only decides whether they apply and then calls them. It used
    to reimplement four of them against a reader too weak to feed them — line-continued address lists, heredoc
    bodies carrying an unmatched brace, and one-line snippet definitions all reached no rule at all and reported
    clean. A second copy of a rule is a copy that drifts, and this one drifted silently.

    Three conditions, and failing any of them is not a violation. One is silence and two are notices, and which
    is which is the entire point. A fourth way the rules end up running against nothing — a `VHOST_SRC` naming a
    file that is not there — is not visible from one file and lives in `declared_vhost_notices`:

      not our vhost   the tenancy rules describe a file installed into somebody else's conf.d. Applied to an
                      ordinary standalone Caddyfile they are simply wrong — a keyless global-options block, a
                      snippet definition and a port-only address are all legitimate when you own the proxy, and
                      measured as three false positives on one such file. `VHOST_SRC` in `config/publish.env` is
                      what names the file this repo installs; another file it names is skipped in silence, and
                      so is every file in a repo whose `VHOST_SRC=` is empty — that is a repo saying out loud
                      that it installs no vhost.
      undeclared      a repo with no `VHOST_SRC` line at all has said nothing, and "unknown" is not "not
                      applicable". Silence here is how a live tenant reads as clean: a checkout of tripit
                      without `config/publish.env` printed `clean (2 file(s) checked)` over the `trips.caddy`
                      that landlord grants it and that its own commit gate calls this script to check, having
                      applied no tenancy rule to it — the same sentence, to the character, that a real pass
                      prints. So this returns a NOTICE.
      no landlord     without the checkout there are no rules to run. A NOTICE too, never silence and never a
                      bare "clean" — a check that cannot tell "passed" from "never ran" is the exact failure
                      this file exists to prevent.

    `owns` and `capabilities` are passed as None, which skips R6/R7 — the two rules needing host data this repo
    does not have. None is not an empty set: an empty `capabilities` means "this host contracts nothing", so R6
    would fire on every legitimate `import`.
    """
    # These are TENANT rules. The proxy owner's own layer is where global options and snippet definitions are
    # supposed to live, so applying them there would flag the very constructs that close the tenant hole.
    # Two ways a file belongs to the host layer:
    #   - it imports the shared conf.d directory, which only a base config does;
    #   - it sits in a host-owned fragment dir (snippets.d/, global.d/), which is where a multi-host proxy repo
    #     keeps the capability definitions tenants merely `import` by name.
    # landlord's lint has no equivalent classifier and would flag both, so this stays here.
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    if "snippets.d" in parts or "global.d" in parts:
        return [], []
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return [], []
    if re.search(r"^[ \t]*import[ \t]+[^\s]*conf\.d", text, re.MULTILINE):
        return [], []

    repo_root = repo_root_of(path)
    if repo_root is None:
        return [], []
    vhost_src = _publish_env_value(repo_root, "VHOST_SRC")
    if vhost_src is None:
        # Not "has no VHOST_SRC line": a transcrypt-locked checkout reads as ciphertext, so the line can be
        # there and unreadable, and a message asserting its absence would send someone to add a second one.
        has_env = os.path.isfile(os.path.join(repo_root, "config", "publish.env"))
        missing = ("no VHOST_SRC is readable in config/publish.env — a transcrypt-locked checkout reads as "
                   "ciphertext, so unlock it first" if has_env else "there is no config/publish.env")
        return [], [
            f"{path}: tenancy rules (landlord R1-R7) NOT CHECKED — {missing}, so nothing here knows whether "
            f"this file is a vhost installed into somebody else's conf.d, where the rules apply, or the "
            f"Caddyfile of a proxy this project owns, where they would be false positives. Add a VHOST_SRC "
            f"line naming this file, relative to {repo_root}, to have them run against it — or an empty "
            f"VHOST_SRC= to record that this repo installs no vhost. The compose rules above ran normally."
        ]
    if not vhost_src:
        return [], []
    if os.path.realpath(os.path.join(repo_root, vhost_src)) != os.path.realpath(path):
        return [], []

    landlord = _find_landlord(repo_root)
    if landlord is None:
        return [], [
            f"{path}: tenancy rules (landlord R1-R7) NOT CHECKED — no landlord checkout found. Looked at "
            f"$CLAUDE_LANDLORD and a 'landlord' sibling of {repo_root}. This file IS this repo's VHOST_SRC, so "
            f"the rules do apply to it; nothing here says whether it satisfies them. The compose rules above "
            f"ran normally."
        ]

    vhost_lint = os.path.join(landlord, "bin", "vhost-lint.py")
    try:
        spec = importlib.util.spec_from_file_location("vhost_lint", vhost_lint)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.lint(path, None, None), []
    except Exception as exc:
        return [], [
            f"{path}: tenancy rules (landlord R1-R7) NOT CHECKED — {vhost_lint} would not load or run "
            f"({type(exc).__name__}: {exc}). This file IS this repo's VHOST_SRC, so the rules do apply to it."
        ]


def lint_caddy(path: str, services: dict) -> tuple[list[str], list[str]]:
    problems, notices = lint_caddy_tenant(path)
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
    return problems, notices


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


def repo_roots_of(paths: list[str]) -> set[str]:
    """The distinct repos the given files sit in, dropping any that sit outside one."""
    return {root for p in paths if (root := repo_root_of(p))}


def declared_vhost_notices(repo_roots: set[str]) -> list[str]:
    """One notice per repo whose declared `VHOST_SRC` names a file that is not there.

    The per-file check skips every Caddy file that is not the declared one, so a declaration left pointing at a
    moved or not-yet-created path makes it skip all of them and say nothing — the third route to a pass that
    covers nothing. Reported per repo rather than per file because the fault is in the declaration, and the
    files it caused to be skipped are only its symptom.
    """
    notices = []
    for root in sorted(repo_roots):
        vhost_src = _publish_env_value(root, "VHOST_SRC")
        if vhost_src and not os.path.exists(os.path.join(root, vhost_src)):
            notices.append(
                f"{os.path.join(root, vhost_src)}: tenancy rules (landlord R1-R7) NOT CHECKED — "
                f"config/publish.env declares VHOST_SRC={vhost_src} and no such file exists, so they had "
                f"nothing to run against. Every other Caddy file here was skipped for not being that one, "
                f"which leaves the pass below covering no vhost at all."
            )
    return notices


def context_services(repo_roots: set[str]) -> dict:
    """Every compose service declared in the repos containing the files being reported on.

    Checked separately from what gets reported because the Caddy rule is cross-file: deciding whether an
    upstream is a compose SERVICE name needs the repo's compose files, and a caller that names one `.caddy`
    file — a hook receiving a single changed path, say — supplies none of them. Without this the rule cannot
    fire and the lint quietly degrades to the denylist half, which is worse than not running: it still prints
    "clean".
    """
    services: dict = {}
    for root in sorted(repo_roots):
        for compose in collect([root])[0]:
            try:
                with open(compose, encoding="utf-8") as fh:
                    found, _ = read_compose(fh.read())
                services.update(found)
            except OSError:
                continue
    return services


def lint(paths: list[str]) -> tuple[list[str], int, list[str]]:
    """The whole check, as a function: -> (problems, files scanned, notices).

    Separate from `main` so callers that are not a terminal can have the findings without the printing —
    specifically the PostToolUse hook, which has to put them in a JSON field on stdout and would otherwise
    reimplement this orchestration and drift from it.

    Notices are the third outcome, and they are not violations: they say a rule set did not run — because its
    dependency is absent, because nothing declared whether it applies, or because what it was pointed at is not
    there. They ride alongside `problems` rather than inside it because they must not set the exit status — but
    a caller that drops them turns "not checked" back into something that reads like "passed".
    """
    composes, caddys = collect(paths)

    # Findings are reported only for the files named, but judged with the whole repo's services in view.
    roots = repo_roots_of(composes + caddys)
    problems: list[str] = []
    notices: list[str] = declared_vhost_notices(roots)
    services: dict = context_services(roots)
    for path in composes:
        found, svc = lint_compose(path)
        problems += found
        services.update(svc)
    for path in caddys:
        found, said = lint_caddy(path, services)
        problems += found
        notices += said

    return problems, len(composes) + len(caddys), notices


def main(argv: list[str]) -> int:
    problems, scanned, notices = lint(argv or ["."])
    if scanned == 0:
        print("nothing to check (no compose or Caddy files found)", file=sys.stderr)
        return 2

    for notice in notices:
        print(f"  NOT CHECKED: {notice}\n")

    if problems:
        print(f"ingress-lint: {len(problems)} violation(s) across {scanned} file(s)\n")
        for p in problems:
            print(f"  {p}\n")
        return 1

    # Never a bare "clean" while something went unchecked — that is the sentence an operator reads as "fine".
    if notices:
        print(f"ingress-lint: no violations in what ran, but {len(notices)} check(s) above did NOT run "
              f"({scanned} file(s) seen)")
        return 0

    print(f"ingress-lint: clean ({scanned} file(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
