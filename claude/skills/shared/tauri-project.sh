#!/usr/bin/env bash
# Shared by the deploy skill's deploy-tauri.sh and the cleanup skill's cleanup-tauri.sh — sourced, never executed,
# after shared/deploy-config.sh, whose DEPLOY_OS it reads. What deploy installs is what cleanup has to find, so
# both take a Tauri project's names and its installed file names from here.

# Read src-tauri/tauri.conf.json and src-tauri/Cargo.toml under <repo-dir> into PRODUCT_NAME (display only, may be
# empty), IDENTIFIER and BIN_NAME (Cargo's [package].name, which names the binary). Returns 1 with the reason
# printed when either file or the binary name is missing.
tauri_read_project() {
    local conf="$1/src-tauri/tauri.conf.json" cargo="$1/src-tauri/Cargo.toml"
    if [ ! -f "$conf" ]; then
        echo "ERROR: src-tauri/tauri.conf.json not found (run from Tauri project root)"
        return 1
    fi
    if [ ! -f "$cargo" ]; then
        echo "ERROR: src-tauri/Cargo.toml not found (run from Tauri project root)"
        return 1
    fi
    PRODUCT_NAME=$(sed -n 's/.*"productName"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$conf" | head -1)
    IDENTIFIER=$(sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$conf" | head -1)
    BIN_NAME=$(sed -n '/^\[package\]/,/^\[/{ s/^name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p; }' "$cargo" | head -1)
    if [ -z "$BIN_NAME" ]; then
        echo "ERROR: could not extract [package].name from src-tauri/Cargo.toml"
        return 1
    fi
}

# The name the app is installed under inside INSTALL_DIR, for a build that produced a macOS .app bundle (`bundle`)
# or only the bare binary (`binary`). The two differ on macOS alone; deploy installs whichever the build produced,
# so cleanup, which cannot know which that was, looks for both.
tauri_installed_name() {
    case "$DEPLOY_OS:$1" in
        win:*)      printf '%s\n' "$BIN_NAME.exe" ;;
        mac:bundle) printf '%s\n' "${PRODUCT_NAME:-$BIN_NAME}.app" ;;
        *)          printf '%s\n' "$BIN_NAME" ;;
    esac
}
