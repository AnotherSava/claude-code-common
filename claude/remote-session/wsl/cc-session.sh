#!/bin/sh
# Attaches the tmux session for one project, creating it first if it is not running yet, or with
# `detach` only creates it.
#
# The session runs the NATIVE Windows claude.exe, not the WSL one. WSL only holds the pty: a Windows
# child launched from a /mnt/d working directory reports a real `D:\...` cwd, so native toolchains
# and the interactive desktop both work. Starting it from an ext4 directory instead gets the
# cmd.exe "UNC paths are not supported" failure.
#
# Usage: cc-session.sh <project> <origin> [<start|resume> [check|detach]]
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
# The exit codes: 2 usage, 1 no such project directory, 4 the holder is down, 5 the session was
# ended on purpose. A failing `tmux attach-session` also exits 1, its status being this script's
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
    ''|check|detach) ;;
    *) mode= ;;
esac
if [ -z "$project" ] || [ -z "$origin" ] || [ -z "$mode" ]; then
    echo "usage: cc-session.sh <project> <origin> [<start|resume> [check|detach]]" >&2
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

# Derived through the shared helper so this agrees with start-here.sh, which names the session from
# the directory it is standing in rather than from an argument. The `=` prefix makes tmux match the
# name exactly; without it "cc-games" would also answer for "cc-games-old" and attach the wrong one.
name=$(remote_session_name "$project")
session="=$name"

# Refuse rather than start a session that would not survive. The tmux server must be the holder's:
# a server started from this connection would hand every Windows process inside it to this
# connection's job object, and the session would look perfectly healthy right up until the moment
# the connection drops and takes claude.exe with it.
if ! remote_session_holder_up; then
    echo "cc-session: the holder is not running, so any session started now would die at disconnect." >&2
    echo "cc-session: start it with 'schtasks /run /tn ClaudeRemoteSessionHolder' on the Windows side," >&2
    echo "cc-session: or re-run windows/install.ps1 if it was never registered." >&2
    exit 4
fi

if [ "$mode" = resume ] && ! tmux has-session -t "$session" 2>/dev/null && [ -e "$(remote_session_ended_marker "$name")" ]; then
    echo "cc-session: $name was ended on purpose, so it is not started again." >&2
    exit 5
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
