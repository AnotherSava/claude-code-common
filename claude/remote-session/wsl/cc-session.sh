#!/bin/sh
# Attaches the tmux session for one project, creating it first if it is not running yet.
#
# The session runs the NATIVE Windows claude.exe, not the WSL one. WSL only holds the pty: a Windows
# child launched from a /mnt/d working directory reports a real `D:\...` cwd, so native toolchains
# and the interactive desktop both work. Starting it from an ext4 directory instead gets the
# cmd.exe "UNC paths are not supported" failure.
#
# Usage: cc-session.sh <project>      # <project> is a directory name under WSL_PROJECT_ROOT

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

project=${1:-}
if [ -z "$project" ]; then
    echo "usage: cc-session.sh <project>" >&2
    exit 2
fi

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
    exit 1
fi

# A detached session is created at tmux's 80x24 default, and the TUI draws itself once at that size.
# Creating it wide means the first thing an attaching client sees is not a session laid out for a
# terminal nobody is using; clients then clamp the pane down to the narrowest one attached.
if ! tmux has-session -t "$session" 2>/dev/null; then
    tmux new-session -d -s "$name" -x 200 -y 50 -c "$directory" "$CLAUDE_EXE"
fi

exec tmux attach-session -t "$session"
