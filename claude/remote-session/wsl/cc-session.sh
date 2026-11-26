#!/bin/sh
# Attaches the tmux session for one project, creating it first if it is not running yet, or with
# `detach` only creates it.
#
# The session runs the NATIVE Windows claude.exe, not the WSL one. WSL only holds the pty: a Windows
# child launched from a /mnt/d working directory reports a real `D:\...` cwd, so native toolchains
# and the interactive desktop both work. Starting it from an ext4 directory instead gets the
# cmd.exe "UNC paths are not supported" failure.
#
# Usage: cc-session.sh <project> <origin> [<start|resume> [check|detach|shell|restart|name]]
#
# <project> is a directory name under WSL_PROJECT_ROOT, or the project's Windows path (`D:\...`),
# which must lie under it; the Claude Code Dashboard passes the path, being the one caller that knows
# a directory and not the root it sits in. <origin> names the machine whose keyboard the person is
# at — `windows` from this box, `mac` from the other one — and both attaching callers pass it as a
# bare token, which is the only thing that survives the Windows sshd's cmd.exe.
#
# The third word says whether a person asked for this session just now. `start` is a pick, a
# cmd+shift+r or attach.cmd, and creates whatever is missing. `resume` is the Mac tab reconnecting,
# or agterm restoring a tab, and creates only a session that did not end cleanly: one whose agent
# exited 0 was ended on purpose, so a resume exits 5 instead and the Mac tab closes as it would have
# had it seen the exit live (lib.sh remote_session_ended_marker).
#
# A trailing `check` runs every refusal below and stops before creating or attaching anything,
# exiting 0 where the real run would go ahead. It exists because the Windows sshd drops a command's
# exit status whenever ssh allocates a terminal: measured 2026-10-20 from the Mac, `ssh -tt` returned
# 0 for remote exits 1, 2, 4 and 7, for plain cmd.exe as well as through wsl, while the same commands
# without a terminal returned each code intact. The attach needs a terminal, so mac/attach.sh asks
# this question first over an ssh without one, and reads every code below from that run alone.
#
# A trailing `detach` instead creates the session and stops before attaching, exiting 0 whether it
# created one or found one running, and prints the project as an attach takes it: the path below
# WSL_PROJECT_ROOT, which is what mac/attach.sh and this script's first word expect. It is the
# Windows dashboard's launcher: a message to a project with no session starts one nobody has
# opened a terminal for, and an attach with no terminal fails after the session already exists.
# The origin is then recorded nowhere, there being no client.
#
# A trailing `shell` opens a login shell in the project's directory and touches no session, so the
# holder need not be up and the third word changes nothing. It is what cmd+d runs in a Mac tab
# (mac/attach.sh), sent here so the directory is derived and refused in one place: `wsl --cd` handed
# a path that does not exist opens its shell in `/` and still exits 0.
#
# A trailing `name` prints two lines and touches nothing, so the holder need not be up and the
# second and third words change nothing: the project as an attach takes it, as `detach` prints it,
# then the tmux session name it runs under. It is how the Windows dashboard learns whether a session
# it delivered a message to is one of these, and the name a Mac tab attaches to it by, without a
# second copy of WSL_PROJECT_ROOT or of remote_session_name.
#
# A trailing `restart` fixes what a 6 or a 7 reported: a tmux server that no longer draws new panes
# is stopped, the holder restarted to bring a fresh one up, and every session that was running
# created again; a session that alone stopped drawing is created again by itself. It attaches
# nothing itself, and exits 4 when the holder does not come back. It is what mac/attach.sh runs when
# the person answers yes.
#
# The exit codes: 2 usage, 1 no such project directory, 4 the holder is down, 5 the session was
# ended on purpose, 6 the tmux server no longer draws new panes, 7 this session never drew (both
# check only). A failing `tmux attach-session` also exits 1, its status being this script's
# last — `kill-server`, and a session killed between the check below and the attach, both produce
# it. The holder gets its own code because it is the one refusal here that clears without a person —
# the sshd answers before logon and the holder's scheduled task fires at it — so a Mac tab that keeps
# trying comes back, where one that stopped would need somebody.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

project=${1:-}
origin=${2:-}
# An attach.sh from before the third word passes none, and a usage exit reaches it as 0 through
# ssh and cmd.exe, which it reads as the session ending and closes the tab. So an absent word means
# `start`, which is how every attach behaved before the word existed.
mode=${3:-start}
case $mode in
    start|resume) ;;
    *) mode= ;;
esac
check=${4:-}
case $check in
    ''|check|detach|shell|restart|name) ;;
    *) mode= ;;
esac
if [ -z "$project" ] || [ -z "$origin" ] || [ -z "$mode" ]; then
    echo "usage: cc-session.sh <project> <origin> [<start|resume> [check|detach|shell|restart|name]]" >&2
    exit 2
fi

# A Windows path is translated and must sit under the root, since the session name is derived from
# the part below it, as start-here.sh derives it, and a path elsewhere would name it by its basename
# alone and collide with a project of that name under the root.
case $project in
    [A-Za-z]:\\*|[A-Za-z]:/*)
        windows_path=$project
        if ! project=$(remote_session_relative "$(wslpath -u "$windows_path")"); then
            printf 'cc-session: %s is not under %s\n' "$windows_path" "$WSL_PROJECT_ROOT" >&2
            exit 1
        fi
        ;;
esac

# Recorded in the environment of the tmux client this script attaches, where start-here.sh reads it
# back to decide whether a terminal on ITS machine is already attached. Demanded rather than
# defaulted: an unrecorded origin reads as `unknown` there and refuses, so a default would silently
# make every attach from one machine block the other.
export REMOTE_SESSION_ORIGIN="$origin"

directory="$WSL_PROJECT_ROOT/$project"
if [ ! -d "$directory" ]; then
    echo "cc-session: no such project directory: $directory" >&2
    exit 1
fi
if [ "$check" = shell ]; then
    cd "$directory"
    exec "${SHELL:-/bin/sh}" -l
fi

# Derived through the shared helper so this agrees with start-here.sh, which names the session from
# the directory it is standing in rather than from an argument. The `=` prefix makes tmux match the
# name exactly; without it "cc-games" would also answer for "cc-games-old" and attach the wrong one.
name=$(remote_session_name "$project")
session="=$name"
if [ "$check" = name ]; then
    printf '%s\n%s\n' "$project" "$name"
    exit 0
fi

# Registered under this name by windows/install.ps1's $TaskName.
holder_task=ClaudeRemoteSessionHolder

# Refuse rather than start a session that would not survive. The tmux server must be the holder's:
# a server started from this connection would hand every Windows process inside it to this
# connection's job object, and the session would look perfectly healthy right up until the moment
# the connection drops and takes claude.exe with it.
if ! remote_session_holder_up; then
    echo "cc-session: the holder is not running, so any session started now would die at disconnect." >&2
    echo "cc-session: start it with 'schtasks /run /tn $holder_task' on the Windows side," >&2
    echo "cc-session: or re-run windows/install.ps1 if it was never registered." >&2
    exit 4
fi

if [ "$mode" = resume ] && ! tmux has-session -t "$session" 2>/dev/null && [ -e "$(remote_session_ended_marker "$name")" ]; then
    echo "cc-session: $name was ended on purpose, so it is not started again." >&2
    exit 5
fi

# A server can stop drawing panes created after some moment while it keeps running them, and the
# panes it drew before go on updating. Measured 2026-11-20 on tmux 3.4, cause not identified: a new
# pane's command ran and capture-pane stayed empty, where a separate `-L` server showed the same line
# at once. Every session created then opens as a blank screen that ignores keys, so the check and the
# restart both prove a fresh pane draws first. The probe's name lacks the `cc-` prefix so the picker
# never lists it, and its command ends by itself, so a run cut off before the kill leaves nothing
# behind. A server that wedges after a tab attached is not caught until the next open.
tmux_draws_new_panes() {
    probe="liveness-probe-$$"
    marker="cc-session-liveness-$$-$(date +%s%N)"
    tmux new-session -d -s "$probe" -x 80 -y 5 "printf '%s\\n' $marker; sleep 5"
    remote_session_size_window "$probe" 80 5
    drawn=
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if tmux capture-pane -p -t "=$probe:" 2>/dev/null | grep -qF "$marker"; then
            drawn=1
            break
        fi
        sleep 0.1
    done
    tmux kill-session -t "=$probe" 2>/dev/null || true
    [ -n "$drawn" ]
}

# Present while a restart is under way, for the reattach command below to wait on.
restart_marker="${XDG_STATE_HOME:-$HOME/.local/state}/claude-remote-session/restarting"

# What a client attached to a session runs in place of its view when a restart detaches it: wait
# for the restart to finish, then attach again through this script. tmux runs it in the client's own
# process, so it keeps that terminal and its environment, and with it the REMOTE_SESSION_ORIGIN its
# entry point exported — measured 2026-11-20 on tmux 3.4 with `detach-client -E`. Waiting on the
# marker rather than on the holder or the session matters: both still answer until the kill, and a
# client that attached then would be killed with them. The wait is bounded so a restart cut off
# before it removes the marker still lets the client try, and be refused.
reattach_command() {  # <project>
    printf '%s' "echo 'The session is restarting. This terminal reattaches when it is back.'
i=0
while [ -e $(remote_session_quote "$restart_marker")] && [ \$i -lt 120 ]; do sleep 1; i=\$((i + 1)); done
[ -n \"\${REMOTE_SESSION_ORIGIN:-}\" ] || { echo 'This terminal recorded no machine, so it cannot reattach by itself.'; exit 1; }
exec $(remote_session_quote "$here/cc-session.sh" "$1")\"\$REMOTE_SESSION_ORIGIN\" resume"
}

# Hands every client attached to a cc- session reattach_command, or only the clients of the one
# session named. A client on a directory outside WSL_PROJECT_ROOT, which this script cannot be
# handed, is only detached.
reattach_clients() {  # [<session name>]
    tmux list-clients -F '#{session_name}|#{client_tty}|#{session_path}' | grep '^cc-' \
        | while IFS='|' read -r client_session client_tty client_path; do
            [ -z "${1:-}" ] || [ "$client_session" = "$1" ] || continue
            client_project=$(remote_session_relative "$client_path") || client_project=
            if [ -n "$client_project" ]; then
                tmux detach-client -t "$client_tty" -E "$(reattach_command "$client_project")" || true
            else
                tmux detach-client -t "$client_tty" || true
            fi
        done
}

# A session created while the server was not drawing stays blank after the server recovers, so a
# passing probe does not clear it. Measured 2026-11-21: cc-scheduler, created at 22:05 inside the
# stall, still showed one line ("…") on an alternate screen with the cursor at 1,0 the next morning,
# its agent alive and its title still forwarded, while new panes drew again and a session beside it
# showed 33 lines. Claude's interface fills far more than one line within seconds, so a session
# older than half a minute showing one line or none is taken as one that will never draw.
# The has-session comes first because display-message on a missing session prints nothing and exits
# 0 (tmux 3.4, measured 2026-11-21), which once passed the age test and reported a session that
# had ended as one that never drew.
# A window one line high can show no more than one line however well it draws, so it proves nothing
# and the attach goes ahead: with window-size `latest` the attaching client resizes it and the TUI
# redraws. Measured 2026-11-25: a dashboard tab agwinterm opens unselected stays a 1x1 client, so its
# session's window was 1x1 and reported here as never drawn, though resized to 147x51 it showed the
# interface whole. A restart would not have helped, since the background tab reattaches at 1x1.
session_shows_nothing() {
    tmux has-session -t "$session" 2>/dev/null || return 1
    [ "$(tmux display-message -p -t "$session:" '#{window_height}')" -gt 1 ] || return 1
    session_created=$(tmux display-message -p -t "$session:" '#{session_created}')
    [ $(( $(date +%s) - session_created )) -ge 30 ] || return 1
    [ "$(tmux capture-pane -p -t "$session:" | grep -c '[^[:space:]]' || true)" -le 1 ]
}

# The check only reports what it finds, since a restart ends the agents in it; mac/attach.sh asks
# the person, and a yes comes back as `restart`, which looks again first so that something fixed
# meanwhile is left alone. A server that stopped drawing new panes is restarted whole, holder
# included: its script stays alive across a `kill-server`, which leaves the task running and
# `schtasks /run` doing nothing, and a server started from this connection would die with it. The
# /end then /run pair is the README's own recovery for that state. Every session that was running
# is then created again. A server that draws, with this one session blank, gets only that session
# restarted. Either way every terminal that was attached reattaches through reattach_command.
if [ "$check" = check ] || [ "$check" = restart ]; then
    # Unprefixed, unlike this script's other messages: mac/attach.sh shows these around its restart
    # prompt, which carries none either.
    if ! tmux_draws_new_panes; then
        if [ "$check" = check ]; then
            echo "tmux on the Windows machine has stopped drawing new sessions." >&2
            echo "Restarting it fixes this, and these sessions resume their conversations:" >&2
            # Named as the picker names them, by the directory under the root.
            tmux list-sessions -F '#{session_name}|#{session_path}' | grep '^cc-' \
                | while IFS='|' read -r _ listed_path; do
                    listed=$(remote_session_relative "$listed_path") || listed=${listed_path##*/}
                    printf '  %s\n' "$listed" >&2
                done
            exit 6
        fi
        mkdir -p "$(dirname "$restart_marker")"
        : > "$restart_marker"
        sessions=$(tmux list-sessions -F '#{session_name}|#{session_path}' | grep '^cc-' || true)
        reattach_clients
        tmux kill-server
        schtasks.exe /end /tn "$holder_task" >&2
        schtasks.exe /run /tn "$holder_task" >&2
        waited=0
        until remote_session_holder_up; do
            if [ "$waited" -ge 60 ]; then
                rm -f "$restart_marker"
                echo "tmux stopped, but the holder did not bring it back within 60 s." >&2
                exit 4
            fi
            sleep 1
            waited=$((waited + 1))
        done
        resumed=0
        while IFS='|' read -r session_name session_path; do
            [ -n "$session_name" ] || continue
            tmux has-session -t "=$session_name" 2>/dev/null \
                || remote_session_create "$session_name" "$session_path" "$(remote_session_resume_command "$CLAUDE_EXE")" 200 50
            resumed=$((resumed + 1))
        done <<EOF
$sessions
EOF
        rm -f "$restart_marker"
        echo "tmux restarted. Sessions resumed: $resumed." >&2
        exit 0
    fi
    if session_shows_nothing; then
        if [ "$check" = check ]; then
            echo "The $project session on the Windows machine has stopped drawing." >&2
            echo "Restarting it fixes this, and its agent resumes its conversation." >&2
            exit 7
        fi
        mkdir -p "$(dirname "$restart_marker")"
        : > "$restart_marker"
        session_path=$(tmux display-message -p -t "$session:" '#{session_path}')
        reattach_clients "$name"
        tmux kill-session -t "$session"
        remote_session_create "$name" "$session_path" "$(remote_session_resume_command "$CLAUDE_EXE")" 200 50
        rm -f "$restart_marker"
        echo "The $project session restarted." >&2
        exit 0
    fi
    if [ "$check" = restart ]; then
        echo "tmux and the $project session both draw again, so nothing was restarted." >&2
        exit 0
    fi
fi
[ "$check" != check ] || exit 0

remote_session_clear_dead "$name" cc-session

# Created at the attaching terminal's size, so the TUI's first draw already fits it; after that the
# window follows whichever attached client was used last. The 200x50 fallback, for a call with no
# terminal, keeps a session started that way from being laid out at tmux's 80x24.
if ! tmux has-session -t "$session" 2>/dev/null; then
    remote_session_create "$name" "$directory" "$(remote_session_resume_command "$CLAUDE_EXE")" 200 50
fi
if [ "$check" = detach ]; then
    printf '%s\n' "$project"
    exit 0
fi

remote_session_attach "$name" "$origin"
