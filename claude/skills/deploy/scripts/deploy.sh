#!/bin/bash
set -e

START=${1:-1}
REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"

# Read install dir from deploy.env
if [ -f "$DEPLOY_ENV" ]; then
    INSTALL_DIR=$(grep '^INSTALL_DIR=' "$DEPLOY_ENV" | cut -d= -f2-)
fi

if [ -z "$INSTALL_DIR" ]; then
    echo "ERROR: No INSTALL_DIR found in config/deploy.env"
    echo "Create config/deploy.env with: INSTALL_DIR=C:/Programs/your-app"
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

echo "Project: $ASSEMBLY_NAME"
echo "Deploying to: $INSTALL_DIR"

echo "=== Step 1: Stopping running app (if any)..."
powershell.exe -Command "Get-Process '$ASSEMBLY_NAME' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
echo "Done."

echo "=== Step 2: Building Release publish..."
rm -rf "$REPO_DIR/src/bin/publish"
dotnet publish "$REPO_DIR/src" -c Release -o "$REPO_DIR/src/bin/publish"
echo "Done."

echo "=== Step 3: Deploying to install directory..."
mkdir -p "$INSTALL_DIR"
rm -f "$INSTALL_DIR"/*
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
sleep 2
if powershell.exe -Command "Get-Process '$ASSEMBLY_NAME' -ErrorAction Stop" > /dev/null 2>&1; then
    echo "$ASSEMBLY_NAME is running. Deploy successful!"
else
    echo "ERROR: $ASSEMBLY_NAME process not found."
    exit 1
fi
