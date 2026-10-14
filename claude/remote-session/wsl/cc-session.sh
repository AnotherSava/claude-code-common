#!/bin/sh
# Attaches the tmux session for one project, creating it first if it is not running yet.
#
# The session runs the NATIVE Windows claude.exe, not the WSL one. WSL only holds the pty: a Windows
# child launched from a /mnt/d working directory reports a real `D:\...` cwd, so native toolchains
# and the interactive desktop both work. Starting it from an ext4 directory instead gets the
# cmd.exe "UNC paths are not supported" failure.
#
# Usage: cc-session.sh <project> <origin>
#
# <project> is a directory name under WSL_PROJECT_ROOT. <origin> names the machine whose keyboard
# the person is at — `windows` from this box, `mac` from the other one — and both callers pass it as
# a bare token, which is the only thing that survives the Windows sshd's cmd.exe.
#
# The exit codes a caller branches on: 2 usage, 1 no such project directory, 4 the holder is down.
# A failing `tmux attach-session` also arrives as 1, its status being this script's last —
# `kill-server`, and a session killed between the check below and the attach, both produce it — so
# a caller that reads 1 cannot separate that from a missing directory and can only say the far side
# refused. The holder gets its own code because it is the one refusal here that clears without a
# person — the sshd answers before logon and the holder's scheduled task fires at it — so a Mac tab
# that keeps trying comes back, where one that stopped would need somebody.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

project=${1:-}
origin=${2:-}
if [ -z "$project" ] || [ -z "$origin" ]; then
    echo "usage: cc-session.sh <project> <origin>" >&2
    exit 2
fi

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

# Created at the attaching terminal's size, so the TUI's first draw already fits it; after that the
# window follows whichever attached client was used last. The 200x50 fallback, for a call with no
# terminal, keeps a session started that way from being laid out at tmux's 80x24.
if ! tmux has-session -t "$session" 2>/dev/null; then
    remote_session_keep_failed_panes
    remote_session_create "$name" "$directory" "$(remote_session_resume_command "$CLAUDE_EXE")" 200 50
fi

remote_session_attach "$name" "$origin"
