#!/bin/bash
set -e

START=${1:-1}
SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"
source "$SKILLS/shared/app-process.sh"
REPO_DIR="$DEPLOY_REPO_DIR"
OS="$DEPLOY_OS"

# INSTALL_DIR is the IDE's plugins directory, which names the IDE version, so it usually differs between
# machines and lives in config/deploy.local.env. The IDE_* keys likewise.
INSTALL_DIR="$(deploy_get INSTALL_DIR)"
IDE_PROCESS="$(deploy_get IDE_PROCESS)"
IDE_EXE="$(deploy_get IDE_EXE)"
IDE_BUNDLE_ID="$(deploy_get IDE_BUNDLE_ID)"

if [ -z "$INSTALL_DIR" ]; then
    echo "ERROR: No INSTALL_DIR found in config/deploy.local.env or config/deploy.env"
    echo "Set it in config/deploy.local.env, e.g.: INSTALL_DIR=%APP_CONFIG%/JetBrains/IntelliJIdea2026.1/plugins"
    exit 1
fi
INSTALL_DIR="$(deploy_expand "$INSTALL_DIR")"
[ -n "$IDE_EXE" ] && IDE_EXE="$(deploy_expand "$IDE_EXE")"

BUILD_GRADLE="$REPO_DIR/build.gradle.kts"
if [ ! -f "$BUILD_GRADLE" ] && [ ! -f "$REPO_DIR/build.gradle" ]; then
    echo "ERROR: build.gradle[.kts] not found (run from Gradle project root)"
    exit 1
fi

# Pick gradle invoker: wrapper if present, else system gradle.
if [ -f "$REPO_DIR/gradlew" ]; then
    GRADLE_CMD="bash $REPO_DIR/gradlew"
elif command -v gradle >/dev/null 2>&1; then
    GRADLE_CMD="gradle --no-daemon"
else
    echo "ERROR: no gradle wrapper (gradlew) and no 'gradle' on PATH"
    exit 1
fi

echo "Project: $(basename "$REPO_DIR")"
echo "Plugins dir: $INSTALL_DIR"
[ -n "$IDE_PROCESS" ] && echo "IDE process: $IDE_PROCESS"
[ -n "$IDE_BUNDLE_ID" ] && echo "IDE bundle id: $IDE_BUNDLE_ID"
[ -n "$IDE_EXE" ] && echo "IDE executable: $IDE_EXE"

echo "=== Step 1: Building plugin zip..."
$GRADLE_CMD buildPlugin
echo "Done."

PLUGIN_ZIP=$(ls -t "$REPO_DIR/build/distributions"/*.zip 2>/dev/null | head -1)
if [ -z "$PLUGIN_ZIP" ] || [ ! -f "$PLUGIN_ZIP" ]; then
    echo "ERROR: no plugin zip found under build/distributions/"
    exit 1
fi
echo "Built: $PLUGIN_ZIP"

# Top-level directory name inside the zip == plugin folder name in plugins dir.
PLUGIN_DIR_NAME=$(unzip -Z1 "$PLUGIN_ZIP" | head -1 | cut -d/ -f1)
if [ -z "$PLUGIN_DIR_NAME" ]; then
    echo "ERROR: could not determine plugin directory name from $PLUGIN_ZIP"
    exit 1
fi

echo "=== Step 2: Stopping IDE (if running)..."
case "$OS" in
    win)
        if [ -n "$IDE_PROCESS" ]; then
            powershell.exe -Command "Get-Process '$IDE_PROCESS' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
            sleep 1
            echo "Done."
        else
            echo "Skipped (IDE_PROCESS not set). Close the IDE manually if the plugin is currently loaded."
        fi
        ;;
    mac|linux)
        stopped=0
        if [ "$OS" = "mac" ] && [ -n "$IDE_BUNDLE_ID" ]; then
            osascript -e "tell application id \"$IDE_BUNDLE_ID\" to quit" 2>/dev/null || true
            stopped=1
        elif [ -n "$IDE_PROCESS" ]; then
            pkill -f "$IDE_PROCESS" 2>/dev/null || true
            stopped=1
        else
            echo "Skipped (IDE_BUNDLE_ID / IDE_PROCESS not set). Close the IDE manually if the plugin is currently loaded."
        fi
        # Verify the IDE actually exited. The macOS osascript-quit can be vetoed
        # by a "Quit IntelliJ IDEA?" confirmation dialog (returns -128 "User
        # canceled"); without this check the install step would race a live IDE.
        if [ "$stopped" = "1" ] && [ -n "$IDE_PROCESS" ]; then
            wait_for_app_exit "$IDE_PROCESS" "IDE" || echo "  WARNING: the IDE is still running — the install below will race it."
            echo "Done."
        elif [ "$stopped" = "1" ]; then
            sleep 1
            echo "Done."
        fi
        ;;
esac

echo "=== Step 3: Installing into plugins dir..."
mkdir -p "$INSTALL_DIR"
if [ -d "$INSTALL_DIR/$PLUGIN_DIR_NAME" ]; then
    rm -rf "$INSTALL_DIR/$PLUGIN_DIR_NAME"
fi
unzip -q -o "$PLUGIN_ZIP" -d "$INSTALL_DIR"
echo "Installed to: $INSTALL_DIR/$PLUGIN_DIR_NAME"

if [ "$START" = "0" ]; then
    echo "Deploy complete (IDE not started)."
    exit 0
fi

if [ -z "$IDE_EXE" ]; then
    echo "Deploy complete. IDE_EXE not set — start your IDE manually to load the plugin."
    exit 0
fi

echo "=== Step 4: Launching IDE..."
case "$OS" in
    win)
        if [ ! -f "$IDE_EXE" ]; then
            echo "WARNING: IDE_EXE does not exist: $IDE_EXE"
            echo "Deploy complete, but the IDE was not started."
            exit 0
        fi
        powershell.exe -Command "Start-Process '$IDE_EXE' -WindowStyle Maximized"
        ;;
    mac)
        if [ ! -e "$IDE_EXE" ]; then
            echo "WARNING: IDE_EXE does not exist: $IDE_EXE"
            echo "Deploy complete, but the IDE was not started."
            exit 0
        fi
        open -a "$IDE_EXE"
        ;;
    linux)
        if [ ! -x "$IDE_EXE" ]; then
            echo "WARNING: IDE_EXE not executable: $IDE_EXE"
            echo "Deploy complete, but the IDE was not started."
            exit 0
        fi
        ( "$IDE_EXE" >/dev/null 2>&1 & )
        ;;
esac
echo "Done."
