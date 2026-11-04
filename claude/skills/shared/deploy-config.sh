#!/usr/bin/env bash
# Shared by the deploy targets, the deploy dispatcher and the cleanup script — sourced, never executed.
#
# A project's deploy settings are its committed config/deploy.env with an ignored config/deploy.local.env over it.
# deploy_config.py beside this file reads them, for these scripts and for the Python callers alike, and its
# docstring has the two files' roles.
#
# Sourcing this sets DEPLOY_REPO_DIR to the project root, found by walking up from $PWD to config/deploy.env,
# DEPLOY_OS to mac, win or linux, and DEPLOY_PY to the interpreter name that OS answers to.

source "$(dirname "${BASH_SOURCE[0]}")/repo-root.sh"

DEPLOY_REPO_DIR="$(resolve_repo_dir config/deploy.env)"
DEPLOY_CONFIG_PY="$(dirname "${BASH_SOURCE[0]}")/deploy_config.py"

case "$(uname -s)" in
    Darwin) DEPLOY_OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) DEPLOY_OS=win ;;
    *) DEPLOY_OS=linux ;;
esac
DEPLOY_PY=python3; [ "$DEPLOY_OS" = "win" ] && DEPLOY_PY=python

# One setting's value, or nothing: `deploy_get KEY [project-root]`, the root defaulting to DEPLOY_REPO_DIR.
deploy_get() {
    "$DEPLOY_PY" "$DEPLOY_CONFIG_PY" get "${2:-$DEPLOY_REPO_DIR}" "$1"
}

# Expand the per-OS placeholders a committed path may carry, so one value resolves on every machine.
# %APP_CONFIG% is the user config dir; %APPDATA% is its older Windows spelling, still found in existing files.
deploy_expand() {
    local p="$1" app_config
    case "$DEPLOY_OS" in
        win)   app_config="$APPDATA" ;;
        mac)   app_config="$HOME/Library/Application Support" ;;
        linux) app_config="${XDG_CONFIG_HOME:-$HOME/.config}" ;;
    esac
    p="${p//%APP_CONFIG%/$app_config}"
    p="${p//\$\{APP_CONFIG\}/$app_config}"
    p="${p//%APPDATA%/$app_config}"
    p="${p//\$\{APPDATA\}/$app_config}"
    printf '%s\n' "$p"
}

# Where an installed app goes when the project names no INSTALL_DIR: the folder every app on that OS shares on
# macOS, and a folder of its own under C:/Programs on Windows, named after the binary. A committed file leaves
# INSTALL_DIR out when these fit, since any one path it could carry is right on one OS only.
deploy_install_dir() {
    local name="$1" dir
    dir="$(deploy_get INSTALL_DIR)"
    if [ -n "$dir" ]; then deploy_expand "$dir"; return 0; fi
    case "$DEPLOY_OS" in
        mac)   printf '%s\n' "/Applications" ;;
        win)   printf '%s\n' "C:/Programs/$name" ;;
        linux) printf '%s\n' "$HOME/.local/bin" ;;
    esac
}
