"""Every port this repo owns comes from the ports registry at launch.

A port written into a dev script is a copy of a number the registry also holds, and it is the copy the
process reads — so the two drift with the wrong one winning. Resolving the port at launch leaves no copy
to drift, which is what lets this rule read the repo rather than compare two records.

Two halves, because the absence of a literal proves only half of it. A dev script with no `-p` and no
resolver is not resolving the port: it takes its framework's default and drifts upward on a collision,
which is worse than the literal, since then no file names the port at all. Measured 2026-10-05, printlab
and what-is-next both reported zero literals in exactly that state. So the second half asks the registry
which unpinned ports it assigns this repo, and requires a launch-determining file that asks for each — the
same files the literal scan reads, so a doc sentence naming the tool is not evidence of a resolver.

What stays is the literal that cannot be resolved at launch, and it carries its reason in the registry
instead — a number fixed by an outside party, a default compiled into a binary, a vendor's own port, or a
literal in a file no launch path ever runs, such as a recipe a person follows by hand. The
`pinned` field is where that reason lives, and requiring it is what separates a deliberate literal from
a forgotten one. A pinned claim belonging to a *different* repo is still reported here: two repos cannot
both own a number, and the registry naming one of them is the answer.

Scope is the files that decide where a server listens, never prose. A README telling a human which URL
to open, an `.env.example` default, a test asserting a URL, a compose healthcheck on a
container-internal port — none of those can be resolved at launch and all are correct to leave. Measured
across the fleet on 2026-10-05: ten launch-path literals against 134 in prose, examples and tests, so
a rule that read everything would bury its own findings.

Both halves are `check_repo` in the ports skill, which `ports.py check --repo` also calls. That function
knows which globs count, which patterns are a port rather than a version number, and which claims are
exempt, and a second copy of any of it here would drift from the tool the migration tells people to run.
"""

import importlib.util
import os
from typing import List

HERE = os.path.dirname(os.path.realpath(__file__))
PORTS_PY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "skills", "ports", "scripts", "ports.py")


class Unanswerable(Exception):
    """The registry or a launch file could not be read, so where this repo's ports come from is unknown.

    Raised rather than returned empty for the reason every rule here raises: an unreadable registry and
    a conforming repo produce the same empty list, and only one of them is a pass.
    """


def _ports_module():
    """The ports skill, imported from its path.

    By path rather than by name because the skill lives outside this package and is the single
    implementation of the check — importing it is what keeps this rule and the command an engineer is
    told to run from answering differently.
    """
    if not os.path.isfile(PORTS_PY):
        raise Unanswerable(
            f"{PORTS_PY} is not there, so where this repo's ports come from could not be established. "
            f"That file is part of the claude dotfiles; check the ~/.claude symlinks are in place."
        )
    spec = importlib.util.spec_from_file_location("ports_skill_rule", PORTS_PY)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # an import error here says nothing about the repo being checked
        raise Unanswerable(f"{PORTS_PY} would not load ({type(exc).__name__}: {exc}), so nothing was checked")
    return module


def check(root: str) -> List[str]:
    """Every port this repo does not get from the registry: an unpinned literal, or a claim nothing
    asks for."""
    ports = _ports_module()
    try:
        registry = ports.read_registry()
    except Exception as exc:
        raise Unanswerable(f"the ports registry at {ports.REGISTRY} could not be read "
                           f"({type(exc).__name__}: {exc}), so nothing here could be judged")
    try:
        problems, _ = ports.check_repo(registry, ports.Path(root))
    except RuntimeError as exc:
        # The scanner raises on a launch file it cannot read and on a git call that did not answer.
        # Both are this rule being unable to look, not a repo that holds nothing.
        raise Unanswerable(str(exc))
    return problems
