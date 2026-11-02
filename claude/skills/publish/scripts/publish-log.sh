#!/usr/bin/env bash
# Where a publish run logs, how it marks its end and how it prints its result lines — sourced by
# publish-ssh-compose.sh, which writes them, and by await-publish.sh, which waits on and reports them. Sourced, never
# executed. Both sides read these definitions so a change to any of them reaches the writer and the reader together;
# a reader left on an old end line would poll until its deadline and report a finished publish as never having
# finished, and one left on an old headline would report the run with its result lines missing.

# The log of the latest run of the repo rooted at $1, overwritten each run (tmp/ is in the global excludes).
publish_log_path() { printf '%s/tmp/publish.log\n' "$1"; }

# The last line of every run, `$PUBLISH_END_PREFIX=<status>` with its exit status $1. The reader matches it with
# end_line_status in scripts/await-end-line.sh, which needs the leading newline to find it on a line of its own.
PUBLISH_END_PREFIX=PUBLISH-EXIT
publish_exit_line() { printf '\n%s=%s\n' "$PUBLISH_END_PREFIX" "$1"; }

# The run's outcome headline, "PUBLISH <outcome>", and an error line. publish_summary picks exactly these out of log
# $1 for the waiter to show, so the writer prints them only through these two helpers.
publish_headline() { printf 'PUBLISH %s\n' "$*"; }
publish_error() { printf 'ERROR: %s\n' "$*"; }
publish_summary() { grep -E '^(PUBLISH |ERROR: )' "$1"; }
