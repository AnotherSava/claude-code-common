#!/usr/bin/env bash
# What `deploy` runs, in every project and on every machine: read DEPLOY_TYPE from the project's committed
# config/deploy.env and hand the arguments to the target script that type names. A project has no wrapper of its
# own, so nothing per machine has to be generated, kept in step or restored after a skill run.
#
# A repo below convention 017 may still call its target through a per-machine scripts/deploy.sh holding steps
# of its own, so that wrapper keeps running there until /adopt moves those steps into config/deploy.env. The
# adopted number decides, read from the repo's committed .claude/conventions record; at 017 and above a leftover
# wrapper is ignored here and reported by the deploy-config-committed rule. The types and the script each one
# runs are listed in shared/deploy_config.py, which the rule reads too.
set -uo pipefail

SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"
REPO="$DEPLOY_REPO_DIR"

if [ ! -f "$REPO/config/deploy.env" ]; then
    echo "deploy: no config/deploy.env in $REPO or above it, so this project has no deploy configured. Run /deploy to set it up."
    exit 1
fi

# The engine answers, since it owns the record format: exit 1 for a repo below 017 and for a fork that declined
# it, both of which keep their wrapper, and 0 for an adopted repo or one the conventions do not govern.
"$DEPLOY_PY" "$SKILLS/../conventions/engine.py" behind "$REPO" 17 >/dev/null
case $? in
    0) ;;
    1) if [ -f "$REPO/scripts/deploy.sh" ]; then cd "$REPO" && exec bash scripts/deploy.sh "$@"; fi ;;
    *) echo "deploy: the conventions engine could not read $REPO/.claude/conventions:"
       "$DEPLOY_PY" "$SKILLS/../conventions/engine.py" behind "$REPO" 17
       exit 1 ;;
esac

type="$(deploy_get DEPLOY_TYPE)"
if [ -z "$type" ]; then
    echo "deploy: config/deploy.env names no DEPLOY_TYPE. Run /deploy to set it."
    exit 1
fi
if ! target="$("$DEPLOY_PY" "$DEPLOY_CONFIG_PY" target "$type")"; then
    echo "deploy: config/deploy.env names DEPLOY_TYPE=$type, which no target script handles ($("$DEPLOY_PY" "$DEPLOY_CONFIG_PY" types | tr '\n' ' ' | sed 's/ $//; s/ /, /g'))."
    exit 1
fi
exec bash "$SKILLS/deploy/scripts/$target" "$@"
