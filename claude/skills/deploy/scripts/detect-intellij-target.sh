#!/bin/bash
# Detects IntelliJ plugin deploy defaults by parsing build.gradle[.kts] and the local machine.
# Usage: detect-intellij-target.sh <field>
#   field: type | plugins-dir | ide-exe | ide-process
# Prints a single value (or empty line if unknown). Never errors out.

set -u

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac

FIELD="${1:-type}"
GRADLE_FILES=""
[ -f build.gradle.kts ] && GRADLE_FILES="build.gradle.kts"
[ -f build.gradle ] && GRADLE_FILES="$GRADLE_FILES build.gradle"

# Extract the IntelliJ platform type. Covers both the 2.x plugin
# (IntelliJPlatformType.X) and the 1.x plugin (type = "IC"/"IU"/...).
TYPE=""
if [ -n "$GRADLE_FILES" ]; then
    TYPE=$(grep -hoE 'IntelliJPlatformType\.[A-Za-z]+' $GRADLE_FILES 2>/dev/null | head -1 | cut -d. -f2)
    if [ -z "$TYPE" ]; then
        CODE=$(grep -hoE 'type[[:space:]]*=[[:space:]]*"[A-Z]{2,3}"' $GRADLE_FILES 2>/dev/null | head -1 | sed -E 's/.*"([A-Z]+)".*/\1/')
        case "$CODE" in
            IC) TYPE="IntellijIdeaCommunity" ;;
            IU) TYPE="IntellijIdeaUltimate" ;;
            PC) TYPE="PyCharmCommunity" ;;
            PY) TYPE="PyCharmProfessional" ;;
            WS) TYPE="WebStorm" ;;
            RD) TYPE="Rider" ;;
            GO) TYPE="GoLand" ;;
            CL) TYPE="CLion" ;;
            DB) TYPE="DataGrip" ;;
            RM) TYPE="RubyMine" ;;
            RR) TYPE="RustRover" ;;
            PS) TYPE="PhpStorm" ;;
            AI) TYPE="AndroidStudio" ;;
        esac
    fi
fi

# Map platform type to config-dir prefix regex (alternation), Windows process name,
# Windows exe basename, and macOS .app bundle name candidates (alternation).
case "$TYPE" in
    IntellijIdeaCommunity)  PREFIX="IdeaIC|IntelliJIdea"; PROC="idea64"; EXE_NAME="idea64"; APP_NAMES="IntelliJ IDEA CE|IntelliJ IDEA Community Edition" ;;
    IntellijIdeaUltimate)   PREFIX="IntelliJIdea";       PROC="idea64"; EXE_NAME="idea64"; APP_NAMES="IntelliJ IDEA|IntelliJ IDEA Ultimate" ;;
    PyCharmCommunity)       PREFIX="PyCharmCE|PyCharm";  PROC="pycharm64"; EXE_NAME="pycharm64"; APP_NAMES="PyCharm CE|PyCharm Community Edition" ;;
    PyCharmProfessional)    PREFIX="PyCharm";            PROC="pycharm64"; EXE_NAME="pycharm64"; APP_NAMES="PyCharm|PyCharm Professional Edition" ;;
    WebStorm)               PREFIX="WebStorm";           PROC="webstorm64"; EXE_NAME="webstorm64"; APP_NAMES="WebStorm" ;;
    Rider)                  PREFIX="Rider";              PROC="rider64"; EXE_NAME="rider64"; APP_NAMES="Rider|JetBrains Rider" ;;
    GoLand)                 PREFIX="GoLand";             PROC="goland64"; EXE_NAME="goland64"; APP_NAMES="GoLand" ;;
    CLion)                  PREFIX="CLion";              PROC="clion64"; EXE_NAME="clion64"; APP_NAMES="CLion" ;;
    DataGrip)               PREFIX="DataGrip";           PROC="datagrip64"; EXE_NAME="datagrip64"; APP_NAMES="DataGrip" ;;
    RubyMine)               PREFIX="RubyMine";           PROC="rubymine64"; EXE_NAME="rubymine64"; APP_NAMES="RubyMine" ;;
    RustRover)              PREFIX="RustRover";          PROC="rustrover64"; EXE_NAME="rustrover64"; APP_NAMES="RustRover" ;;
    PhpStorm)               PREFIX="PhpStorm";           PROC="phpstorm64"; EXE_NAME="phpstorm64"; APP_NAMES="PhpStorm" ;;
    AndroidStudio)          PREFIX="AndroidStudio|Google/AndroidStudio"; PROC="studio64"; EXE_NAME="studio64"; APP_NAMES="Android Studio" ;;
    *)                      PREFIX=""; PROC=""; EXE_NAME=""; APP_NAMES="" ;;
esac

# On macOS, IDE process names drop the trailing "64".
if [ "$OS" = "mac" ] && [ -n "$PROC" ]; then
    PROC="${PROC%64}"
fi

config_base() {
    case "$OS" in
        win)   echo "${APPDATA:-}/JetBrains" ;;
        mac)   echo "$HOME/Library/Application Support/JetBrains" ;;
        linux) echo "${XDG_CONFIG_HOME:-$HOME/.config}/JetBrains" ;;
    esac
}

pick_config_dir() {
    local base
    base=$(config_base)
    [ -d "$base" ] || return
    if [ -n "$PREFIX" ]; then
        ls -t "$base" 2>/dev/null | grep -iE "^($PREFIX)[0-9]" | head -1
    else
        # Unknown type: fall back to newest IntelliJ IDEA dir of either edition.
        ls -t "$base" 2>/dev/null | grep -iE '^(IntelliJIdea|IdeaIC)[0-9]' | head -1
    fi
}

pick_ide_exe() {
    local found=""
    case "$OS" in
        win)
            [ -z "$EXE_NAME" ] && return
            found=$(ls -t \
                "${LOCALAPPDATA:-}/Programs/"*/bin/"$EXE_NAME".exe \
                "${PROGRAMFILES:-}/JetBrains/"*/bin/"$EXE_NAME".exe \
                "${LOCALAPPDATA:-}/JetBrains/Toolbox/apps/"*/bin/"$EXE_NAME".exe \
                2>/dev/null | head -1)
            # Normalise to forward slashes for config consistency.
            echo "$found" | tr '\\' '/'
            ;;
        mac)
            [ -z "$APP_NAMES" ] && return
            local IFS='|'
            local name
            for name in $APP_NAMES; do
                for path in \
                    "/Applications/$name.app" \
                    "$HOME/Applications/$name.app" \
                    "$HOME/Applications/JetBrains Toolbox/$name.app" \
                    "$HOME/Library/Application Support/JetBrains/Toolbox/apps"/*/"$name.app"
                do
                    if [ -d "$path" ]; then
                        found="$path"
                        break 2
                    fi
                done
            done
            echo "$found"
            ;;
        linux)
            # No standard install path on Linux; leave empty for the user to fill in.
            return
            ;;
    esac
}

case "$FIELD" in
    type)
        echo "${TYPE:-unknown}"
        ;;
    plugins-dir)
        DIR=$(pick_config_dir)
        if [ -n "$DIR" ]; then
            # Emit the cross-platform %APP_CONFIG% placeholder so the same
            # INSTALL_DIR= line resolves on whichever machine reads deploy.env.
            echo "%APP_CONFIG%/JetBrains/$DIR/plugins"
        fi
        ;;
    ide-exe)
        pick_ide_exe
        ;;
    ide-process)
        echo "$PROC"
        ;;
    *)
        echo "Usage: $0 {type|plugins-dir|ide-exe|ide-process}" >&2
        exit 2
        ;;
esac
