#!/bin/bash
set -e

START=${1:-1}
SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"
source "$SKILLS/shared/app-process.sh"
REPO_DIR="$DEPLOY_REPO_DIR"
OS="$DEPLOY_OS"

if [ "$OS" != "win" ]; then
    echo "deploy.sh (.NET tray app) is Windows-only — current OS: $OS"
    exit 1
fi

# Find the .csproj in src/ and extract AssemblyName
CSPROJ=$(ls "$REPO_DIR"/src/*.csproj 2>/dev/null | head -1)
if [ -z "$CSPROJ" ]; then
    echo "ERROR: No .csproj found in src/"
    exit 1
fi

ASSEMBLY_NAME=$(sed -n 's/.*<AssemblyName>\([^<]*\)<.*/\1/p' "$CSPROJ")
if [ -z "$ASSEMBLY_NAME" ]; then
    ASSEMBLY_NAME=$(basename "$CSPROJ" .csproj)
fi

# INSTALL_DIR from config/deploy.env or config/deploy.local.env; C:/Programs/<assembly name> when neither sets it.
INSTALL_DIR="$(deploy_install_dir "$ASSEMBLY_NAME")"

echo "Project: $ASSEMBLY_NAME"
echo "Deploying to: $INSTALL_DIR"

echo "=== Step 1: Building Release publish..."
rm -rf "$REPO_DIR/src/bin/publish"
dotnet publish "$REPO_DIR/src" -c Release -o "$REPO_DIR/src/bin/publish"
echo "Done."

echo "=== Step 2: Stopping running app (if any)..."
powershell.exe -Command "Get-Process '$ASSEMBLY_NAME' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
echo "Done."

echo "=== Step 3: Deploying to install directory..."
mkdir -p "$INSTALL_DIR"
# Top-level files only. A subdirectory can hold what another repo installed here (plugins), and `rm` on
# one fails, which under `set -e` aborts after the app's files are gone and before the new ones land.
for entry in "$INSTALL_DIR"/*; do
    [ -d "$entry" ] || rm -f "$entry"
done
cp -rf "$REPO_DIR/src/bin/publish"/* "$INSTALL_DIR/"
if [ -f "$REPO_DIR/config/local.json" ]; then
    echo "  Applying config/local.json override..."
    cp -f "$REPO_DIR/config/local.json" "$INSTALL_DIR/config.json"
fi
echo "Done."

if [ "$START" = "0" ]; then
    echo "Deploy complete (app not started)."
    exit 0
fi

echo "=== Step 4: Launching app..."
powershell.exe -Command "Start-Process '$INSTALL_DIR\\$ASSEMBLY_NAME.exe'"
echo "Done."

echo "=== Step 5: Verifying app started..."
if wait_for_app_start "$ASSEMBLY_NAME"; then
    echo "$ASSEMBLY_NAME is running. Deploy successful!"
else
    echo "ERROR: $ASSEMBLY_NAME process not found."
    echo "       The build is installed at $INSTALL_DIR — start it by hand to see what it reports."
    exit 1
fi
