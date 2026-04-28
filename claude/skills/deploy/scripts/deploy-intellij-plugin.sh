#!/bin/bash
set -e

START=${1:-1}
REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"

if [ -f "$DEPLOY_ENV" ]; then
    INSTALL_DIR=$(grep '^INSTALL_DIR=' "$DEPLOY_ENV" | cut -d= -f2-)
    IDE_PROCESS=$(grep '^IDE_PROCESS=' "$DEPLOY_ENV" | cut -d= -f2-)
    IDE_EXE=$(grep '^IDE_EXE=' "$DEPLOY_ENV" | cut -d= -f2-)
fi

if [ -z "$INSTALL_DIR" ]; then
    echo "ERROR: No INSTALL_DIR found in config/deploy.env"
    echo "Create config/deploy.env with: INSTALL_DIR=%APPDATA%/JetBrains/IntelliJIdea2026.1/plugins"
    exit 1
fi

# Expand %APPDATA% / ${APPDATA} so users can author portable paths.
expand_appdata() {
    local p="$1"
    p="${p//%APPDATA%/$APPDATA}"
    p="${p//\$\{APPDATA\}/$APPDATA}"
    echo "$p"
}
INSTALL_DIR=$(expand_appdata "$INSTALL_DIR")
IDE_EXE=$(expand_appdata "$IDE_EXE")

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
[ -n "$IDE_EXE" ] && echo "IDE executable: $IDE_EXE"

echo "=== Step 1: Stopping IDE (if running)..."
if [ -n "$IDE_PROCESS" ]; then
    powershell.exe -Command "Get-Process '$IDE_PROCESS' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
    sleep 1
    echo "Done."
else
    echo "Skipped (IDE_PROCESS not set). Close the IDE manually if the plugin is currently loaded."
fi

echo "=== Step 2: Building plugin zip..."
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
if [ ! -f "$IDE_EXE" ]; then
    echo "WARNING: IDE_EXE does not exist: $IDE_EXE"
    echo "Deploy complete, but the IDE was not started."
    exit 0
fi
powershell.exe -Command "Start-Process '$IDE_EXE' -WindowStyle Maximized"
echo "Done."
