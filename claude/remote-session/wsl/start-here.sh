#!/bin/sh
# Starts Claude in the current directory inside the holder's tmux server, so the session can be
# attached later — from a second terminal on this machine, or from the Mac.
#
# This is the body of the Windows machine's `claude` shell function. Both of them — Git Bash's
# `claude()` and PowerShell's `function claude` — are thin callers of this one script, so the
# behaviour lives in the repo rather than in two per-machine profiles that nothing versions.
#
# Called as `wsl -d <distro> -- <this> [claude args...]`. Nothing has to convert the path: wsl.exe
# starts with the caller's Windows working directory already translated, so $PWD is right.
#
# What it preserves from the functions it replaces: `--new` starts a fresh conversation, anything
# else resumes with `--continue` and falls back to a fresh one, and Claude's own terminal-title
# writes stay disabled so the dashboard's tab colour survives.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

# Claude's per-tick OSC title writes would otherwise clobber the status circle the dashboard puts in
# the tab. WSL passes an environment variable to a Windows child only when WSLENV names it.
CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
WSLENV="CLAUDE_CODE_DISABLE_TERMINAL_TITLE:${WSLENV:-}"
export CLAUDE_CODE_DISABLE_TERMINAL_TITLE WSLENV

fresh=""
if [ "${1:-}" = "--new" ]; then
    shift
    fresh=yes
fi

if [ -n "$fresh" ]; then
    inner="exec $(remote_session_quote "$CLAUDE_EXE") $(remote_session_quote "$@")"
else
    inner=$(remote_session_resume_command "$CLAUDE_EXE" "$@")
fi

# Nothing to wrap in: either there is no server to put this in, or we are already inside a pane and
# tmux will not nest. Run Claude directly and say why, rather than refusing to start it at all —
# losing the everyday command because a scheduled task died is the worse failure.
if [ -n "${TMUX:-}" ]; then
    exec sh -c "$inner"
fi
if ! remote_session_holder_up; then
    echo "claude: the session holder is not running, so this session will not survive a disconnect." >&2
    echo "claude: start it with 'schtasks /run /tn ClaudeRemoteSessionHolder'." >&2
    exec sh -c "$inner"
fi

relative=$(remote_session_relative "$PWD")
session=$(remote_session_name "$relative")

# One session per directory. A second Claude here would be a second conversation in the same
# project, and the session already running is almost always the one that was wanted.
if tmux has-session -t "=$session" 2>/dev/null; then
    # printf, not echo: this shell's echo expands backslash escapes, and a Windows path is nothing
    # but backslashes — `claude\remote-session\windows\attach.cmd` came out as
    # `claudeemote-session\windowsttach.cmd`, having eaten \r as a carriage return and \a as a bell.
    printf 'claude: attach to the session already running here instead of starting another:\n' >&2
    printf 'claude:   claude\\remote-session\\windows\\attach.cmd %s\n' "$relative" >&2
    printf 'claude: or cmd+shift+r on the Mac, which lists it.\n' >&2
    exit 1
fi

# Created detached and attached as a second step, rather than in one call. A single
# `tmux new-session` without -d fails outright when there is no terminal to attach to, creating
# nothing; this way the session exists and is recoverable even if the attach is what went wrong.
# The pane is forked by the holder's server either way, which is what keeps the Windows child out
# of this connection's job object.
tmux new-session -d -s "$session" -c "$PWD" "$inner"
exec tmux attach-session -t "=$session"
