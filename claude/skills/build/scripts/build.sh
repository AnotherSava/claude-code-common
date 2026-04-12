#!/bin/bash
set -e

REPO_DIR="$(pwd)"

# Auto-detect project type
if [ -f "$REPO_DIR/package.json" ]; then
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
