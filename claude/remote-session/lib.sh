#!/bin/sh
# The two things every script here needs: the config, and the rule for naming a session.
#
# Source it, then call what you need:
#
#     . "$(dirname -- "$0")/../lib.sh"
#     remote_session_load_config "$(dirname -- "$0")/../config.secret.env" || exit 1

# Sources config.secret.env into the caller's shell, failing loudly rather than half-configured.
#
# The config is transcrypt-encrypted in git and plaintext in the working tree. A checkout that was
# never unlocked holds base64 ciphertext instead, which `.` would happily source as nonsense — so
# that case is detected and named, because the repair ("run transcrypt here") is not guessable from
# whatever error the caller would hit three lines later.
remote_session_load_config() {
    remote_session_config="$1"

    if [ ! -f "$remote_session_config" ]; then
        echo "remote-session: no config at $remote_session_config" >&2
        return 1
    fi

    # transcrypt stores openssl's salted-base64 form, which always begins with this marker.
    if head -c 10 "$remote_session_config" | grep -q '^U2FsdGVkX1'; then
        echo "remote-session: $remote_session_config is still ciphertext — this checkout was never unlocked." >&2
        echo "remote-session: run transcrypt in it (see the /transcrypt skill), then retry." >&2
        return 1
    fi

    . "$remote_session_config"

    for remote_session_key in REMOTE_HOST REMOTE_USER REMOTE_DEVICE WSL_DISTRO WSL_PROJECT_ROOT REPO_WSL_PATH CLAUDE_EXE; do
        eval "remote_session_value=\${$remote_session_key:-}"
        if [ -z "$remote_session_value" ]; then
            echo "remote-session: $remote_session_key is missing from $remote_session_config" >&2
            return 1
        fi
    done
}

# The tmux session that keeps the holder's server alive. Defined here because four places need it —
# the holder that creates it, the two scripts that refuse to start anything without it, and the
# installer's proof that it came up — and renaming it anywhere else would leave the others checking
# for a session that no longer exists, reported as "the holder is down" while the holder runs.
# install.ps1 cannot source this file, so it reads the value out of this line.
REMOTE_SESSION_KEEPALIVE=_holder

# Whether the holder's tmux server is up. Every session must be created inside it: a server started
# from a connection hands every Windows process in it to that connection's job object, so sessions
# started any other way die at disconnect while looking perfectly healthy until then.
remote_session_holder_up() {
    tmux has-session -t "=$REMOTE_SESSION_KEEPALIVE" 2>/dev/null
}

# The machine each client attached to a session is sitting at, one line per client, `unknown` where
# the client recorded none. Takes the bare session name.
#
# The origin cannot be inferred, which is why every entry point has to state it. Measured 2026-09-22
# against one local client and one attached from the Mac: the tmux client variables, the WSL process
# ancestry and the client's own environment all separated those two, and none of them separated them
# BY MACHINE — client_termtype named the terminal emulator, the ancestry was token-identical, and
# windows/attach.cmd runs on this box the same cc-session.sh the Mac runs over ssh, so a second local
# terminal reproduces the remote's fingerprint byte for byte. The Windows side does see the two
# process trees apart, and has no identifier in common with a tmux client to join them by.
#
# One value covers a client attached before this convention shipped, one attached by driving tmux by
# hand, and one whose /proc entry could not be read. They belong together because none of them can be
# read as "somewhere else", and the caller refuses on all three.
remote_session_client_origins() {
    tmux list-clients -t "=$1" -F '#{client_pid}' 2>/dev/null | while read -r remote_session_client; do
        remote_session_origin=$(tr '\0' '\n' < "/proc/$remote_session_client/environ" 2>/dev/null | sed -n 's/^REMOTE_SESSION_ORIGIN=//p')
        printf '%s\n' "${remote_session_origin:-unknown}"
    done
}

# Keep a pane whose command exited non-zero, instead of destroying the session with it.
#
# A session created for a command Claude Code rejects — an argument it does not know, a directory it
# refuses — otherwise disappears in the same instant it appears, and the only thing on screen is the
# attach failing rather than the reason it failed. `failed` holds that case alone, so an ordinary
# exit still takes the session with it and leaves nothing to clean up.
#
# Set on the server rather than on the session, and before the session exists: one that fails
# immediately can be gone before a `set-option -t` naming it could run.
remote_session_keep_failed_panes() {
    tmux set-option -g remain-on-exit failed
}

# The tmux session name for a project path, given as a path relative to WSL_PROJECT_ROOT.
#
# One function because two scripts derive it and they must agree: cc-session.sh is handed a project
# by the picker, start-here.sh works it out from the directory the shell is standing in, and a name
# that came out differently would leave the second script's session unreachable by the first.
#
# The whole relative path goes into the name, not just its last component. `claude` run in two
# projects' `docs` subdirectories would otherwise ask for the same session, and since a second run
# in one directory is refused, that collision would present as a refusal to start at all. A project
# at the top of the tree still comes out as `cc-<project>`.
remote_session_name() {
    printf 'cc-%s' "$(printf '%s' "$1" | tr '/' '-')"
}

# Single-quotes its arguments for a shell command string this repo builds here and runs elsewhere —
# inside a tmux pane, or through `sh -c`. Each argument comes back with a trailing space, so the
# pieces concatenate without the caller tracking separators.
remote_session_quote() {
    for remote_session_argument; do printf "'%s' " "$(printf '%s' "$remote_session_argument" | sed "s/'/'\\\\''/g")"; done
}

# The command a newly created session runs: resume the conversation already in that directory, or
# start a fresh one where there is none to resume.
#
# Shared because two call sites must agree and did not. start-here.sh is the Windows machine's
# `claude` function and resumed; cc-session.sh is what the Mac's attach runs and launched the
# executable bare, so opening a project from the Mac began a new conversation while opening the same
# project on the Windows box came back to the old one. From the Mac that presents as the remote
# session having lost everything, with nothing on screen to say a second conversation now exists.
#
# `--continue` exits non-zero where the directory holds no conversation yet, which is an ordinary
# first run rather than a failure, so the fallback starts one.
remote_session_resume_command() {
    remote_session_exe=$(remote_session_quote "$1")
    shift
    remote_session_args=$(remote_session_quote "$@")
    printf '%s --continue %s || exec %s %s' "$remote_session_exe" "$remote_session_args" "$remote_session_exe" "$remote_session_args"
}

# The path of a directory relative to WSL_PROJECT_ROOT, or its basename when it lies outside.
remote_session_relative() {
    case "$1" in
        "$WSL_PROJECT_ROOT"/*) printf '%s' "${1#"$WSL_PROJECT_ROOT"/}" ;;
        *) printf '%s' "${1##*/}" ;;
    esac
}
