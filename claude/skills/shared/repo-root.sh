#!/usr/bin/env bash
# Shared helper for the deploy, publish and wrap-up scripts — sourced, never executed.
#
# resolve_repo_dir prints the project root that owns one of the anchor paths named in its arguments, so a script
# works when invoked from a subdirectory (e.g. `web/`) and not only from the root. It prints the nearest ancestor
# of $PWD, inclusive, that holds any one of them; failing that the git top-level; failing that $PWD.
#
# The anchor is an argument rather than a constant because each caller owns a different file and must not resolve
# against another's. A publish target anchored on config/deploy.env would silently pick a repo that has no publish
# target at all, and a deploy target anchored on publish.env the reverse — so pass the file the caller itself goes
# on to read. A caller that cares about several, as wrap-up's ship_wrappers.sh does, passes all of them and takes
# the first root holding any; order within one directory level does not matter, since the answer is the directory.
#
# Why the walk exists rather than a bare `git rev-parse`: a target invoked as `bash scripts/deploy.sh` from a
# subdirectory set REPO_DIR to $PWD, read a nonexistent web/config/deploy.env, and fell back to a default port and
# directory. Observed 2026-07-12 — a dev server meant for port 3939 came up on 3000. The git top-level is the
# fallback rather than the primary because a project may sit below the root of the repository that contains it.
#
# Changing this changes every deploy and publish on the machine; claude/tests/repo-root.py pins the cases.
resolve_repo_dir() {
    local d="$PWD" anchor
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        for anchor in "$@"; do
            if [ -f "$d/$anchor" ]; then
                printf '%s\n' "$d"
                return 0
            fi
        done
        d="$(dirname "$d")"
    done
    git rev-parse --show-toplevel 2>/dev/null || pwd
}
