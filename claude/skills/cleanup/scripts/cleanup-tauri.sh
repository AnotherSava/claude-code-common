#!/bin/bash
set -e

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac

REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"

# INSTALL_DIR is read from the same deploy.env the deploy skill writes — so a
# user who ran `deploy` once and then runs `cleanup` doesn't need to repeat
# the per-machine config. If the file is missing or empty, fall back to the
# OS-default and warn; the bundle may have been installed manually.
if [ -f "$DEPLOY_ENV" ]; then
    INSTALL_DIR=$(grep '^INSTALL_DIR=' "$DEPLOY_ENV" | cut -d= -f2-)
    # BACKUP_FILES is a comma- or space-separated list of paths inside the
    # app-data dir to copy to <REPO_DIR>/.cleanup-backups/<timestamp>/ before
    # the data wipe. Set per-project in config/deploy.env for files the user
    # would lose work over — e.g. local prompt-history / scratch DBs.
    BACKUP_FILES=$(grep '^BACKUP_FILES=' "$DEPLOY_ENV" | cut -d= -f2-)
fi
if [ -z "$INSTALL_DIR" ]; then
    case "$OS" in
        win)   INSTALL_DIR="C:/Programs/$(basename "$REPO_DIR")" ;;
        mac)   INSTALL_DIR="/Applications" ;;
        linux) INSTALL_DIR="$HOME/.local/bin" ;;
    esac
    echo "WARNING: config/deploy.env missing or has no INSTALL_DIR; using fallback $INSTALL_DIR"
fi

case "$OS" in
    win)   APP_CONFIG_DIR="$APPDATA" ;;
    mac)   APP_CONFIG_DIR="$HOME/Library/Application Support" ;;
    linux) APP_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}" ;;
esac

expand_paths() {
    local p="$1"
    p="${p//%APP_CONFIG%/$APP_CONFIG_DIR}"
    p="${p//\$\{APP_CONFIG\}/$APP_CONFIG_DIR}"
    p="${p//%APPDATA%/$APP_CONFIG_DIR}"
    p="${p//\$\{APPDATA\}/$APP_CONFIG_DIR}"
    echo "$p"
}
INSTALL_DIR=$(expand_paths "$INSTALL_DIR")

TAURI_CONF="$REPO_DIR/src-tauri/tauri.conf.json"
CARGO_TOML="$REPO_DIR/src-tauri/Cargo.toml"

if [ ! -f "$TAURI_CONF" ]; then
    echo "ERROR: src-tauri/tauri.conf.json not found (run from Tauri project root)"
    exit 1
fi
if [ ! -f "$CARGO_TOML" ]; then
    echo "ERROR: src-tauri/Cargo.toml not found (run from Tauri project root)"
    exit 1
fi

PRODUCT_NAME=$(sed -n 's/.*"productName"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TAURI_CONF" | head -1)
IDENTIFIER=$(sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TAURI_CONF" | head -1)
BIN_NAME=$(sed -n '/^\[package\]/,/^\[/{ s/^name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p; }' "$CARGO_TOML" | head -1)

if [ -z "$IDENTIFIER" ]; then
    echo "ERROR: could not extract \"identifier\" from src-tauri/tauri.conf.json"
    exit 1
fi
if [ -z "$BIN_NAME" ]; then
    echo "ERROR: could not extract [package].name from src-tauri/Cargo.toml"
    exit 1
fi

PROC_NAME="$BIN_NAME"
case "$OS" in
    win)
        BUNDLE_NAME="$BIN_NAME.exe"
        APP_DATA="$APP_CONFIG_DIR/$IDENTIFIER"
        CACHES=("$LOCALAPPDATA/$IDENTIFIER")
        ;;
    mac)
        BUNDLE_NAME="${PRODUCT_NAME:-$BIN_NAME}.app"
        APP_DATA="$HOME/Library/Application Support/$IDENTIFIER"
        CACHES=("$HOME/Library/Caches/$IDENTIFIER")
        ;;
    linux)
        BUNDLE_NAME="$BIN_NAME"
        APP_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$IDENTIFIER"
        CACHES=("${XDG_CACHE_HOME:-$HOME/.cache}/$IDENTIFIER")
        ;;
esac

DEST="$INSTALL_DIR/$BUNDLE_NAME"

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
clean install. Reads INSTALL_DIR from config/deploy.env and the identifier /
binary name from src-tauri/{tauri.conf.json,Cargo.toml}.

Optional config/deploy.env keys:
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
[ "$KEEP_BUNDLE" = "0" ] && echo "  app:    $DEST"
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
# Wait briefly so the next rm doesn't race the running process's mmap'd binary.
sleep 1
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
    remove_path "app   " "$DEST"
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
