#!/bin/bash
# Waits for a script handed to the user to finish, then prints how it ended. An agent starts this as a background
# command right before handing over `! bash <script>`: the user's run gives the agent no turn, but this command
# exiting does, so the result is read and reported without the user having to say "done".
#
# The handed-over script must log to <log> and write `HANDOFF-EXIT=<status>` as its last line, which it does with
# two lines at its top:
#   exec > >(tee "<log>") 2>&1
#   trap 'echo "HANDOFF-EXIT=$?"' EXIT
# A run counts once <log> is newer than the marker this script touches at start and carries that line, so a log
# left by an earlier run never passes for this one. Exits with the script's own status, or 124 after the timeout.
# The same shape as the publish skill's await-publish.sh, which waits on publish's own end line.
#   usage: await-handoff.sh <log> [timeout-seconds]   (default 3600)
set -uo pipefail

LOG="${1:?usage: await-handoff.sh <log> [timeout-seconds]}"
TIMEOUT="${2:-3600}"
DEADLINE=$(($(date +%s) + TIMEOUT))
# A marker rather than `date -r "$LOG"`, which not every BSD date accepts. One per process: `-nt` is true against a
# missing file, so a marker shared with another waiter and deleted by its trap would let a stale log through.
MARKER="$(dirname "$LOG")/.await-handoff-start.$$"
mkdir -p "$(dirname "$LOG")" && touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if [ "$LOG" -nt "$MARKER" ]; then
        STATUS=$(sed -n 's/^HANDOFF-EXIT=\([0-9]*\)$/\1/p' "$LOG" | tail -1)
        if [ -n "$STATUS" ]; then
            tail -5 "$LOG"
            echo "handed-over script exited $STATUS — full output in $LOG"
            exit "$STATUS"
        fi
    fi
    sleep 3
done
echo "no run finished within ${TIMEOUT}s — $LOG never received a HANDOFF-EXIT line"
exit 124
