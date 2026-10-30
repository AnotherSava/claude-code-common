#!/bin/bash
# Waits for the next publish of this repo to finish, then prints how it ended. An agent starts this as a background
# command right before handing the user `! publish`: the user's run gives the agent no turn, but this command
# exiting does, so the outcome is reported without the user having to say "done".
#
# A run counts once <repo>/tmp/publish.log is newer than the marker this script touches at start and carries the
# PUBLISH-EXIT= line publish-ssh-compose.sh writes last. Exits with the publish's own status, or 124 after the timeout.
#   usage: await-publish.sh [timeout-seconds]   (default 3600)
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../shared/repo-root.sh"
REPO_DIR="$(resolve_repo_dir config/publish.env)"
LOG="$REPO_DIR/tmp/publish.log"
DEADLINE=$(($(date +%s) + ${1:-3600}))
# A marker rather than `date -r "$LOG"`, which not every BSD date accepts. One marker per process: `-nt` is true
# against a missing file, so a shared one deleted by another waiter's trap would let a stale log through.
MARKER="$REPO_DIR/tmp/.await-publish-start.$$"
mkdir -p "$REPO_DIR/tmp" && touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if [ "$LOG" -nt "$MARKER" ]; then
        STATUS=$(sed -n 's/^PUBLISH-EXIT=\([0-9]*\)$/\1/p' "$LOG" | tail -1)
        if [ -n "$STATUS" ]; then
            grep -E '^(PUBLISH (OK|FAILED)|ERROR)' "$LOG" | tail -3
            echo "publish exited $STATUS — full output in $LOG"
            exit "$STATUS"
        fi
    fi
    sleep 5
done
echo "no publish finished within ${1:-3600}s — $LOG was not written by a completed run"
exit 124
