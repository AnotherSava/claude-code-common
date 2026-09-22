#!/bin/sh
# Owns the two things that have to outlive every connection: the WSL distro, and the tmux server.
#
# Started by the scheduled task that install.ps1 registers, never by hand. The task is what puts this
# outside every SSH connection's job object; running the same commands over ssh looks identical and
# dies at disconnect.
#
# The copy that actually runs lives in the distro's own filesystem, not here — install.ps1 puts it
# there, because a script executing over the drvfs mount holds a Windows file lock on the checkout.
# Editing this file changes nothing until install.ps1 runs again. The installer copies lib.sh beside
# it, which is why the source path below has no `..` the way its siblings in this directory do.
#
# The distro: WSL shuts an idle one down about 45 s after the last connection closes. The blocking
# `sleep` at the end is a live wsl.exe connection for as long as the logon session lasts, so the
# distro is never idle. `.wslconfig` only removes the distro-level timeout; this is what keeps the VM
# itself busy.
#
# The tmux server: whoever starts it decides whether the sessions inside it survive. A Windows
# process launched through WSL interop joins the job object of the wsl.exe that started its WSL
# session — so a server started from an ssh connection hands every claude.exe inside it to that
# connection, and they are all killed when it drops. The window then closes, the session ends, and
# the server exits with it. Started here instead, the server forks each pane itself and the Windows
# children belong to this scheduled task.
#
# A tmux server with no sessions does not stay up, so the server is held by a session of its own
# rather than by `tmux start-server`, which would exit again immediately.
#
# `sleep` runs as a child rather than through `exec` on purpose: it leaves this script's path in the
# process table, so `pgrep -f holder.sh` identifies the holder exactly.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/lib.sh"

remote_session_holder_up || tmux new-session -d -s "$REMOTE_SESSION_KEEPALIVE" 'sleep infinity'

sleep infinity
