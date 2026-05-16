#!/bin/bash
set -e

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac

# Ensure cargo (rustup's default location) is on PATH — bash on Windows
# often does not inherit the user's PATH additions.
if ! command -v cargo >/dev/null 2>&1; then
    if [ -x "$HOME/.cargo/bin/cargo.exe" ] || [ -x "$HOME/.cargo/bin/cargo" ]; then
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
fi

START=${1:-1}
REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"

# Read settings from deploy.env
if [ -f "$DEPLOY_ENV" ]; then
    INSTALL_DIR=$(grep '^INSTALL_DIR=' "$DEPLOY_ENV" | cut -d= -f2-)
    CONFIG_DEST=$(grep '^CONFIG_DEST=' "$DEPLOY_ENV" | cut -d= -f2-)
fi

if [ -z "$INSTALL_DIR" ]; then
    echo "ERROR: No INSTALL_DIR found in config/deploy.env"
    if [ "$OS" = "mac" ]; then
        echo "Create config/deploy.env with: INSTALL_DIR=/Applications/your-app"
    else
        echo "Create config/deploy.env with: INSTALL_DIR=C:/Programs/your-app"
    fi
    exit 1
fi

# Per-OS user config dir for placeholder expansion below.
case "$OS" in
    win)   APP_CONFIG_DIR="$APPDATA" ;;
    mac)   APP_CONFIG_DIR="$HOME/Library/Application Support" ;;
    linux) APP_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}" ;;
esac

# Expand %APP_CONFIG% (canonical, cross-platform) and %APPDATA% (legacy alias,
# kept so existing Windows-authored deploy.env files still resolve on macOS).
expand_paths() {
    local p="$1"
    p="${p//%APP_CONFIG%/$APP_CONFIG_DIR}"
    p="${p//\$\{APP_CONFIG\}/$APP_CONFIG_DIR}"
    p="${p//%APPDATA%/$APP_CONFIG_DIR}"
    p="${p//\$\{APPDATA\}/$APP_CONFIG_DIR}"
    echo "$p"
}
INSTALL_DIR=$(expand_paths "$INSTALL_DIR")
[ -n "$CONFIG_DEST" ] && CONFIG_DEST=$(expand_paths "$CONFIG_DEST")

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

# productName from tauri.conf.json (display only); binary name from Cargo [package].name
PRODUCT_NAME=$(sed -n 's/.*"productName"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TAURI_CONF" | head -1)
BIN_NAME=$(sed -n '/^\[package\]/,/^\[/{ s/^name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p; }' "$CARGO_TOML" | head -1)

if [ -z "$BIN_NAME" ]; then
    echo "ERROR: could not extract [package].name from src-tauri/Cargo.toml"
    exit 1
fi

# Pick the build artifact and the install target name per-OS.
PROC_NAME="$BIN_NAME"

# Resolve build outputs into BUILT_ARTIFACT / INSTALLED_NAME. On macOS this
# must run *after* `tauri build` since we prefer the .app bundle, which
# doesn't exist on a fresh checkout — calling this before the build would
# always fall through to the bare binary on first deploy.
select_built_artifact() {
    case "$OS" in
        win)
            BUILT_ARTIFACT="$REPO_DIR/src-tauri/target/release/$BIN_NAME.exe"
            INSTALLED_NAME="$BIN_NAME.exe"
            ;;
        mac)
            BUNDLE_NAME="${PRODUCT_NAME:-$BIN_NAME}.app"
            BUILT_BUNDLE="$REPO_DIR/src-tauri/target/release/bundle/macos/$BUNDLE_NAME"
            BUILT_BIN="$REPO_DIR/src-tauri/target/release/$BIN_NAME"
            if [ -d "$BUILT_BUNDLE" ]; then
                BUILT_ARTIFACT="$BUILT_BUNDLE"
                INSTALLED_NAME="$BUNDLE_NAME"
            else
                BUILT_ARTIFACT="$BUILT_BIN"
                INSTALLED_NAME="$BIN_NAME"
            fi
            ;;
        linux)
            BUILT_ARTIFACT="$REPO_DIR/src-tauri/target/release/$BIN_NAME"
            INSTALLED_NAME="$BIN_NAME"
            ;;
    esac
}

echo "Project: ${PRODUCT_NAME:-$BIN_NAME}"
echo "Deploying to: $INSTALL_DIR"

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
echo "Done."

echo "=== Step 2: Building Tauri Release..."
# Skip the macOS .dmg target: deploy copies the .app from target/release/bundle/macos/
# directly into INSTALL_DIR, so the DMG is wasted work — and `bundle_dmg.sh` mounts the
# DMG, which auto-opens (and then closes) its "drag-to-Applications" Finder window every
# build. On Windows / Linux this is a no-op (no DMG target there); on macOS the .app
# bundle is what we actually need.
case "$OS" in
    mac) npm run tauri -- build --bundles app ;;
    *)   npm run tauri -- build ;;
esac
echo "Done."

select_built_artifact
echo "Artifact: $(basename "$BUILT_ARTIFACT")"
if [ ! -e "$BUILT_ARTIFACT" ]; then
    echo "ERROR: build output not found at $BUILT_ARTIFACT"
    exit 1
fi

echo "=== Step 3: Deploying to install directory..."
mkdir -p "$INSTALL_DIR"
DEST="$INSTALL_DIR/$INSTALLED_NAME"
if [ -d "$BUILT_ARTIFACT" ]; then
    rm -rf "$DEST"
    cp -R "$BUILT_ARTIFACT" "$DEST"
else
    rm -f "$DEST"
    cp -f "$BUILT_ARTIFACT" "$DEST"
fi
if [ -f "$REPO_DIR/config/local.json" ]; then
    if [ -n "$CONFIG_DEST" ]; then
        mkdir -p "$(dirname "$CONFIG_DEST")"
        cp -f "$REPO_DIR/config/local.json" "$CONFIG_DEST"
        echo "  Applied config/local.json to $CONFIG_DEST"
    else
        echo "  WARNING: config/local.json exists but CONFIG_DEST is not set in config/deploy.env."
        echo "           The override was not deployed. Re-run the deploy skill to configure CONFIG_DEST."
    fi
fi
echo "Done."

if [ "$START" = "0" ]; then
    echo "Deploy complete (app not started)."
    exit 0
fi

echo "=== Step 4: Launching app..."
case "$OS" in
    win)
        powershell.exe -Command "Start-Process '$INSTALL_DIR\\$INSTALLED_NAME'"
        ;;
    mac)
        open "$DEST"
        ;;
    linux)
        ( "$DEST" >/dev/null 2>&1 & )
        ;;
esac
echo "Done."

echo "=== Step 5: Verifying app started..."
sleep 2
case "$OS" in
    win)
        if powershell.exe -Command "Get-Process '$PROC_NAME' -ErrorAction Stop" > /dev/null 2>&1; then
            echo "$BIN_NAME is running. Deploy successful!"
        else
            echo "ERROR: $BIN_NAME process not found."
            exit 1
        fi
        ;;
    mac|linux)
        if pgrep -x "$BIN_NAME" >/dev/null; then
            echo "$BIN_NAME is running. Deploy successful!"
        else
            echo "ERROR: $BIN_NAME process not found."
            exit 1
        fi
        ;;
esac
