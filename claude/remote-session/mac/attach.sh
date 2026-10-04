#!/bin/sh
# Opens the Windows box's Claude session for one project in this terminal, and opens it again when
# the transport under it dies.
#
# Usage: attach.sh <project>
#
# Safe to run while a Windows terminal is attached to the same session — tmux takes both clients at
# once, which is the whole reason the design is tmux rather than `claude --bg` + `claude attach`.
# Both clients then draw at the size of whichever was used last (tmux's `window-size latest`), and a
# reconnect is another attach, so the Windows window takes this Mac's size again each time, with
# nobody here to have asked for it.
#
# Nothing keeps the connection alive, and nothing could: a sleeping laptop runs no process and sends
# no packet. What the loop adds is a deadline and another attempt. Measured 2026-10-03: the Mac
# slept on battery at 08:26:52 and neither end was asking the other for anything — `ssh -G` reported
# serveraliveinterval 0, the far side's sshd clientaliveinterval 0, the kernel's keepidle two hours
# — so three sockets sat until TCP timers reaped them between 1h15m and 6h34m later, every one of
# them while the laptop was still asleep. tmux on the far side held all three sessions and all three
# agents throughout; only the transport had died, and the tabs sat at a press-any-key prompt.
#
# This no longer `exec`s into ssh, which has one consequence worth knowing before changing it back:
# the tab's foreground process is now this shell for the tab's whole life, because agterm names a
# pane by its process group leader and for a `--command` pane that resolves to this script, never to
# its ssh child. Two readers act on that. pick-session.py matches this script's own argv, so a
# reconnect gap cannot make the chord open a second tab onto a session that is already open. And the
# Claude Code Dashboard's `terminals::agterm_facts::occupant` must read a shell running a script as
# a program rather than as an idle prompt, or `person_verdict` refuses every observation these tabs
# produce and cross-machine attention tracking stops.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

project=${1:-}
if [ -z "$project" ]; then
    echo "usage: attach.sh <project>" >&2
    exit 2
fi

# The project name is data travelling through the Windows sshd's cmd.exe, and no quoting makes data
# safe there: `a b` arrives as `a`, silently, and the session opens on the wrong directory. Measured
# rather than assumed. So anything outside the set that survives is refused here, at the boundary,
# rather than half-working further in. pick-session.py's tab match leans on the same restriction: it
# flattens a tab's argv to words, which recovers the project only because a name cannot hold one.
case $project in
    *[!A-Za-z0-9._/-]*)
        echo "attach: '$project' has a character that does not survive the Windows shell, so it" >&2
        echo "attach: cannot be reached from here. Start it on that machine instead — 'claude' in" >&2
        echo "attach: the folder, which passes nothing through that boundary." >&2
        exit 1
        ;;
esac

# How long an attempt must last to count as having held a real session. Above ConnectTimeout, and
# far below the 75s a keepalive teardown adds to any attach that was actually up, so the two cannot
# be mistaken for each other.
LIVE_SECS=25
FIRST_WAIT=5    # seconds before the first retry
MAX_WAIT=300    # the backoff stops doubling here; the far machine can be away for days
SLICE=5         # the wait is counted in these, so Ctrl-C lands within one of them
NOISY_AFTER=5   # consecutive failures before the message stops calling it a lost connection

# The tab's title is the far machine's, forwarded by tmux (see remote_session_attach in lib.sh). A
# dead transport stops that forwarding and leaves the last status sitting on the tab — a question
# nobody can answer through it any more. What is written here keeps the badge, which is still true,
# and drops the status glyph, which is not: the dashboard's `terminal_title::parse_title` wants one
# of its own glyphs after the badge, so this names no row, and leaving the tab can no longer mark
# the other machine's unread answer as read.
tab_title() {
    printf '\033]0;%s %s · %s\007' "$REMOTE_SESSION_BADGE" "$project" "$1"
}

# ssh restores the termios settings it changed but never leaves tmux's alternate screen, so without
# this the tab keeps the agent's last frame and every line below lands inside it, where it reads as
# live output from the session.
plain_screen() {
    printf '\033[?1049l'
}

# Everything typed while there was nothing to type into. The tty queued it and the next attempt's
# raw mode does not discard it, so it would be delivered into the agent on reconnect — into a
# session that, on 2026-10-03, had been parked on an unanswered question since 08:24. There is no
# POSIX shell verb for TCIFLUSH; a failure here only means those keystrokes arrive, which is what
# happens today, so it is tolerated rather than fatal.
drop_typed_input() {
    /usr/bin/python3 -c 'import sys, termios; termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)' 2>/dev/null || true
}

stop=0
trap 'stop=1' INT TERM

# Nothing is retried until this tab has held a live session. Before that, the picker's own inventory
# ssh reached that machine seconds ago, so a failure here is news and is reported rather than
# retried; it is also what keeps a refused key, a changed host key and a renamed WSL distro from
# becoming a loop, all three of which exit 255 exactly as a dropped link does — `wsl -d <missing>`
# was measured at 255 through this same chain, so 255 is not ssh's own code alone.
settled=0
fails=0
wait_secs=$FIRST_WAIT

while [ "$stop" -eq 0 ]; do
    if [ "$settled" -eq 0 ]; then mode=create; else mode=reattach; fi

    # The checkout is the same repo on both machines, so the far side runs its own copy of this
    # script's sibling. Keeping the remote command to bare tokens is what makes it survive cmd.exe,
    # which is the Windows sshd's default shell.
    # The trailing `mac` is the origin: this script only ever runs on the Mac, so it is the one place
    # that knows the person is not at the Windows keyboard. `claude` over there reads it back off the
    # client and attaches alongside rather than refusing.
    # ServerAlive* is a deadline, not a keepalive. Nothing is sent while the Mac is asleep; what they
    # buy is that a transport which died during that sleep is noticed within 75s of waking instead of
    # hours later, the probe deadline being absolute against a clock that ran through the suspend.
    # They are set here rather than in ~/.ssh/config, which is per-machine and unversioned while this
    # file is shared by both checkouts, and because tearing a connection down after 75s of silence is
    # right for one a person is watching and wrong for every other ssh to this host.
    began=$(date +%s)
    status=0
    ssh -t -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o ConnectTimeout=10 \
        "$REMOTE_USER@$REMOTE_HOST" \
        "wsl -d $WSL_DISTRO -- $REPO_WSL_PATH/claude/remote-session/wsl/cc-session.sh $project mac $mode" || status=$?
    [ $(( $(date +%s) - began )) -lt "$LIVE_SECS" ] || { settled=1; fails=0; wait_secs=$FIRST_WAIT; }
    plain_screen

    case $status in
        0)
            # A detach, or a session that ended under the client. remote_session_attach already
            # blanked the title on its way out.
            exit 0
            ;;
        3)
            tab_title "session ended"
            printf '\nattach: %s is up but holds no session for %s any more, so nothing was\n' "$REMOTE_HOST" "$project" >&2
            printf 'attach: reconnected. A session that ended hours ago is worth seeing rather than\n' >&2
            printf 'attach: replacing with a fresh agent in the same directory. Close this tab, then\n' >&2
            printf 'attach: cmd+shift+r.\n' >&2
            exit 3
            ;;
        4|255)
            if [ "$settled" -eq 0 ]; then
                tab_title "not connected"
                printf '\nattach: could not open %s on %s — the lines above say why. Close this tab,\n' "$project" "$REMOTE_HOST" >&2
                printf 'attach: then cmd+shift+r to try again.\n' >&2
                exit "$status"
            fi
            ;;
        *)
            tab_title "refused"
            printf '\nattach: the far side refused with status %s — the lines above say why. Close\n' "$status" >&2
            printf 'attach: this tab, then cmd+shift+r.\n' >&2
            exit "$status"
            ;;
    esac

    fails=$((fails + 1))
    tab_title "reconnecting"
    if [ "$fails" -lt "$NOISY_AFTER" ]; then
        printf '\nattach: lost the connection to %s. Reconnecting in %ds — Ctrl-C to stop.\n' "$REMOTE_HOST" "$wait_secs" >&2
    else
        # Worded differently on purpose. A machine that is away and a fault that will never clear
        # both exit 255, and neither this script nor ssh can separate them, so after a few rounds the
        # message stops asserting which one it is and points at the only thing that can tell them
        # apart.
        printf '\nattach: %s has refused %d times in a row. If it is not simply away, the ssh lines\n' "$REMOTE_HOST" "$fails" >&2
        printf 'attach: above say why — a changed host key and a renamed WSL distro end the same way.\n' >&2
        printf 'attach: Retrying in %ds; Ctrl-C to stop.\n' "$wait_secs" >&2
    fi

    # Counted in slices so Ctrl-C lands within one of them, and so a wait straddling a system sleep
    # cannot overshoot by more than the wait itself, however Darwin treats a relative timer.
    waited=0
    while [ "$waited" -lt "$wait_secs" ] && [ "$stop" -eq 0 ]; do
        sleep "$SLICE"
        waited=$((waited + SLICE))
    done
    wait_secs=$((wait_secs * 2))
    [ "$wait_secs" -le "$MAX_WAIT" ] || wait_secs=$MAX_WAIT
    drop_typed_input
done

tab_title "stopped"
printf '\nattach: stopped reconnecting. Close this tab, then cmd+shift+r to open %s again.\n' "$project" >&2
exit 130
