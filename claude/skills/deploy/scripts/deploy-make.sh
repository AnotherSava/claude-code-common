#!/usr/bin/env bash
# DEPLOY_TYPE=make: run the project's own Makefile target, for a stack whose build and install the project
# already scripts (an Xcode app built through xcodegen, for one). Everything stack-specific stays in the Makefile;
# this only picks the target and supplies the per-machine install location.
#
# Keys:
#   MAKE_TARGET   the target to run; `deploy` when unset.
#   INSTALL_DIR   forwarded as the make variable INSTALL_DIR, placeholders expanded, only when a settings file
#                 names it. Unset, the Makefile's own default applies, since no per-OS guess fits every Makefile.
#                 Being a machine fact, it belongs in config/deploy.local.env.
#
# Arguments are passed to make after these, so `deploy VAR=value` overrides a variable for one run.
# Whether the target stops or launches an app is the Makefile's business; nothing here starts one.
set -euo pipefail

SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"

target="$(deploy_get MAKE_TARGET)"
args=("${target:-deploy}")
dir="$(deploy_get INSTALL_DIR)"
[ -n "$dir" ] && args+=("INSTALL_DIR=$(deploy_expand "$dir")")

echo "deploy: make ${args[*]} $*"
exec make -C "$DEPLOY_REPO_DIR" "${args[@]}" "$@"
