#!/bin/sh
# Opens the Windows box's Claude session for one project in this terminal, and opens it again when
# the transport under it dies.
#
# Usage: attach.sh <project> [<start-token>]
#
# The start token is a file pick-session.py writes just before it opens the tab, and the first pass
# deletes it. It is how this script tells a person's pick from agterm restoring the tab, which runs
# the same command line again: by then the token it names is gone. A pick creates the session even
# where its last agent ended on purpose; a restore and every reconnect leave such a session ended
# (wsl/cc-session.sh, on its `start` and `resume`).
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

# The token is consumed before anything here can exit, so no early failure leaves it for a restore
# to find and run as a pick.
mode=resume
if [ -n "${2:-}" ] && [ -f "$2" ]; then
    rm -f "$2"
    mode=start
fi

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

project=${1:-}
if [ -z "$project" ]; then
    echo "usage: attach.sh <project> [<start-token>]" >&2
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
MAX_WAIT=60     # the backoff stops doubling here; an attempt is one ssh connect, cheap even for days

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
# live output from the session. Focus reporting is left on the same way, and the terminal then sends
# a focus-in sequence on every return to the tab, which the tty echoes as `^[[I` under the status.
plain_screen() {
    printf '\033[?1049l\033[?1004l'
}

# The reconnect status is one block redrawn in place on every attempt, its last line a countdown, so
# what matters is always the bottom of the tab rather than scrolled away under repeats of itself.
# status_rows is how many rows the header and detail took on screen, for the cursor to climb back
# over; 0 means nothing is drawn, and anything printed after a drawing must call status_end first so
# the next drawing cannot overwrite it.
status_rows=0
if [ -t 2 ]; then
    c_head=$(printf '\033[33m') c_dim=$(printf '\033[2m') c_off=$(printf '\033[0m')
else
    c_head= c_dim= c_off=
fi

rows_of() {  # <text> — the rows it fills at the tab's current width
    n=${#1}
    [ "$n" -gt 0 ] || n=1
    echo $(( (n + cols - 1) / cols ))
}

status_draw() {  # <header> <detail, possibly several lines or empty>
    # tput finds the terminal through stderr, the only one of its outputs a command substitution
    # leaves on the tab; pointed anywhere else it answers terminfo's 80 whatever the width.
    cols=$(tput cols 2>/dev/tty) || cols=80
    [ "$status_rows" -eq 0 ] || printf '\r\033[%dA\033[J' "$status_rows" >&2
    printf '%s%s%s\n' "$c_head" "$1" "$c_off" >&2
    status_rows=$(rows_of "$1")
    if [ -n "$2" ]; then
        while IFS= read -r line; do
            printf '%s  %s%s\n' "$c_dim" "$line" "$c_off" >&2
            status_rows=$((status_rows + $(rows_of "  $line")))
        done <<EOF
$2
EOF
    fi
}

status_end() {
    [ "$status_rows" -eq 0 ] || printf '\n' >&2
    status_rows=0
}

# What the check wrote to stderr that nothing has shown yet. A retried failure shows it inside the
# status block instead, so this runs only where the loop goes on to attach or stops, which the
# `case $status` below decides and nothing else re-derives.
flush_check_err() {
    status_end
    [ -z "$check_err" ] || printf '%s\n' "$check_err" >&2
    check_err=
}

# Everything typed while there was nothing to type into. The tty queued it and the next attempt's
# raw mode does not discard it, so it would be delivered into the agent on reconnect — into a
# session that, on 2026-10-03, had been parked on an unanswered question since 08:24. There is no
# POSIX shell verb for TCIFLUSH; a failure here only means those keystrokes arrive, which is what
# happens today, so it is tolerated rather than fatal. It runs before the next check, so keys typed
# while that check waits out its connect timeout are not dropped: echo is off then, and they reach
# the agent unseen if the attach that follows succeeds.
drop_typed_input() {
    /usr/bin/python3 -c 'import sys, termios; termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)' 2>/dev/null || true
}

# ServerAlive* is a deadline, not a keepalive. Nothing is sent while the Mac is asleep; what they
# buy is that a transport which died during that sleep is noticed within 75s of waking instead of
# hours later, the probe deadline being absolute against a clock that ran through the suspend.
# They are set here rather than in ~/.ssh/config, which is per-machine and unversioned while this
# file is shared by both checkouts, and because tearing a connection down after 75s of silence is
# right for one a person is watching and wrong for every other ssh to this host.
ssh_opts="-o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o ConnectTimeout=10"

# The checkout is the same repo on both machines, so the far side runs its own copy of this
# script's sibling. Keeping the remote command to bare tokens is what makes it survive cmd.exe,
# which is the Windows sshd's default shell.
# The `mac` is the origin: this script only ever runs on the Mac, so it is the one place that
# knows the person is not at the Windows keyboard. `claude` over there reads it back off the
# client and attaches alongside rather than refusing.
cc_session="wsl -d $WSL_DISTRO -- $REPO_WSL_PATH/claude/remote-session/wsl/cc-session.sh $project mac"

# Tints this tab's agterm sidebar row so a remote session reads as one at a glance. The tab tints
# itself because every route to it runs this script, pick-session.py and the dashboard's attach
# alike; the ⇄ badge stays in the title for terminals with no row colours, agwinterm among them.
# No colour, or neither part on, clears instead of skipping, so a restored tab loses an old tint.
# A failure costs only the colour, so it is reported and the attach goes on.
if [ -n "${AGTERM_SESSION_ID:-}" ]; then
    tint_parts=
    tint_part() {  # <key> <part> <value>
        case $3 in
            true) tint_parts=${tint_parts:+$tint_parts,}$2 ;;
            false) ;;
            *) echo "attach: $1 must be true or false, not '$3'" >&2 ;;
        esac
    }
    tint_part REMOTE_TINT_ICON icon "${REMOTE_TINT_ICON:-false}"
    tint_part REMOTE_TINT_NAME name "${REMOTE_TINT_NAME:-false}"
    tint=${REMOTE_TINT_COLOUR:-clear}
    [ -n "$tint_parts" ] || tint=clear
    # agterm refuses a placement beside `clear`.
    [ "$tint" = clear ] && tint_parts=
    agtermctl session tint "$tint" ${tint_parts:+--on "$tint_parts"} --target "$AGTERM_SESSION_ID" ${AGTERM_SOCKET:+--socket "$AGTERM_SOCKET"} >/dev/null \
        || echo "attach: could not tint this tab $tint" >&2

    # cmd+d in this tab opens a shell on the same machine in the project's directory, rather than a
    # local one. agterm runs the line as argv with no shell, which the project check above keeps safe;
    # the split's ssh ends with the split, so it gets the attach's deadline but not its reconnect loop.
    # cc-session.sh opens that shell, so a directory that is gone is refused as it is for the session;
    # `wsl --cd` would open the shell in `/` instead and still exit 0.
    # An agterm too old for the command only loses that, so it is reported and the attach goes on.
    agtermctl session split command "/usr/bin/ssh -t $ssh_opts $REMOTE_USER@$REMOTE_HOST $cc_session resume shell" \
        --target "$AGTERM_SESSION_ID" ${AGTERM_SOCKET:+--socket "$AGTERM_SOCKET"} >/dev/null \
        || echo "attach: could not point this tab's cmd+d at $REMOTE_HOST" >&2
fi

stop=0
trap 'stop=1' INT TERM
exec 3>&1  # the check's stdout, kept on the terminal while its stderr is captured

# No lost connection is retried until this tab has held a live session (a holder that is down is,
# from the first pass, since it clears by itself). After a pick, the picker's own inventory
# ssh reached that machine seconds ago, so a failure here is news and is reported rather than
# retried. After an agterm restore no picker ran and the last contact may be days old, so the
# failure is not news there; the tab still waits for cmd+shift+r, because not retrying is also
# what keeps a refused key, a changed host key and a renamed WSL distro from becoming a loop, all
# three of which exit 255 exactly as a dropped link does — `wsl -d <missing>` was measured at 255
# through this same chain, so 255 is not ssh's own code alone.
settled=0
fails=0
wait_secs=$FIRST_WAIT

while [ "$stop" -eq 0 ]; do
    # Every attempt creates the session when it is not running, reconnects included, so a tab that
    # outlives a reboot of the far machine comes back resuming the directory's conversation. Only
    # a session whose agent exited 0 stays ended on a resume; cc-session.sh then exits 5 and the
    # tab closes below.
    remote="$cc_session $mode"

    # Asked first without a terminal, because the Windows sshd returns 0 for every remote exit once
    # ssh allocates one (cc-session.sh's header has the measurement). This run's status is the only
    # place a refusal can be read; the attach below can only say whether the transport held.
    status=0
    # -T for the same reason, against a config that asks for a terminal; the ServerAlive deadline so a
    # transport that dies mid-check is noticed as it would be under the attach.
    # Its stderr is captured so that a failure the loop will retry shows inside the status block
    # instead of piling up above it; flush_check_err prints it everywhere else.
    check_err=$(ssh -n -T $ssh_opts "$REMOTE_USER@$REMOTE_HOST" "$remote check" 2>&1 1>&3) || status=$?
    # Echo has been off since the countdown, so keys typed while this check waited out its connect
    # timeout could not move the cursor off the block. It comes back on before the attach, whose ssh
    # restores whatever it found on the way out.
    stty echo 2>/dev/null || true

    # A pick stays a start until a pass gets as far as the attach: one that waited out a down holder
    # has still created nothing, so the person's pick must not turn into a resume behind it.
    if [ "$status" -eq 0 ]; then
        flush_check_err
        began=$(date +%s)
        ssh -t $ssh_opts "$REMOTE_USER@$REMOTE_HOST" "$remote" || status=$?
        [ $(( $(date +%s) - began )) -lt "$LIVE_SECS" ] || { settled=1; fails=0; wait_secs=$FIRST_WAIT; }
        plain_screen
        mode=resume
    fi

    case $status in
        0|5)
            # 0 is a detach, or a session that ended under the client — both of which mean stop,
            # and both measured on the far side's tmux 3.4 rather than read from its source, since
            # the whole loop turns on them: a client detached with `detach-client`, which is the
            # same MSG_DETACH that Ctrl-b d sends, exits 0, and so does one whose session is killed
            # under it. The attach's other failures reach here as 0 too, the terminal having eaten
            # their status, so they close the tab the same way. 5 is the check finding the session
            # ended on purpose while this tab could not see it. After a 0 from an attach that
            # reached tmux, remote_session_attach has already blanked the title on its way out; a 5
            # skipped the attach and leaves the title as it was, which on a first pass is whatever
            # agterm or the shell set.
            # The tab closes with it, so a session the far side ended (the agent exiting, or a
            # `tmux kill-session` there) leaves no press-any-key prompt behind here. The close
            # kills this script before agtermctl returns — measured 2026-10-15 — so nothing placed
            # after it runs inside agterm; the exit only covers a run outside agterm, where there
            # is no session to close.
            flush_check_err
            [ -z "${AGTERM_SESSION_ID:-}" ] || agtermctl session close --target "$AGTERM_SESSION_ID" >/dev/null 2>&1 || true
            exit 0
            ;;
        4)
            # The one refusal that clears without a person, so it is retried from the first pass.
            ;;
        255)
            if [ "$settled" -eq 0 ]; then
                flush_check_err
                tab_title "not connected"
                printf '\nattach: could not open %s on %s — the lines above say why. Close this tab,\n' "$project" "$REMOTE_HOST" >&2
                printf 'attach: then cmd+shift+r to try again.\n' >&2
                exit "$status"
            fi
            ;;
        *)
            flush_check_err
            tab_title "refused"
            printf '\nattach: the far side refused with status %s — the lines above say why. Close\n' "$status" >&2
            printf 'attach: this tab, then cmd+shift+r.\n' >&2
            exit "$status"
            ;;
    esac

    fails=$((fails + 1))
    [ "$fails" -gt 1 ] || since=$(date +%H:%M)
    tab_title "reconnecting"
    where="$REMOTE_SESSION_BADGE $project @ $REMOTE_HOST"
    if [ "$status" -eq 4 ]; then
        status_draw "$where — its session holder is down" "$check_err"
    elif [ "$fails" -eq 1 ]; then
        status_draw "$where is unreachable" "$check_err"
    else
        # A machine that is away and a fault that will never clear (a changed host key, a renamed
        # WSL distro) both exit 255, so the header claims neither; the ssh line under it tells them
        # apart.
        status_draw "$where — unreachable since $since" "$check_err"
    fi

    # Ticked against a wall-clock deadline, so Ctrl-C lands within a second and a wait straddling a
    # system sleep ends on waking, however Darwin treats a relative timer. Echo is off from here
    # through the next check, so a key pressed now cannot push the block off the rows the next
    # drawing climbs back over. A Ctrl-C interrupts the sleep, which then fails, so its status is
    # dropped or `set -e` would end the script before the loop reads stop.
    deadline=$(( $(date +%s) + wait_secs ))
    stty -echo 2>/dev/null || true
    while [ "$stop" -eq 0 ]; do
        left=$(( deadline - $(date +%s) ))
        [ "$left" -gt 0 ] || break
        printf '\r\033[K  attempt %d in %ds · Ctrl-C to stop' $((fails + 1)) "$left" >&2
        sleep 1 || true
    done
    # The attempt itself can take ConnectTimeout, which a countdown frozen at 1s would misreport.
    [ "$stop" -ne 0 ] || printf '\r\033[K  attempt %d…' $((fails + 1)) >&2
    wait_secs=$((wait_secs * 2))
    [ "$wait_secs" -le "$MAX_WAIT" ] || wait_secs=$MAX_WAIT
    drop_typed_input
done

# The countdown is no longer true once stopped, so it goes rather than stays above the notice.
stty echo 2>/dev/null || true
[ "$status_rows" -eq 0 ] || printf '\r\033[K' >&2
tab_title "stopped"
printf '\nattach: stopped reconnecting. Close this tab, then cmd+shift+r to open %s again.\n' "$project" >&2
exit 130
