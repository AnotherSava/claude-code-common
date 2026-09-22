#!/bin/sh
# Loads the shared config and hands it to pick-session.py, which does the work.
#
# This split exists so there is one config loader rather than two: the Python side would otherwise
# need its own copy of the transcrypt-locked-checkout check, which is the part worth not duplicating.
#
# Bound to a chord in agterm's keymap, which resolves binaries against the app's GUI PATH — the
# launchd default plus the bundled agtermctl, /usr/local/bin and /opt/homebrew/bin — and not against
# anything a login shell adds. Everything invoked from here stays inside that set: `env` by absolute
# path, then python3 and agtermctl, both of which it covers.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/../lib.sh"
remote_session_load_config "$here/../config.secret.env" || exit 1

# CLAUDE_EXE and REPO_WSL_PATH stay unexported: attach.sh loads those for itself. The loader still
# runs for all of it, because it is the one place that recognises a transcrypt-locked checkout.
export REMOTE_HOST REMOTE_USER REMOTE_DEVICE WSL_DISTRO WSL_PROJECT_ROOT

exec /usr/bin/env python3 "$here/pick-session.py"
