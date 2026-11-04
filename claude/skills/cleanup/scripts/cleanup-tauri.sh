#!/bin/bash
set -e

SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"
source "$SKILLS/shared/app-process.sh"
source "$SKILLS/shared/tauri-project.sh"
REPO_DIR="$DEPLOY_REPO_DIR"
OS="$DEPLOY_OS"

# BACKUP_FILES is a comma- or space-separated list of paths inside the app-data dir to copy to
# <REPO_DIR>/.cleanup-backups/<timestamp>/ before the data wipe, for files the user would lose work over —
# local prompt history, scratch databases. Read, like INSTALL_DIR, from the deploy settings, so a project that
# deploys needs no second configuration to be cleaned up.
BACKUP_FILES="$(deploy_get BACKUP_FILES)"

tauri_read_project "$REPO_DIR" || exit 1
if [ -z "$IDENTIFIER" ]; then
    echo "ERROR: could not extract \"identifier\" from src-tauri/tauri.conf.json"
    exit 1
fi

INSTALL_DIR="$(deploy_install_dir "$BIN_NAME")"
PROC_NAME="$BIN_NAME"
case "$OS" in
    win)
        APP_DATA="$APPDATA/$IDENTIFIER"
        CACHES=("$LOCALAPPDATA/$IDENTIFIER")
        ;;
    mac)
        APP_DATA="$HOME/Library/Application Support/$IDENTIFIER"
        CACHES=("$HOME/Library/Caches/$IDENTIFIER")
        ;;
    linux)
        APP_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$IDENTIFIER"
        CACHES=("${XDG_CACHE_HOME:-$HOME/.cache}/$IDENTIFIER")
        ;;
esac

# Deploy installs a macOS build as its .app bundle, or as the bare binary when the build made no bundle, and which
# one it was is recorded nowhere, so both are removed. Elsewhere the two names are the same file.
DESTS=("$INSTALL_DIR/$(tauri_installed_name bundle)")
[ "$(tauri_installed_name binary)" != "$(tauri_installed_name bundle)" ] && DESTS+=("$INSTALL_DIR/$(tauri_installed_name binary)")

# Caller can pass flags to opt out of specific scopes — defaults remove all
# three so `cleanup` does the full "uninstall before clean install" pass in
# one shot. Flags use --keep-* so the destructive default is the no-flag form.
KEEP_BUNDLE=0
KEEP_DATA=0
KEEP_CACHE=0
for arg in "$@"; do
    case "$arg" in
        --keep-bundle) KEEP_BUNDLE=1 ;;
        --keep-data)   KEEP_DATA=1 ;;
        --keep-cache)  KEEP_CACHE=1 ;;
        --bundle-only) KEEP_DATA=1; KEEP_CACHE=1 ;;
        --data-only)   KEEP_BUNDLE=1; KEEP_CACHE=1 ;;
        -h|--help)
            cat <<EOF
Usage: cleanup [--keep-bundle] [--keep-data] [--keep-cache]
               [--bundle-only | --data-only]
Removes the installed Tauri app and its on-disk state in preparation for a
clean install. Reads INSTALL_DIR from the deploy settings and the identifier /
binary name from src-tauri/{tauri.conf.json,Cargo.toml}.

Optional config/deploy.env (or config/deploy.local.env) keys:
  BACKUP_FILES   Comma- or space-separated list of paths inside the app-data
                 dir to copy to <repo>/.cleanup-backups/<timestamp>/ BEFORE
                 the data wipe. Use for files the user would lose work over
                 (e.g. prompt_history.json). Honored only when app data is
                 being removed (i.e. --keep-data is not set).
EOF
            exit 0
            ;;
        *) echo "WARNING: unknown argument '$arg' (use --help)" ;;
    esac
done

echo "Project: ${PRODUCT_NAME:-$BIN_NAME}"
echo "Identifier: $IDENTIFIER"
# Normalize BACKUP_FILES (comma- or space-separated) into a bash array of
# items to copy out of $APP_DATA before it's deleted. Each entry is a path
# relative to the app-data dir (e.g. `prompt_history.json`, `db/scratch.sqlite`).
BACKUP_LIST=()
if [ "$KEEP_DATA" = "0" ] && [ -n "$BACKUP_FILES" ]; then
    # shellcheck disable=SC2206
    BACKUP_LIST=(${BACKUP_FILES//,/ })
fi

echo "Targets:"
[ "$KEEP_BUNDLE" = "0" ] && for d in "${DESTS[@]}"; do echo "  app:    $d"; done
[ "$KEEP_DATA" = "0" ]   && echo "  data:   $APP_DATA"
[ "$KEEP_CACHE" = "0" ]  && for c in "${CACHES[@]}"; do echo "  cache:  $c"; done
[ "${#BACKUP_LIST[@]}" -gt 0 ] && for f in "${BACKUP_LIST[@]}"; do echo "  backup: $APP_DATA/$f"; done

echo "=== Step 1: Stopping running app (if any)..."
case "$OS" in
    win)
        powershell.exe -Command "Get-Process '$PROC_NAME' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
        ;;
    mac)
        pkill -x "$BIN_NAME" 2>/dev/null \
            || osascript -e "quit app \"${PRODUCT_NAME:-$BIN_NAME}\"" 2>/dev/null \
            || true
        ;;
    linux)
        pkill -x "$BIN_NAME" 2>/dev/null || true
        ;;
esac
# Every scope below wants the app gone rather than merely signalled: `rm -rf` over the bundle unmaps
# the running process's binary, and app data or caches can still be written by a process that has not
# exited — so the wait does not depend on which scopes were asked for. Windows keeps a brief sleep:
# whether a handle outlives `Stop-Process` there is unmeasured, and `deploy-tauri.sh`'s Windows stop
# path carries the same open question.
case "$OS" in
    win) sleep 1 ;;
    *)   wait_for_app_exit "$PROC_NAME" "${PRODUCT_NAME:-$BIN_NAME}" || echo "  WARNING: it is still running — the removal below may fail." ;;
esac
echo "Done."

# remove_path is a small helper so each branch reports the same way: a `gone`
# line when the target existed and was removed, a `not present` line when it
# didn't — so the user can see at a glance whether prior state was actually
# wiped or there was nothing to remove.
remove_path() {
    local label="$1"
    local target="$2"
    if [ -z "$target" ]; then
        echo "  $label: (skipped — empty path)"
        return
    fi
    if [ -e "$target" ] || [ -L "$target" ]; then
        rm -rf "$target"
        echo "  $label: removed $target"
    else
        echo "  $label: not present ($target)"
    fi
}

echo "=== Step 2: Removing installed bundle..."
if [ "$KEEP_BUNDLE" = "0" ]; then
    for d in "${DESTS[@]}"; do
        remove_path "app   " "$d"
    done
else
    echo "  app   : skipped (--keep-bundle)"
fi
echo "Done."

# Backup runs *before* Step 3 wipes app data. POSIX `date` is fine here
# (cleanup is interactive — no resume-cache concerns like in workflow scripts).
# The destination is gitignored under .cleanup-backups/ so repeated runs don't
# leak into commits; each run gets its own timestamped subdir so older backups
# survive a fresh cleanup.
if [ "${#BACKUP_LIST[@]}" -gt 0 ] && [ -d "$APP_DATA" ]; then
    echo "=== Step 2.5: Backing up files from app data..."
    BACKUP_ROOT="$REPO_DIR/.cleanup-backups"
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
    BACKED_UP=0
    for rel in "${BACKUP_LIST[@]}"; do
        src="$APP_DATA/$rel"
        if [ -e "$src" ] || [ -L "$src" ]; then
            mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
            cp -R "$src" "$BACKUP_DIR/$rel"
            echo "  backup: $rel → $BACKUP_DIR/$rel"
            BACKED_UP=$((BACKED_UP + 1))
        else
            echo "  backup: $rel (not present in app data — skipped)"
        fi
    done
    if [ "$BACKED_UP" -eq 0 ]; then
        # Don't leave behind an empty timestamped dir.
        rmdir "$BACKUP_DIR" 2>/dev/null || true
    fi
    echo "Done."
fi

echo "=== Step 3: Removing app data + cache..."
if [ "$KEEP_DATA" = "0" ]; then
    remove_path "data  " "$APP_DATA"
else
    echo "  data  : skipped (--keep-data)"
fi
if [ "$KEEP_CACHE" = "0" ]; then
    for c in "${CACHES[@]}"; do
        remove_path "cache " "$c"
    done
else
    echo "  cache : skipped (--keep-cache)"
fi
echo "Done."

echo
echo "Cleanup complete. Run \`deploy\` to perform a clean install."
