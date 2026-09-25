# Shell Environment

Shell configuration across the user's environments. Use this to verify correct setup when running Claude Code in a new shell (e.g. WSL) or diagnosing missing functions/aliases.

## Shells and config files

| Shell | Config file |
|---|---|
| Git Bash (Windows) | `~/.bashrc` |
| WSL Ubuntu | `~/.bashrc` |
| macOS zsh | `~/.zshrc` (interactive). Put `export` lines that need to apply to non-interactive shells (cron, hooks) in `~/.zshenv` instead. |
| PowerShell 7 | `Documents/PowerShell/Microsoft.PowerShell_profile.ps1` |
| PowerShell 5 | `Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1` |

## Bash functions (`~/.bashrc`)

All bash shells (Git Bash, WSL) should have these functions:

### `claude` — wrapper with auto-continue

```bash
claude() {
  export CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
  if [[ "$1" == "--new" ]]; then
    shift
    command claude "$@"
  else
    command claude --continue "$@"
    if [[ $? -ne 0 ]]; then
      command claude "$@"
    fi
  fi
  [[ $? -eq 0 ]] && clear
}
```

- `claude` → resumes last conversation (`--continue`). Falls back to fresh session if none exists.
- `claude --new` → fresh conversation.
- Exports `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` so Claude's per-tick title writes (`⠐ Claude Code`) do not overwrite the title the dashboard puts on the tab (see `windows-terminal-title.md`). The wrapper writes no title of its own, because the dashboard owns it.
- Screen clears on success; preserved on error so the message is readable.
- **macOS:** drop the same function in `~/.zshrc` (zsh) or `~/.bash_profile` (bash). The export matters there as well: the dashboard writes the title to the tab's tty, and Claude's per-tick writes would otherwise overwrite it.
- **The Windows machine that runs the remote-session holder** is the exception: there Git Bash, Windows PowerShell 5.1 and PowerShell 7 each get the one-line `claude` that `claude/remote-session/windows/install-shells.ps1` writes, which hands off to `start-here.sh`, and the title switch-off travels inside the tmux pane's command. The installer does not touch WSL's `~/.bashrc`.

### `deploy` / `build` / `publish` / `cb` — project shortcuts

```bash
run_repo_script() { local rel="$1"; shift; local d="$PWD"; while [ "$d" != "/" ] && [ ! -f "$d/$rel" ]; do d="$(dirname "$d")"; done; if [ -f "$d/$rel" ]; then ( cd "$d" && bash "$rel" "$@" ); else echo "No $rel in this directory or any parent"; fi; }
deploy() { run_repo_script scripts/deploy.sh "$@"; }
build()  { run_repo_script scripts/build.sh "$@"; }
# Ship a project live — the counterpart to `deploy`, which only runs/installs it here.
# Kept separate so nothing publishes by accident.
publish() { run_repo_script scripts/publish.sh "$@"; }
# Re-copy the value Claude last put on the clipboard, for when something has overwritten it since.
# The script is regenerated on every copy, so it always holds the most recent one.
cb() { run_repo_script scripts/cb.sh "$@"; }
```

Use `! deploy`, `! build`, `! publish` or `! cb` inside Claude Code, or run directly in any terminal. They all delegate to `run_repo_script`, which walks up from the current directory to the repo's `scripts/<name>.sh` and runs it from the directory that holds it — so they work from any subdirectory (the underlying scripts read `config/deploy.env` and other paths relative to that root). `run_repo_script` is generic: reuse it for any future repo shortcut. Each project carries whichever of `scripts/deploy.sh`, `scripts/build.sh`, `scripts/publish.sh` and `scripts/cb.sh` it actually needs, each a thin wrapper delegating to the global script in the corresponding skill directory — and a project that publishes from CI deliberately has no `publish.sh` at all. All of them are gitignored via the global excludes file, where one narrow rule covers every repo, so nothing leaks into a shared project's committed `.gitignore`.

`cb` is the odd one out: its script is not written once at setup but **regenerated every time Claude puts a
value on the user's clipboard**, so `cb` always hands back the most recent one. It holds the command that
*retrieves* the value (normally a `doppler secrets get`), never the value itself — so no secret sits in
plaintext on disk and a rotation can't leave it serving a dead credential. See the doppler skill.

### `memo` — fast backlog access

```bash
memo() {
  local py="$HOME/.claude/skills/memo/memos.py"
  if [ $# -gt 0 ]; then python "$py" add "$@"; return; fi
  # memos.py sizes itself everywhere but Windows, where a console is not a pty — see Width below.
  case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) python "$py" list --width "${MEMO_WIDTH:-148}" ;;
    *) python "$py" list ;;
  esac
}
```

macOS reaches the same helper through `~/.local/bin/memo` rather than a shell function, and that script needs no width arm at all — it execs `memos.py` and nothing else.

`! memo` (or `memo` in any terminal) prints the open backlog at full width in ~0.1 s; `memo <text>` writes that text as a new memo file, deriving the title from its first sentence (no quotes needed). This is the **model-free** path — the `/memo` skill is slow because it drives the model through multi-step tool calls, wasted effort for a plain list/append. Reach for the skill only when you want model help: titling an idea well on capture, or reviewing with offers to act on items.

**The function is add-and-list only; every other subcommand goes through the script.** It passes any argument straight to `add`, so `memo done 1` creates a memo *titled* "done 1" rather than closing memo 1 — use `python ~/.claude/skills/memo/memos.py done 1` for that, and likewise for `show`, `path`, `reopen`. Routing on the first word was considered and rejected: memos are written as imperatives, so `done`, `list`, `show` and `count` are all plausible openers for a real memo, and any such guard would swallow one. The mistake is at least visible — `add` echoes the stored title and the new count, so a junk entry shows up the moment it is made.

**Flags forward for free, and only from the front.** `"$@"` reaches `add` unchanged, so `memo --platform windows the thing that only works there` works without touching the function. `_take_flag` reads only the opening run of `--flag value` pairs, which is what keeps a flag word occurring later in a memo's own prose — `memo use --title to name a thing` — from being eaten along with the word after it. Lead with the flags; anything after the first non-flag argument is memo text.

**Width.** Pass nothing on macOS, Linux and WSL: `memos.py` asks `skills/shared/terminal_width.py`, which walks up the process chain to the Claude Code process and reads that tty's winsize. Neither `tput cols` nor `$COLUMNS` can answer from a captured shell — both return their own defaults, 80 and 0, with no error — which is why the wrapper used to carry a pinned number instead.

**Windows still needs one, and the pin has to sit inside the function.** A console is not a pty, so the walk finds nothing and the helper falls back to ~100. Two facts shape the workaround: Claude Code syncs `.bashrc` *functions* into the `!` shell but not its top-level `export`s, so a `MEMO_WIDTH` export never reaches `! memo` and the default must be written in the function body; and `CLAUDECODE=1` is in Claude Code's own environment rather than `.bashrc`, so it is the reliable flag for a captured shell where a narrower value is wanted. **Set the pin to `window − ~4 − 2`, not the raw window**: Claude Code renders `!`-command output under a `└` tree prefix that indents it ~4 columns, so wrapping at the full width overflows and the terminal re-wraps it (a 156-column window wants ≈ 148). Adjust it after resizing.

That `└` indent applies to the detected path too, and the shared module subtracts only the 2-column gutter — it is tuned for tool-call output, which is where the skills render their tables. A `! memo` listing can therefore run a couple of columns wide. `memos.py` reads a `MEMO_WIDTH` environment variable ahead of detection for exactly this, the same way `github-status` reads `GHS_WIDTH`; in a plain terminal an export is enough, but the `!` shell never sees one, so fixing it there means the same in-function default Windows already uses.

## PowerShell `claude` wrapper

```powershell
function claude {
    $env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE = "1"
    if ($args[0] -eq '--new') {
        & claude.cmd @($args[1..$args.Length])
    } else {
        & claude.cmd --continue @args
        if ($LASTEXITCODE -ne 0) { & claude.cmd @args }
    }
    if ($LASTEXITCODE -eq 0) { Clear-Host }
}
```

Same behavior as the bash version. PowerShell re-asserts its own title on each prompt render after Claude exits. On the Windows machine that runs the remote-session holder, use the function `install-shells.ps1` writes instead.

## PowerShell `memo` wrapper

```powershell
function memo {
    $py = "$HOME\.claude\skills\memo\memos.py"
    if ($args.Count -gt 0) { python $py add @args; return }
    $w = if ($env:MEMO_WIDTH) { [int]$env:MEMO_WIDTH } else { [Math]::Max(40, $Host.UI.RawUI.WindowSize.Width - 2) }
    python $py list --width $w
}
```

Same as the bash `memo` — fast, model-free backlog access (`memo` to list, `memo <text>` to add).

## Verification checklist

When setting up a new shell (e.g. WSL), verify:

1. **`claude` function exists** — `type claude` should show the function, not the binary path
2. **`deploy` function exists** — `type deploy`
3. **`build` function exists** — `type build`
4. **`publish` function exists** — `type publish`
5. **`memo` function exists** — `type memo`
6. **`notify` function exists** — `type notify`
7. **A real `python` on `PATH`** — `python -V`. Hooks and the statusline invoke the bare name, never `python3`, because `python3` is an indirection on both platforms (bash shim on Windows, `xcode-select` dispatcher on macOS). A machine without it runs no hooks, silently.
8. **macOS only:** Apple ships no `python`, and the Command Line Tools `python3` is 3.9 — old enough that `str | None` annotations fail at import. Run `brew install python && ln -s /opt/homebrew/bin/python3 ~/.local/bin/python`, and check `~/.local/bin` is on `PATH`. See the README's [Python interpreter](../../README.md#python-interpreter) section.
9. **Deps for `notify`** — `python -c "import requests, dotenv"`. The Claude hooks themselves are stdlib-only, so this gates `notify`, not them.
10. **Symlinks intact** — `ls -la ~/.claude` should point to the claude-code-common repo's `claude/` directory
11. **Git hooks linked** — `git config --global core.hooksPath` should return `~/.git-hooks`
