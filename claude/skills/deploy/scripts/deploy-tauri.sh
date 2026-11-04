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
SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SKILLS/shared/deploy-config.sh"
source "$SKILLS/shared/app-process.sh"
source "$SKILLS/shared/tauri-project.sh"
REPO_DIR="$DEPLOY_REPO_DIR"
OS="$DEPLOY_OS"

# Settings come from config/deploy.env, with config/deploy.local.env over it (shared/deploy-config.sh):
#   INSTALL_DIR      optional; the per-OS default is /Applications or C:/Programs/<binary name>
#   CONFIG_DEST      where the app reads its config, e.g. %APP_CONFIG%/<identifier>/config.json. The config
#                    copied there is config/local.template.json rendered through Doppler when that template
#                    exists, else config/local.json.
#   DOPPLER_PROJECT, DOPPLER_CONFIG   where the secrets the template and SECRET_FIELDS name are read from
#   SECRET_FILE, SECRET_FIELDS        for an app that keeps settings of its own: the fields SECRET_FIELDS lists
#                    (dotted.path=SECRET_NAME, space-separated) are written into the existing SECRET_FILE and
#                    nothing else in it changes. See secret_fields.py.
CONFIG_DEST="$(deploy_get CONFIG_DEST)"
[ -n "$CONFIG_DEST" ] && CONFIG_DEST="$(deploy_expand "$CONFIG_DEST")"
DOPPLER_PROJECT="$(deploy_get DOPPLER_PROJECT)"
DOPPLER_CONFIG="$(deploy_get DOPPLER_CONFIG)"
SECRET_FILE="$(deploy_get SECRET_FILE)"
[ -n "$SECRET_FILE" ] && SECRET_FILE="$(deploy_expand "$SECRET_FILE")"
SECRET_FIELDS="$(deploy_get SECRET_FIELDS)"
TEMPLATE="$REPO_DIR/config/local.template.json"
if { [ -f "$TEMPLATE" ] || [ -n "$SECRET_FIELDS" ]; } && { [ -z "$DOPPLER_PROJECT" ] || [ -z "$DOPPLER_CONFIG" ]; }; then
    echo "ERROR: secrets are configured (config/local.template.json or SECRET_FIELDS) and config/deploy.env names no DOPPLER_PROJECT and DOPPLER_CONFIG to read them from."
    exit 1
fi
if [ -n "$SECRET_FIELDS" ] && [ -z "$SECRET_FILE" ]; then
    echo "ERROR: SECRET_FIELDS is set and SECRET_FILE, the settings file to write them into, is not."
    exit 1
fi
if { [ -f "$TEMPLATE" ] || [ -f "$REPO_DIR/config/local.json" ]; } && [ -z "$CONFIG_DEST" ]; then
    echo "ERROR: there is a config to deploy and config/deploy.env names no CONFIG_DEST to put it in."
    exit 1
fi

tauri_read_project "$REPO_DIR" || exit 1

INSTALL_DIR="$(deploy_install_dir "$BIN_NAME")"

# Pick the build artifact and the install target name per-OS.
PROC_NAME="$BIN_NAME"

# Resolve build outputs into BUILT_ARTIFACT / INSTALLED_NAME. On macOS this
# must run *after* `tauri build` since we prefer the .app bundle, which
# doesn't exist on a fresh checkout — calling this before the build would
# always fall through to the bare binary on first deploy.
select_built_artifact() {
    # A Cargo workspace builds into the workspace's target dir, not src-tauri/target, so ask
    # Cargo rather than assuming. Failing here beats installing a stale binary from the
    # other directory.
    local target_dir
    target_dir=$(cd "$REPO_DIR/src-tauri" && cargo metadata --format-version 1 --no-deps | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log(JSON.parse(s).target_directory))")
    if [ -z "$target_dir" ]; then
        echo "ERROR: cargo metadata did not report a target directory"
        exit 1
    fi
    [ "$OS" = "win" ] && target_dir=$(cygpath -u "$target_dir")
    case "$OS" in
        win)
            BUILT_ARTIFACT="$target_dir/release/$BIN_NAME.exe"
            INSTALLED_NAME="$(tauri_installed_name binary)"
            ;;
        mac)
            BUILT_BUNDLE="$target_dir/release/bundle/macos/$(tauri_installed_name bundle)"
            if [ -d "$BUILT_BUNDLE" ]; then
                BUILT_ARTIFACT="$BUILT_BUNDLE"
                INSTALLED_NAME="$(tauri_installed_name bundle)"
            else
                BUILT_ARTIFACT="$target_dir/release/$BIN_NAME"
                INSTALLED_NAME="$(tauri_installed_name binary)"
            fi
            ;;
        linux)
            BUILT_ARTIFACT="$target_dir/release/$BIN_NAME"
            INSTALLED_NAME="$(tauri_installed_name binary)"
            ;;
    esac
}

echo "Project: ${PRODUCT_NAME:-$BIN_NAME}"
echo "Deploying to: $INSTALL_DIR"

echo "=== Step 1: Building Tauri Release..."
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

# The secrets are read from Doppler before the app is stopped, so a Doppler that cannot answer (offline, an expired
# login, a SECRET_FILE the app has not written yet) fails the deploy with the old app still running. Writing them
# waits for Step 3, while the app is stopped, so it cannot save over what was just written. A rendered template is a
# plaintext copy of the secrets, so it exists only until Step 3 has copied it.
if [ -f "$TEMPLATE" ]; then
    RENDERED="$(mktemp)"
    trap 'rm -f "$RENDERED"' EXIT
    doppler secrets substitute "$TEMPLATE" --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" > "$RENDERED"
fi
if [ -n "$SECRET_FIELDS" ]; then
    # Word-split on purpose: SECRET_FIELDS is a space-separated list of dotted.path=NAME pairs.
    # shellcheck disable=SC2086
    "$DEPLOY_PY" "$SKILLS/deploy/scripts/secret_fields.py" --check "$SECRET_FILE" "$DOPPLER_PROJECT" "$DOPPLER_CONFIG" $SECRET_FIELDS
fi

echo "=== Step 2: Stopping running app (if any)..."
case "$OS" in
    win)
        powershell.exe -Command "Get-Process '$PROC_NAME' -ErrorAction SilentlyContinue | Stop-Process -Force" || true
        ;;
    mac)
        pkill -x "$BIN_NAME" 2>/dev/null \
            || osascript -e "quit app \"${PRODUCT_NAME:-$BIN_NAME}\"" 2>/dev/null \
            || true
        wait_for_app_exit "$PROC_NAME" "${PRODUCT_NAME:-$BIN_NAME}" || echo "  WARNING: it is still running — Step 3 is about to overwrite a live process."
        ;;
    linux)
        pkill -x "$BIN_NAME" 2>/dev/null || true
        wait_for_app_exit "$PROC_NAME" || echo "  WARNING: it is still running — Step 3 is about to overwrite a live process."
        ;;
esac
echo "Done."

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
if [ -f "$TEMPLATE" ] || [ -f "$REPO_DIR/config/local.json" ]; then
    mkdir -p "$(dirname "$CONFIG_DEST")"
    if [ -f "$TEMPLATE" ]; then
        cp -f "$RENDERED" "$CONFIG_DEST"
        rm -f "$RENDERED"
        echo "  Rendered config/local.template.json from Doppler $DOPPLER_PROJECT/$DOPPLER_CONFIG into $CONFIG_DEST"
    else
        cp -f "$REPO_DIR/config/local.json" "$CONFIG_DEST"
        echo "  Applied config/local.json to $CONFIG_DEST"
    fi
fi
if [ -n "$SECRET_FIELDS" ]; then
    # shellcheck disable=SC2086
    "$DEPLOY_PY" "$SKILLS/deploy/scripts/secret_fields.py" "$SECRET_FILE" "$DOPPLER_PROJECT" "$DOPPLER_CONFIG" $SECRET_FIELDS
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
        # A non-zero status here is not the outcome: LaunchServices reports -600 for a request it
        # went on to honour, so Step 5 decides whether the app started.
        open "$DEST" || echo "  open reported a failure — Step 5 checks whether the app started anyway."
        ;;
    linux)
        ( "$DEST" >/dev/null 2>&1 & )
        ;;
esac
echo "Done."

echo "=== Step 5: Verifying app started..."
if wait_for_app_start "$PROC_NAME"; then
    echo "$PROC_NAME is running. Deploy successful!"
else
    echo "ERROR: $PROC_NAME process not found."
    echo "       The build is installed at $DEST — start it by hand to see what it reports."
    exit 1
fi
