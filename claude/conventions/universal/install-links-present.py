"""Every symlink and git setting this dotfiles repo installs is in place on this machine.

The commit gate itself depends on one of them. v9 tells every repo to run
`python3 ~/.claude/conventions/check.py .`, so adopting it made a repo's gate reach through
`~/.claude/conventions` — and nothing asserted that link at the moment the gate runs. What asserted
it was `check-install.py` at session start, which had already run: a link arriving in a `git pull`
mid-session is missing and silent for as long as that session lasts, and the session that pulled it
is exactly the one about to commit.

Measured, 2026-09-16: the `conventions` link was in both install blocks and in neither of
`check-install.py`'s lists, so it was created on neither machine. Every documented convention
command failed on both, and the session-start check called the install clean throughout.

This is universal rather than versioned for the same reason the memory-cache link is. A version
asks *did this repo change shape*, once; this asks *is this machine wired*, and the answer changes
under a repo that never moved — a fresh machine, a moved checkout, a Git Bash `ln -s` that made a
copy. No number could be true of two machines at once. It is about no repo in particular, which is
why every repo's gate is the right place to ask it: the links are what that gate reads.

The lists and the comparison are `check-install.py`'s, imported rather than restated. Two readers of
one contract drift the day either gains a link, and this rule exists because a contract with three
copies already drifted once. A checkout without that file takes the answer away rather than passing:
the rule raises, and the checker reports it unmeasured.

What this cannot see, stated because a clean line must never stand in for an unasked question: in a
repo dialling `~/.claude/conventions/check.py`, that one link is proven by the invocation rather
than by the check — the gate line could not have run without it. Run from this checkout, where the
gate dials the path inside the repo, all of them are genuinely checked.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType

HERE = os.path.dirname(os.path.realpath(__file__))
CHECK_INSTALL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "hooks", "check-install.py")


def install_check() -> ModuleType:
    """check-install.py as a module. Importing it runs nothing — its work is behind a main guard."""
    spec = importlib.util.spec_from_file_location("conventions_install_contract", CHECK_INSTALL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"the install contract could not be loaded from {CHECK_INSTALL}, and this "
                           f"rule will not fall back to a second copy of the link list — a rule and "
                           f"the session-start check must not disagree about what is installed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"the install contract at {CHECK_INSTALL} would not import ({exc}), so what "
                           f"this machine is supposed to have was never established") from exc
    return module


INSTALL = install_check()

# The platform's own install block, named by the script that owns the contract rather than restated
# here, so the sentence a broken machine is given is the one its README actually contains.
FIX = INSTALL.repair_hint()


def check(root: str) -> list[str]:
    """Every install check that does not hold, one line each. The repo is not what this asks about.

    `root` is unused and stays in the signature because that is the rules' interface: this rule is
    the class whose answer is the same in every repo on the machine, which is the whole reason it is
    gated by no version.
    """
    if INSTALL.git_globals() is None:
        # check_all() renders this as one more failed row. A rule must not: git refusing to answer
        # is three settings unmeasured, and reporting it as a violation would invent a finding out
        # of a question nobody got to ask.
        raise RuntimeError("git would not list the global config, so whether core.hooksPath, "
                           "core.excludesFile and core.attributesFile point into this repo is unknown")
    return [f"{label} — {why}" for label, ok, why in INSTALL.check_all() if not ok]
