#!/bin/bash
# Waits for a script handed to the user to finish, then prints how it ended. An agent starts this as a background
# command right before handing over `! bash <script>`; the loop itself is await_end_line in await-end-line.sh.
#
# The handed-over script must log to <log> and write `HANDOFF-EXIT=<status>` as its last line, which it does with
# two lines at its top:
#   exec > >(tee "<log>") 2>&1
#   trap 'echo "HANDOFF-EXIT=$?"' EXIT
# Exits with the script's own status, or 124 after the timeout.
#   usage: await-handoff.sh <log> [timeout-seconds]   (default 3600)
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/await-end-line.sh"

handoff_exit_status() { sed -n 's/^HANDOFF-EXIT=\([0-9]*\)$/\1/p' "$1" | tail -1; }
handoff_summary() { tail -5 "$1"; }

await_end_line "${1:?usage: await-handoff.sh <log> [timeout-seconds]}" "${2:-3600}" handoff_exit_status handoff_summary "handed-over script"
