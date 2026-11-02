#!/usr/bin/env bash
# The wait loop behind every "the user runs it, the agent learns when it ends" handover — sourced by
# await-handoff.sh and by the publish skill's await-publish.sh, never executed. An agent starts one of those as a
# background command right before handing the user a command: the user's run gives the agent no turn, but the waiter
# exiting does, so the result is read and reported without the user having to say "done".

# end_line_status <prefix> <log>
# The status from the last `<prefix>=<status>` line in <log>, or nothing while the run is still in progress. The match
# is anchored, so a writer has to start its end line with a newline to keep it off output that ended without one.
end_line_status() { sed -n "s/^$1=\([0-9]*\)\$/\1/p" "$2" | tail -1; }

# await_end_line <log> <timeout-seconds> <end-prefix> <summary-fn> <label>
# Waits until <log> is newer than a marker touched at the start and carries an `<end-prefix>=<status>` line, then
# prints <summary-fn> <log> and a closing line and exits with that status, or with 124 after the timeout. The
# marker is what keeps a log left by an earlier run from passing for this one.
await_end_line() {
    local log="$1" timeout="$2" prefix="$3" summary_fn="$4" label="$5" deadline status
    deadline=$(($(date +%s) + timeout))
    # A marker rather than `date -r "$log"`, which not every BSD date accepts. One per process: `-nt` is true against
    # a missing file, so a marker shared with another waiter and deleted by its trap would let a stale log through.
    # Global, since the EXIT trap runs after this function's locals are gone.
    AWAIT_MARKER="$(dirname "$log")/.await-start.$$"
    mkdir -p "$(dirname "$log")" && touch "$AWAIT_MARKER"
    trap 'rm -f "$AWAIT_MARKER"' EXIT

    while [ "$(date +%s)" -lt "$deadline" ]; do
        if [ "$log" -nt "$AWAIT_MARKER" ]; then
            status=$(end_line_status "$prefix" "$log")
            if [ -n "$status" ]; then
                "$summary_fn" "$log"
                echo "$label exited $status — full output in $log"
                exit "$status"
            fi
        fi
        sleep 3
    done
    echo "no $label finished within ${timeout}s — $log never received its end line"
    exit 124
}
