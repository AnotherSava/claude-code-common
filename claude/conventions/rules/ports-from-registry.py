"""Every port literal in a launch-determining file is a `pinned` claim in the ports registry.

A port written into a dev script is a copy of a number the registry also holds, and it is the copy the
process reads — so the two drift with the wrong one winning. Resolving the port at launch leaves no copy
to drift, which is what lets this rule be a search for literals rather than a comparison between two
records: the absence of one *is* the evidence.

What stays is the literal that cannot be resolved at launch, and it carries its reason in the registry
instead — a number fixed by an outside party, a default compiled into a binary, a vendor's own port. The
`pinned` field is where that reason lives, and requiring it is what separates a deliberate literal from
a forgotten one. A pinned claim belonging to a *different* repo is still reported here: two repos cannot
both own a number, and the registry naming one of them is the answer.

Scope is the files that decide where a server listens, never prose. A README telling a human which URL
to open, an `.env.example` default, a test asserting a URL, a compose healthcheck on a
container-internal port — none of those can be resolved at launch and all are correct to leave. Measured
across the fleet on 2026-10-05: ten launch-path literals against 134 in prose, examples and tests, so a rule that
read everything would bury its own findings.

The scan itself is `launch_path_literals` in the ports skill, which `ports.py check --repo` also calls.
That function knows which globs count and which patterns are a port rather than a version number, and a
second copy of either here would drift from the tool the migration tells people to run.
"""

import importlib.util
import os
from typing import List

HERE = os.path.dirname(os.path.realpath(__file__))
PORTS_PY = os.path.join(os.path.dirname(os.path.dirname(HERE)), "skills", "ports", "scripts", "ports.py")


class Unanswerable(Exception):
    """The registry or a launch file could not be read, so what this repo hardcodes is unknown.

    Raised rather than returned empty for the reason every rule here raises: an unreadable registry and
    a repo with no literals produce the same empty list, and only one of them is a pass.
    """


def _ports_module():
    """The ports skill, imported from its path.

    By path rather than by name because the skill lives outside this package and is the single
    implementation of the scan — importing it is what keeps this rule and the command an engineer is
    told to run from answering differently.
    """
    if not os.path.isfile(PORTS_PY):
        raise Unanswerable(
            f"{PORTS_PY} is not there, so which ports this repo may hardcode could not be established. "
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
    """Every launch-path port literal this repo has no pinned claim for."""
    ports = _ports_module()
    try:
        registry = ports.read_registry()
    except Exception as exc:
        raise Unanswerable(f"the ports registry at {ports.REGISTRY} could not be read "
                           f"({type(exc).__name__}: {exc}), so no literal here could be judged")
    try:
        problems, _ = ports.check_repo(registry, ports.Path(root))
    except RuntimeError as exc:
        # The scanner raises on a tracked launch file it cannot read and on a git call that did not
        # answer. Both are this rule being unable to look, not a repo that holds nothing.
        raise Unanswerable(str(exc))
    return problems
