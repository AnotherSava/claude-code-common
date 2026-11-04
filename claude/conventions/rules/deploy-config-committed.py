"""A project's deploy settings are committed, and nothing per machine stands between `deploy` and them.

The `deploy` shell function runs the deploy skill's `run.sh`, which reads DEPLOY_TYPE from
`config/deploy.env` and calls the target that type names. A setting the project decides is therefore
read from one committed file on every clone, and a file left untracked on one machine is a setting the
other machine silently lacks: the shape that left one Tauri project rendering its secrets from Doppler
on one box and shipping a plaintext config on the other.

Checked, for a repo that has a `config/deploy.env`:

  committed    git tracks it or would commit it, so the other clone reads the same settings
  typed        it names a DEPLOY_TYPE `deploy` dispatches: one of the TARGETS in shared/deploy_config.py
  no wrapper   no `scripts/deploy.sh` sits beside it. `run.sh` no longer calls one, so a wrapper still
               holding a step of its own does nothing, and that step belongs in `config/deploy.env`
  local apart  `config/deploy.local.env`, the per-machine overrides, is neither tracked nor committable

A repo with no `config/deploy.env` has no deploy configured, which is an answer rather than a finding.
"""

from __future__ import annotations

import os
import sys

import _git

# The deploy settings reader and the DEPLOY_TYPE list live with the deploy scripts, which read them too.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
                                "skills", "shared"))
import deploy_config  # noqa: E402

CONFIG = "config/deploy.env"
LOCAL = "config/deploy.local.env"
WRAPPER = "scripts/deploy.sh"


def committable(root: str, path: str) -> bool:
    """Whether a commit made now would carry `path`: tracked already, or untracked and not ignored.

    The set a commit carries rather than the index alone, because `/adopt` runs the gate before it
    commits, when the settings file it just moved into place is still untracked.
    """
    done = _git.git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", path)
    _git.answered(done, "ls-files")
    if done.returncode != 0:
        raise _git.GitRefused(f"git ls-files exited {done.returncode} rather than answering")
    return bool(done.stdout.strip())


def check(root: str) -> list[str]:
    """One line per way this repo's deploy settings fall short of being one committed file."""
    if not os.path.isfile(os.path.join(root, CONFIG)):
        return []
    violations: list[str] = []
    if not committable(root, CONFIG):
        violations.append(f"{CONFIG} is ignored, so the other clone deploys without these settings — remove the rule hiding it "
                          f"(`git check-ignore -v {CONFIG}` names it) and commit the file")
    typed = deploy_config.value_in(os.path.join(root, CONFIG), "DEPLOY_TYPE")
    known = ", ".join(deploy_config.TARGETS)
    if not typed:
        violations.append(f"{CONFIG} names no DEPLOY_TYPE, so `deploy` refuses to run — set it to one of {known}")
    elif typed not in deploy_config.TARGETS:
        violations.append(f"{CONFIG} names DEPLOY_TYPE={typed}, which `deploy` refuses — set it to one of {known}")
    if os.path.exists(os.path.join(root, WRAPPER)):
        violations.append(f"{WRAPPER} exists and `deploy` no longer runs it — move any step it holds into {CONFIG}, then delete it")
    if committable(root, LOCAL):
        violations.append(f"{LOCAL} would be committed, and it holds this machine's overrides — it belongs ignored, "
                          f"in the global excludes; untrack it with `git rm --cached {LOCAL}` if it is tracked")
    return violations
