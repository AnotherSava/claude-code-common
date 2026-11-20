#!/bin/bash
set -e

REPO_DIR="$(pwd)"

# Auto-detect project type
if [ -f "$REPO_DIR/package.json" ]; then
    # A fresh clone has no node_modules, and `npm run build` then fails with "<tool>: command not found".
    # A pull that changes the lockfile leaves node_modules stale: npm rewrites node_modules/.package-lock.json
    # on every install and git stamps a pulled file with the current time, so a newer lockfile means stale deps.
    if [ ! -d "$REPO_DIR/node_modules" ] || [ "$REPO_DIR/package-lock.json" -nt "$REPO_DIR/node_modules/.package-lock.json" ]; then
        echo "=== Installing dependencies (npm ci)..."
        npm ci
    fi
    BUILD_CMD="npm run build"
elif ls "$REPO_DIR"/src/*.csproj &>/dev/null; then
    BUILD_CMD="dotnet build src -c Release"
else
    echo "ERROR: Cannot auto-detect project type (no package.json or src/*.csproj)"
    exit 1
fi

echo "Build command: $BUILD_CMD"
echo "=== Building..."
eval "$BUILD_CMD"
echo "=== Build complete."
