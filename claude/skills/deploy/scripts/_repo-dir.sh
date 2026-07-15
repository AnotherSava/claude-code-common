#!/usr/bin/env bash
# Shared helper for the deploy skill's target scripts — sourced, never executed.
#
# resolve_repo_dir: print the repo root that owns config/deploy.env, so a deploy target works when invoked from a
# subdirectory (e.g. `web/`), not only the repo root. It prints the nearest ancestor of $PWD (inclusive) that
# contains config/deploy.env; failing that, the git top-level; failing that, $PWD.
#
# Why this exists: every target script builds its paths from REPO_DIR and reads $REPO_DIR/config/deploy.env. The
# `deploy` shell function's run_repo_script already cd's to the repo root before running scripts/deploy.sh — but a
# direct `bash scripts/deploy.sh` (or `bash ~/.claude/skills/deploy/scripts/deploy-*.sh`) from a subdir used to set
# REPO_DIR="$(pwd)", read a nonexistent web/config/deploy.env, and silently fall back to default port/dir. Anchoring
# on the config file makes both invocation paths correct. (Observed 2026-07-12: a dev server meant for port 3939
# came up on 3000 this way.)
resolve_repo_dir() {
    local d="$PWD"
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        if [ -f "$d/config/deploy.env" ]; then
            printf '%s\n' "$d"
            return 0
        fi
        d="$(dirname "$d")"
    done
    git rev-parse --show-toplevel 2>/dev/null || pwd
}
