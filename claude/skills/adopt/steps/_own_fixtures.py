"""The one directory every step that walks a repo has to refuse to walk: this skill's fixtures.

Four steps enumerate their subject by walking the tree — the three Node ones and the compose-name
one — and the dotfiles repo is itself in the fleet, so each of them eventually runs against the
checkout holding `steps/fixtures/`. Those trees are deliberately broken: a manifest with no
`engines`, a `.gitignore` duplicating the global file, a compose file written to be unparseable.
A step that reads them reports its own test data as findings about the repo, and the damage is
not only noise. Measured before this module existed: `verify` for the Node steps listed nine
fixture manifests and could never return 0 here, so those steps were unrecordable in this repo;
and the gitignore-scope step's `probe` exited 0 on a list where one real finding sat among five
fixture ones, which is a dry run that reads plausible and gets approved.

The test is identity, not name. Skipping any directory called `fixtures` would also skip a real
`tests/fixtures/` that a project genuinely maintains, and this hazard belongs to exactly one
directory on disk. Comparing resolved paths also survives the `~/.claude/skills/` symlink these
steps are normally invoked through, and it cannot fire inside a scratch copy of a fixture tree —
there the fixture *is* the repo under test, and every step must read it in full.
"""

import os

# <repo>/claude/skills/adopt/steps/_own_fixtures.py -> <repo>/claude/skills/adopt/steps/fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures")


def is_own_fixtures(path: str) -> bool:
    """Is this directory the adoption steps' own fixture tree, however it was reached."""
    try:
        return os.path.realpath(path) == os.path.realpath(FIXTURES_DIR)
    except OSError:
        return False


def prune(base: str, dirs: list[str]) -> list[str]:
    """The `os.walk` child list with this skill's fixture tree removed, for the caller to assign."""
    return [name for name in dirs if not is_own_fixtures(os.path.join(base, name))]


def is_beneath(path: str) -> bool:
    """Does this path sit anywhere inside the fixture tree, at any depth.

    What `prune` cannot answer for a caller that never walks. A list of paths from `git ls-files`
    arrives already flattened, so each one is tested by climbing its own parents rather than by
    having been reached through the directory that would have been pruned.
    """
    current = os.path.dirname(os.path.abspath(path))
    while True:
        if is_own_fixtures(current):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent
