#!/bin/sh
# Starts Claude in the current directory inside the holder's tmux server, so the session can be
# attached later — from a second terminal on this machine, or from the Mac.
#
# This is the body of the Windows machine's `claude` shell function. Every shell there is a thin
# caller of this one script — Git Bash, Windows PowerShell 5.1 and PowerShell 7 — so the behaviour
# lives in the repo rather than in per-machine profiles that nothing versions. The function itself is
# written by windows/install-shells.ps1.
#
# Called as `wsl -d <distro> -- <this> [claude args...]`. Nothing has to convert the path: wsl.exe
# starts with the caller's Windows working directory already translated, so $PWD is right.
#
# What it preserves from the functions it replaces: a session resumes with `--continue` and falls
# back to a fresh conversation where there is none, and Claude's own terminal-title writes stay
# disabled so the dashboard's tab colour survives.
#
# There is no flag for starting a fresh conversation instead of resuming. `/clear` inside the session
# does that, from either terminal watching it, which is the reachable answer once a session can have
# a client on each machine; a flag read once at creation could not be.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

# Claude's per-tick OSC title writes would otherwise clobber the status circle the dashboard puts in
# the tab. WSL passes an environment variable to a Windows child only when WSLENV names it. This
# covers the commands that run straight through below; a session's command carries its own copy
# (lib.sh remote_session_resume_command), because tmux does not hand this environment to a pane.
CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
WSLENV="CLAUDE_CODE_DISABLE_TERMINAL_TITLE:${WSLENV:-}"
export CLAUDE_CODE_DISABLE_TERMINAL_TITLE WSLENV

# The machine whose keyboard the person is at. This script only ever runs on the Windows box, so it
# can state it rather than work it out, and the tmux client it attaches carries it for as long as
# that client lives. No WSLENV entry: the reader is another Linux process in this distro, not a
# Windows child.
REMOTE_SESSION_ORIGIN=windows
export REMOTE_SESSION_ORIGIN

# Claude Code's own subcommands, and the flags that print and exit, open no session in this
# directory — so they run straight through instead of being wrapped. Without this, `claude update`
# reached the one-session-per-directory refusal below and never ran at all, telling the user to
# attach to a session they were not trying to start.
#
# The list is the Commands section of `claude --help`, matched on the first argument only, which is
# where a subcommand is always typed. It has to be a list rather than a rule, because `claude <word>`
# is equally a prompt: Claude Code decides between the two by knowing its own commands, and nothing
# here can infer it. A command added later falls through to the session path and refuses, which
# names itself clearly enough to recognise — add it here when that happens.
case "${1:-}" in
    agents|attach|auth|auto-mode|doctor|gateway|import|install|logs|mcp|plugin|plugins|project|respawn|rm|setup-token|stop|kill|ultrareview|update|upgrade)
        exec "$CLAUDE_EXE" "$@" ;;
    -h|--help|-v|--version|-p|--print|--bg|--background)
        exec "$CLAUDE_EXE" "$@" ;;
esac

inner=$(remote_session_resume_command "$CLAUDE_EXE" "$@")

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

# Clear a session whose command died before deciding anything about it. `remain-on-exit failed` holds
# that pane so the error is still readable instead of vanishing with the session, and this is where
# it gets read: printed, removed, and a fresh session started below. Checked here rather than right
# after creating one, because a command rejected on startup takes longer to die than the next line
# takes to run — so the create path always lost that race, while by the time anyone types `claude`
# here again the pane has long since settled.
#
# The bare session name for these two, not the `=` exact-match form the rest of the file uses:
# display-message and capture-pane reject `=name` with "can't find pane", which reads as a session
# that is not there rather than as a name they will not take.
if [ "$(tmux display-message -p -t "$session" '#{pane_dead}' 2>/dev/null)" = "1" ]; then
    tmux capture-pane -p -t "$session" | sed '/^[[:space:]]*$/d;s/^/claude: /' >&2
    printf 'claude: that session ended with the error above. Starting a new one.\n' >&2
    tmux kill-session -t "=$session"
fi

# One session per directory, and one terminal per machine onto it. A session already running here is
# joined, not refused — that is what tmux serving several clients at once is for, and it is how the
# Mac and this box watch the same agent. Only a terminal on THIS machine is turned away, because a
# second one here is two windows onto one pane, echoing each other and both clamped to the narrower.
#
# A client that recorded no origin is turned away too. Its absence is not evidence of "somewhere
# else": it is equally a client attached before this convention shipped, one attached by driving tmux
# by hand, and one whose /proc entry could not be read. Refusing on it is the direction that cannot
# open two windows here by accident, and it clears as soon as that client reattaches.
if tmux has-session -t "=$session" 2>/dev/null; then
    # An absolute path, derived from where this script actually sits. A path relative to the dotfiles
    # repo is unusable in the one place this message is ever read: the reader is standing in the
    # project directory they tried to start Claude in, where no such file exists.
    #
    # printf with %s, not echo: this shell's echo expands backslash escapes, and a Windows path is
    # nothing but backslashes — `claude\remote-session\windows\attach.cmd` came out as
    # `claudeemote-session\windowsttach.cmd`, having eaten \r as a carriage return and \a as a bell.
    attach=$(wslpath -w "$(CDPATH= cd -- "$here/../windows" && pwd)/attach.cmd")

    origins=$(remote_session_client_origins "$session")
    if printf '%s\n' "$origins" | grep -q -x "$REMOTE_SESSION_ORIGIN"; then
        printf 'claude: a terminal on this machine is already attached to this session.\n' >&2
        printf 'claude:   %s %s\n' "$attach" "$relative" >&2
        exit 1
    fi
    if printf '%s\n' "$origins" | grep -q -x unknown; then
        printf 'claude: a client is attached that recorded no machine, so this cannot tell it from a terminal here.\n' >&2
        printf 'claude: Reattach it through cmd+shift+r or attach.cmd and this clears.\n' >&2
        printf 'claude:   %s %s\n' "$attach" "$relative" >&2
        exit 1
    fi

    # Nothing attached, or only the other machine: this is the second viewer the design exists for,
    # so join what is running rather than refusing or starting a second conversation beside it.
    remote_session_attach "$session" "$REMOTE_SESSION_ORIGIN"
    exit
fi

# Created detached and attached as a second step, rather than in one call. A single
# `tmux new-session` without -d fails outright when there is no terminal to attach to, creating
# nothing; this way the session exists and is recoverable even if the attach is what went wrong.
# The pane is forked by the holder's server either way, which is what keeps the Windows child out
# of this connection's job object.
remote_session_keep_failed_panes
tmux new-session -d -s "$session" -c "$PWD" "$inner"
remote_session_attach "$session" "$REMOTE_SESSION_ORIGIN"
