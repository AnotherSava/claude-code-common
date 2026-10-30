#!/usr/bin/env bash
# Where a publish run logs, how it marks its end and how it prints its result lines — sourced by
# publish-ssh-compose.sh, which writes them, and by await-publish.sh, which waits on and reports them. Sourced, never
# executed. Both sides read these definitions so a change to any of them reaches the writer and the reader together;
# a reader left on an old end line would poll until its deadline and report a finished publish as never having
# finished, and one left on an old headline would report the run with its result lines missing.

# The log of the latest run of the repo rooted at $1, overwritten each run (tmp/ is in the global excludes).
publish_log_path() { printf '%s/tmp/publish.log\n' "$1"; }

# The last line of every run, carrying its exit status $1.
publish_exit_line() { printf 'PUBLISH-EXIT=%s\n' "$1"; }

# The status from the last end line in log $1, or nothing while the run is still in progress.
publish_exit_status() { sed -n 's/^PUBLISH-EXIT=\([0-9]*\)$/\1/p' "$1" | tail -1; }

# The run's outcome headline, "PUBLISH <outcome>", and an error line. publish_summary picks exactly these out of log
# $1 for the waiter to show, so the writer prints them only through these two helpers.
publish_headline() { printf 'PUBLISH %s\n' "$*"; }
publish_error() { printf 'ERROR: %s\n' "$*"; }
publish_summary() { grep -E '^(PUBLISH |ERROR: )' "$1"; }
