#!/usr/bin/env bash
# Shared helper for the deploy and cleanup targets that stop a desktop app, and for deploy's own
# check that it started again — sourced, never executed.
# Expects $OS (win | mac | linux) from the calling script.
#
# A launcher's exit status does not say a process is running, so both waits below ask the process
# table instead. macOS is where that matters most: `open` on a bundle whose previous instance is
# still terminating activates the dying instance and exits 0, which installs the new build and
# leaves nothing running. The same race also surfaces as
# `_LSOpenURLsWithCompletionHandler() failed with error -600`, aborting a deploy whose app did
# start. Measured 2026-10-09 — learnings/macos-open-after-killing-an-app.md.

# True when a process with exactly this name is running.
app_process_running() {
    if [ "$OS" = "win" ]; then
        powershell.exe -Command "Get-Process '$1' -ErrorAction Stop" >/dev/null 2>&1
    else
        pgrep -x "$1" >/dev/null 2>&1
    fi
}

# Wait for a signalled app to actually exit, then SIGKILL whatever is left. Called from the mac and
# linux stop paths only — the Windows ones kill through `Stop-Process -Force` and do not wait.
# Returns non-zero only when even the SIGKILL left it running — the caller is then about to
# overwrite or remove the files of a live process, which is worth saying out loud.
wait_for_app_exit() {
    local proc="$1" label="${2:-$1}" waited=0
    while [ "$waited" -lt 10 ]; do
        app_process_running "$proc" || return 0
        sleep 1
        waited=$((waited + 1))
    done
    echo "  $label did not exit within 10s — sending SIGKILL."
    pkill -9 -x "$proc" 2>/dev/null || true
    sleep 1
    app_process_running "$proc" && return 1
    return 0
}

# Wait for a launched app to appear in the process table, then require it to still be there 2s later.
# Returns non-zero when it never appears or dies inside that window. Appearing alone proves little
# outside macOS: `Start-Process` and a backgrounded exec create the process before they return, so
# the first poll succeeds for an app that crashes a second later. Measured 2026-10-09 on Windows: an
# exe exiting ~1s after launch passed the appear-only check in 2 of 3 trials —
# learnings/windows-stop-and-relaunch-an-app.md.
wait_for_app_start() {
    local proc="$1" waited=0
    while [ "$waited" -lt 15 ]; do
        if app_process_running "$proc"; then
            sleep 2
            app_process_running "$proc"
            return
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}
