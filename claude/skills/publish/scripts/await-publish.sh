#!/bin/bash
# Waits for the next publish of this repo to finish, then prints how it ended. An agent starts this as a background
# command right before handing the user `! publish`; the loop itself is await_end_line in the shared
# scripts/await-end-line.sh.
#
# A run counts once the publish log carries the end line publish-ssh-compose.sh writes last; publish-log.sh defines
# both for the two scripts. Exits with the publish's own status, or 124 after the timeout.
#   usage: await-publish.sh [timeout-seconds]   (default 3600)
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../shared/repo-root.sh"
source "$(dirname "${BASH_SOURCE[0]}")/publish-log.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../../../scripts/await-end-line.sh"
REPO_DIR="$(resolve_repo_dir config/publish.env)"

publish_result_lines() { publish_summary "$1" | tail -3; }

await_end_line "$(publish_log_path "$REPO_DIR")" "${1:-3600}" publish_exit_status publish_result_lines publish
