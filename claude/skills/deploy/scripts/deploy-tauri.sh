#!/bin/bash
set -e

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
    echo "Create config/deploy.env with: INSTALL_DIR=C:/Programs/your-app"
    exit 1
fi

# Expand %APPDATA% (and ${APPDATA}) to the runtime value so users can author a
# portable CONFIG_DEST without hardcoding per-machine paths.
if [ -n "$CONFIG_DEST" ]; then
    CONFIG_DEST="${CONFIG_DEST//%APPDATA%/$APPDATA}"
    CONFIG_DEST="${CONFIG_DEST//\$\{APPDATA\}/$APPDATA}"
fi

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

# Windows Get-Process matches the executable name without .exe
PROC_NAME="$BIN_NAME"
BUILT_EXE="$REPO_DIR/src-tauri/target/release/$BIN_NAME.exe"

echo "Project: ${PRODUCT_NAME:-$BIN_NAME}"
echo "Binary:  $BIN_NAME.exe"
echo "Deploying to: $INSTALL_DIR"

echo "=== Step 1: Stopping running app (if any)..."
powershell.exe -Command "Get-Process '$PROC_NAME' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
echo "Done."

echo "=== Step 2: Building Tauri Release..."
npm run tauri -- build
echo "Done."

if [ ! -f "$BUILT_EXE" ]; then
    echo "ERROR: build output not found at $BUILT_EXE"
    exit 1
fi

echo "=== Step 3: Deploying to install directory..."
mkdir -p "$INSTALL_DIR"
rm -f "$INSTALL_DIR/$BIN_NAME.exe"
cp -f "$BUILT_EXE" "$INSTALL_DIR/"
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
powershell.exe -Command "Start-Process '$INSTALL_DIR\\$BIN_NAME.exe'"
echo "Done."

echo "=== Step 5: Verifying app started..."
sleep 2
if powershell.exe -Command "Get-Process '$PROC_NAME' -ErrorAction Stop" > /dev/null 2>&1; then
    echo "$BIN_NAME is running. Deploy successful!"
else
    echo "ERROR: $BIN_NAME process not found."
    exit 1
fi
