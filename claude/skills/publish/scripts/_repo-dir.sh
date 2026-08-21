#!/usr/bin/env bash
# Shared helper for the publish skill's target scripts — sourced, never executed.
#
# resolve_repo_dir: print the repo root that owns config/publish.env, so a publish target works when invoked from a
# subdirectory (e.g. `web/`), not only the repo root. It prints the nearest ancestor of $PWD (inclusive) that
# contains config/publish.env; failing that, the git top-level; failing that, $PWD.
#
# Anchored on publish.env rather than deploy.env on purpose: a project may have one verb wired and not the other,
# and anchoring on the wrong file would silently resolve to a repo that has no publish target at all. The deploy
# skill carries its own copy of this for the same reason — see the note there about a dev server meant for one
# port coming up on another when REPO_DIR was taken from $PWD.
resolve_repo_dir() {
    local d="$PWD"
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        if [ -f "$d/config/publish.env" ]; then
            printf '%s\n' "$d"
            return 0
        fi
        d="$(dirname "$d")"
    done
    git rev-parse --show-toplevel 2>/dev/null || pwd
}
