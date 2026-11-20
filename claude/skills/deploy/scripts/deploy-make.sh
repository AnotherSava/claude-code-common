#!/usr/bin/env bash
# DEPLOY_TYPE=make: run the project's own Makefile target, for a stack whose build and install the project
# already scripts (an Xcode app built through xcodegen, for one). Everything stack-specific stays in the Makefile;
# this only picks the target and supplies the per-machine install location.
#
# Keys:
#   MAKE_TARGET   the target to run; `deploy` when unset.
#   INSTALL_DIR   forwarded as the make variable INSTALL_DIR, placeholders expanded, only when a settings file
#                 names it. Unset, the Makefile's own default applies, since no per-OS guess fits every Makefile.
#                 Being a machine fact, it belongs in config/deploy.local.env.
#
# Arguments are passed to make after these, so `deploy VAR=value` overrides a variable for one run.
# Whether the target stops or launches an app is the Makefile's business; nothing here starts one.
#
# make's own output goes to tmp/deploy-make.log, and the terminal gets a heartbeat and a verdict instead. A
# build log runs to tens of KB, and Claude Code's `!` keeps only the first 2,000 characters of long output in
# view, so the result line at the end was the part nobody saw. The log is not tmp/deploy.log because wrap-up
# redirects this script's own output there.
set -uo pipefail

SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"

HEARTBEAT_SECONDS=20
FAILURE_TAIL_LINES=40

target="$(deploy_get MAKE_TARGET)"
args=("${target:-deploy}")
dir="$(deploy_get INSTALL_DIR)"
[ -n "$dir" ] && args+=("INSTALL_DIR=$(deploy_expand "$dir")")

mkdir -p "$DEPLOY_REPO_DIR/tmp"
log="$DEPLOY_REPO_DIR/tmp/deploy-make.log"
echo "deploy: make ${args[*]}${*:+ $*} (full output: tmp/deploy-make.log)"

start=$SECONDS
make -C "$DEPLOY_REPO_DIR" "${args[@]}" "$@" > "$log" 2>&1 &
pid=$!
# A background job in a non-interactive shell ignores SIGINT, so Ctrl-C would stop this script and leave make
# building. GNU make passes SIGTERM on to its recipe processes.
trap 'kill "$pid" 2>/dev/null; wait "$pid"; echo "deploy: interrupted, full output: tmp/deploy-make.log"; exit 130' INT TERM
next=$HEARTBEAT_SECONDS
while kill -0 "$pid" 2>/dev/null; do
    sleep 1
    if [ $((SECONDS - start)) -ge "$next" ]; then
        last="$(grep -v '^[[:space:]]*$' "$log" | tail -1 | sed 's/^[[:space:]]*//' | cut -c1-100)"
        echo "deploy: still running, $((SECONDS - start))s: $last"
        next=$((next + HEARTBEAT_SECONDS))
    fi
done
wait "$pid"
status=$?
elapsed="$(( (SECONDS - start) / 60 ))m $(( (SECONDS - start) % 60 ))s"

if [ "$status" -ne 0 ]; then
    tail -n "$FAILURE_TAIL_LINES" "$log"
    echo "deploy: FAILED (make exit $status) after $elapsed, full output: tmp/deploy-make.log"
    exit "$status"
fi
grep -v '^[[:space:]]*$' "$log" | tail -3
echo "deploy: done in $elapsed"
