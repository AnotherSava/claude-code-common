#!/bin/sh
# Opens the Windows box's Claude session for one project in this terminal.
#
# Usage: attach.sh <project>
#
# Safe to run while a Windows terminal is attached to the same session — tmux takes both clients at
# once, which is the whole reason the design is tmux rather than `claude --bg` + `claude attach`.
# Both clients then draw at the narrower one's width.

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
# rather than half-working further in.
case $project in
    *[!A-Za-z0-9._/-]*)
        echo "attach: '$project' has a character that does not survive the Windows shell, so it" >&2
        echo "attach: cannot be reached from here. Start it on that machine instead — 'claude' in" >&2
        echo "attach: the folder, which passes nothing through that boundary." >&2
        exit 1
        ;;
esac

# The checkout is the same repo on both machines, so the far side runs its own copy of this script's
# sibling. Keeping the remote command to bare tokens is what makes it survive cmd.exe, which is the
# Windows sshd's default shell.
# The trailing `mac` is the origin: this script only ever runs on the Mac, so it is the one place
# that knows the person is not at the Windows keyboard. `claude` over there reads it back off the
# client and attaches alongside rather than refusing.
exec ssh -t "$REMOTE_USER@$REMOTE_HOST" "wsl -d $WSL_DISTRO -- $REPO_WSL_PATH/claude/remote-session/wsl/cc-session.sh $project mac"
