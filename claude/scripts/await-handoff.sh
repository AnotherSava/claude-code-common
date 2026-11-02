#!/bin/bash
# Waits for a script handed to the user to finish, then prints how it ended. An agent starts this as a background
# command right before handing over `! bash <script>`; the loop itself is await_end_line in await-end-line.sh.
#
# The handed-over script must log to <log> and write `HANDOFF-EXIT=<status>` as its last line, which it does with
# two lines at its top:
#   exec > >(tee "<log>") 2>&1
#   trap 'printf "\nHANDOFF-EXIT=%s\n" "$?"' EXIT
# The leading newline keeps the end line off output that ended without one, where the anchored match would miss it.
# Exits with the script's own status, or 124 after the timeout.
#   usage: await-handoff.sh <log> [timeout-seconds]   (default 3600)
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/await-end-line.sh"

handoff_summary() { tail -5 "$1"; }

await_end_line "${1:?usage: await-handoff.sh <log> [timeout-seconds]}" "${2:-3600}" HANDOFF-EXIT handoff_summary "handed-over script"
