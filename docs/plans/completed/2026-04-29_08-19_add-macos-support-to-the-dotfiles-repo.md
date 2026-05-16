# Add macOS support to the dotfiles repo

## Context

This repo (`Projects/claude`) is symlinked to `~/.claude/` and `~/.git-hooks/` on every machine that uses it. So far it has been used only on Windows; the install path, deploy scripts, default paths, global rules, and one memory file all assume Git Bash + PowerShell + drive-letter paths. The user now wants to use it on macOS too — without forking the repo.

Goal: make the repo work *unchanged* on a macOS machine. Anything that genuinely can't be cross-platform stays Windows-only with a clean early-exit guard. The README and `claude/CLAUDE.md` already have a Linux/macOS branch for the symlink install commands, so the install path itself is already covered — the work is in scripts, defaults, rules, and a few docs.

User's scoping decisions (from earlier Q&A):
- **Deploy:** Tauri and IntelliJ scripts get cross-platform support; `.NET` deploy stays Windows-only with a guard.
- **`claude/CLAUDE.md`:** rewrite Windows-only rules as platform-conditional.
- **Memory `reference_claude_dotfiles_repo.md`:** generalize to drop the hardcoded `D:/projects/claude` path and show both PowerShell and bash env-var commands.

## Files to modify

### 1. Deploy scripts — make Tauri + IntelliJ cross-platform

All three scripts gain an OS-detect block at the top:

```bash
case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac
```

#### `claude/skills/deploy/scripts/deploy.sh` (.NET — Windows-only)
- Add `[ "$OS" = mac ] && { echo "deploy.sh (.NET tray app) is Windows-only"; exit 1; }` near the top, after OS detection. Leaves the rest of the script untouched.

#### `claude/skills/deploy/scripts/deploy-tauri.sh`
- Replace the hardcoded `BUILT_EXE=...$BIN_NAME.exe` with an OS-aware block. Both branches resolve paths relative to `$REPO_DIR` (the project root the script is invoked from):
  - Win: `BUILT_EXE="$REPO_DIR/src-tauri/target/release/$BIN_NAME.exe"`; install to `$INSTALL_DIR/$BIN_NAME.exe`.
  - Mac: prefer the `.app` bundle at `$REPO_DIR/src-tauri/target/release/bundle/macos/<productName>.app`; fall back to the raw binary `$REPO_DIR/src-tauri/target/release/$BIN_NAME`.
- Replace `powershell.exe -Command "Get-Process … | Stop-Process -Force"` with:
  - Win: keep the existing PowerShell call.
  - Mac: `pkill -x "$BIN_NAME" 2>/dev/null || osascript -e "quit app \"$PRODUCT_NAME\"" 2>/dev/null || true`.
- Replace `Start-Process` launch with:
  - Mac: `open "$INSTALL_DIR/<bundle or binary>"`.
- Replace verification (`Get-Process …`) with:
  - Mac: `pgrep -x "$BIN_NAME" >/dev/null`.
- Introduce a cross-platform placeholder for the per-user config directory. The current scripts only recognize `%APPDATA%` / `${APPDATA}`, which is a Windows variable name and reads as a foreign concept on macOS. Rename the canonical placeholder to **`%APP_CONFIG%`** (and `${APP_CONFIG}`) and resolve it per-OS:
  - Win: `${APP_CONFIG} = $APPDATA` (i.e. `~/AppData/Roaming`).
  - Mac: `${APP_CONFIG} = $HOME/Library/Application Support`.
  - Linux: `${APP_CONFIG} = ${XDG_CONFIG_HOME:-$HOME/.config}` (in case this skill is ever invoked there).
- Keep `%APPDATA%` / `${APPDATA}` as a back-compat alias that expands to the same `${APP_CONFIG}` value on every OS, so existing `deploy.env` files copied over from the Windows machine still resolve. Add a one-line comment in the script noting that `%APPDATA%` is retained for legacy configs and `%APP_CONFIG%` is the preferred form going forward.

#### `claude/skills/deploy/scripts/deploy-intellij-plugin.sh`
- Same OS-detect prelude.
- Stop IDE: replace PowerShell call with mac branch `osascript -e "tell application id \"$IDE_BUNDLE_ID\" to quit"` *or* `pkill -f "$IDE_PROCESS"` (use bundle id if `IDE_BUNDLE_ID` env var is set, else fall back to `pkill`).
- Launch IDE: replace `Start-Process` with mac branch `open -a "$IDE_EXE"` (where `IDE_EXE` on mac is the `.app` path, e.g. `/Applications/IntelliJ IDEA.app`).
- `INSTALL_DIR` expansion: handle the `%APP_CONFIG%` placeholder (and `%APPDATA%` back-compat alias) the same way as the Tauri script.

#### `claude/skills/deploy/scripts/detect-intellij-target.sh`
- Add OS detect at top.
- `pick_config_dir`: branch on OS. Windows already uses `$APPDATA/JetBrains`; mac uses `$HOME/Library/Application Support/JetBrains`.
- `pick_ide_exe`: branch on OS.
  - Win: keep the existing `LOCALAPPDATA`/`PROGRAMFILES`/Toolbox `.exe` search.
  - Mac: search `/Applications/<NameVariants>.app`, `$HOME/Applications/JetBrains Toolbox/<IDE>.app`, and `$HOME/Library/Application Support/JetBrains/Toolbox/apps/*/<IDE>.app`. Print the `.app` path with forward slashes.
- The `PROC` mapping needs a mac variant (no `64` suffix on macOS):
  - `idea64` → `idea` on mac, etc. Add a parallel mac case in the existing `case "$TYPE"` block, or compute mac process name as the win value with `64` stripped.
- The `plugins-dir` output should switch to the new `%APP_CONFIG%/JetBrains/<DIR>/plugins` literal on **both** OSes (replacing the old `%APPDATA%/...` literal on Windows). Emitting the cross-platform placeholder means the same `INSTALL_DIR=` line works regardless of which machine the user later edits `deploy.env` on.

### 2. `claude/skills/deploy/SKILL.md` — defaults

Update the default-suggestions in **Step 2** so they're OS-aware. `Context` block already provides the `Detect…` invocations, which now return mac paths; the SKILL.md text needs:
- **Tauri / .NET INSTALL_DIR default:** state both: "`C:/Programs/<project>` on Windows, `/Applications/<project>` on macOS".
- **IntelliJ INSTALL_DIR fallback:** suggest the cross-platform placeholder form `%APP_CONFIG%/JetBrains/IntelliJIdea<newest>/plugins` (which resolves to `~/AppData/Roaming/...` on Windows and `~/Library/Application Support/...` on macOS), and note that the legacy `%APPDATA%/...` form is still accepted.
- **Tauri CONFIG_DEST default:** suggest `%APP_CONFIG%/<identifier>/config.json` as the canonical form, and document that it expands to `%APPDATA%/<identifier>/config.json` on Windows and `$HOME/Library/Application Support/<identifier>/config.json` on macOS.

### 3. `claude/CLAUDE.md` — platform-conditional rules

Two sections need to be rewritten so the rule reads correctly on both machines:

- **"Windows Bash Commands" (lines 29–34)** — rename to **"Bash Commands"** and split:
  - "**Windows (Git Bash):** use forward slashes in paths; backslashes get stripped as escapes."
  - "**macOS / Linux:** paths are already Unix-style; no special handling."
  - "When asking the user to run a command manually: **on Windows** provide PowerShell syntax; **on macOS/Linux** provide bash/zsh syntax."

- **"Symlinks" (lines 81–84)** is already cross-platform but uses Windows-first ordering. Keep the content; tighten wording to "Use the platform-appropriate command from `README.md`'s Global Installation section."

### 4. `claude/learnings/shell-environment.md`

- **Shells table:** add a row `macOS zsh | ~/.zshrc` (and a note that `~/.zshenv` is the right place for `export` lines that need to apply to non-interactive shells, e.g. cron / hooks).
- **`claude` wrapper:** the existing bash function works in zsh as-is. Add a one-line note: "On macOS, drop this in `~/.zshrc` (zsh) or `~/.bash_profile` (bash); the OSC 0 escape sets the tab title in Terminal.app and iTerm2." Keep the `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` line — it's harmless on macOS even though the `windows-terminal-title.md` rationale doesn't apply there.
- **Verification checklist:** add "On macOS, also verify `python3` resolves (Apple-provided python is gone in recent macOS — install via `brew install python` or use the dev-tools shim)."

### 5. `claude/skills/move-project/SKILL.md`

Line 39 currently says "On Windows, print both bash (`mv`) and PowerShell (`Move-Item`) variants". Change to: "On Windows, print both bash and PowerShell variants. On macOS / Linux, print only the bash `mv` form."

### 6. `claude/memory/reference_claude_dotfiles_repo.md`

- Drop `D:/projects/claude` from the title and body; replace with "this dotfiles repo" phrasing.
- The `name:` frontmatter currently says `Claude dotfiles repo (D:/projects/claude)` — change to just `Claude dotfiles repo`.
- The `[Environment]::SetEnvironmentVariable(...)` line gets a sibling bash example: `export CLAUDE_<APP>=<path>` (in `~/.zshenv` on macOS, `~/.bashrc` on Linux).
- Update the corresponding `MEMORY.md` index line (line 9 of `claude/memory/MEMORY.md`) to drop the `(D:/projects/claude)` parenthetical.

### 7. `README.md` — minor polish

The README already has a `Linux / macOS` branch for symlink setup and env vars. Two small tweaks:
- Under "Global Installation": add a one-line note above the Windows block saying "macOS / Linux users skip this section — see below." (purely navigational; the existing structure already separates them, but a top-of-section pointer reduces ambiguity).
- Under "Linux / macOS" symlink commands, add `mkdir -p ~/.claude` as the first line (the directory may not exist on a fresh macOS install before Claude Code's first run).

## Files NOT touched (deliberate)

- **`claude/hooks/check-bash-paths.py`** — the drive-letter check (`cwd[1] == ":"`) is already a no-op on macOS, where `cwd` starts with `/`. Works correctly as-is.
- **`claude/settings.json`**, **`git/hooks/pre-push`**, **`git/gitignore`**, **`git/gitattributes`** — already portable.
- **`claude/skills/skill/references/claude-project-memory-paths.md`** — already explicitly handles the macOS case ("Linux and macOS use plain `pwd`").
- **`claude/skills/release/SKILL.md`** — .NET / Windows release flow. The user keeps Windows-only releases; macOS won't invoke this skill.
- **Windows-only learning files** (`autohotkey.md`, `windows-terminal-title.md`, `tauri-windows-native.md`, `dotnet-tray-app.md`, `electron-windows-launcher.md`, `claude-code-plugin-mcp-config.md`) — informational, not loaded automatically. Harmless on macOS.
- **`claude/memory/feedback_glob_safety_windows.md`** — universal advice; the filename suffix is just historical. Not worth renaming and breaking the MEMORY.md link.

## Verification

After changes, on the macOS machine:

1. **Install path** — run the `Linux / macOS` symlink block from the README and confirm `ls -la ~/.claude` shows symlinks pointing into the repo.
2. **Hooks fire** — start `claude` in any project; the `PreToolUse` hook (`check-bash-paths.py`) must accept normal commands. Run a `cd` command; it should still be rejected.
3. **Pre-push hook** — make a signed commit and push to a test branch; the hook should pass it.
4. **Deploy guard** — in a .NET project (or any non-Tauri/non-IntelliJ dir on mac), run `bash ~/.claude/skills/deploy/scripts/deploy.sh`; expect the "Windows-only" early exit.
5. **Tauri deploy on mac** — clone any Tauri project, populate `config/deploy.env` with `INSTALL_DIR=/Applications/<name>`, run `! deploy`. Verify the `.app` lands in `/Applications/<name>` and `open` launches it.
6. **IntelliJ detect on mac** — in any IntelliJ-plugin Gradle project, run `bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh plugins-dir` and confirm it prints a path under `~/Library/Application Support/JetBrains/...`.
7. **Memory generalization** — open `~/.claude/memory/reference_claude_dotfiles_repo.md` on the macOS machine and confirm the bash `export` example is present and no `D:/projects/...` path appears.
