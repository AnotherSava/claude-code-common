# Windows Terminal tab titles from Claude Code hooks

Per-tab title manipulation from inside Claude Code hooks/subprocesses is **not feasible** on Windows Terminal. Tested April 2026 on Windows 11 + Git Bash + Windows Terminal.

## What was tested

Both methods invoked from a Claude bash subprocess (via `!` prefix and via the Bash tool — same stdio environment as a real `Notification` or `Stop` hook would have).

**1. OSC escape sequence to stdout**

```python
sys.stdout.write(f"\033]0;{title}\a")
```

Result: Claude captures the bash subprocess's stdout. The ESC byte gets stripped/visualized in Claude's display (`]0;test` shows up as plain text in the output block). The sequence never reaches Windows Terminal's stream. **Title does not change.**

**2. `SetConsoleTitleW` via ctypes**

```python
ctypes.windll.kernel32.SetConsoleTitleW(title)
```

Result: API call returns `ok=True err=0` — meaning the hook process *has* a console attached — but the WT tab title does not change. The hook process is connected to a console that is not WT's rendering surface (likely a detached conhost or a ConPTY without title-event propagation back to WT).

**3. `/dev/tty` write**

```bash
printf '\033]0;test\a' > /dev/tty
```

Result: `/dev/tty: No such device or address`. Claude's bash subprocess has no controlling TTY at all.

## What works (for reference)

- Both OSC stdout and `SetConsoleTitleW` work fine when invoked from a real PowerShell/bash session, *not* from inside Claude. PowerShell re-asserts its own title on each prompt render, so the title reverts unless `--suppressApplicationTitle` is set on the WT profile.

## `wt.exe` capabilities (per Microsoft docs, Nov 2025)

- Subcommands: `new-tab`, `split-pane`, `focus-tab`, `move-focus`, `move-pane`, `swap-pane`. **No `rename-tab`.**
- `--title` only works at tab/pane *creation* time: `wt -w 0 nt --title "X"`.
- `--suppressApplicationTitle` makes a title static so children can't overwrite it.
- `-w 0` targets an existing window for *creating* new things; cannot mutate existing tab metadata.
- Active feature request: [microsoft/terminal#19887](https://github.com/microsoft/terminal/issues/19887) — independent per-tab custom titles with optional automatic update control. No public API yet.

## Workarounds (none clean)

- **Static title via launcher:** `wt -w 0 nt --title "[project] claude" --suppressApplicationTitle claude` — gives project name in tab header for the session lifetime, but no dynamic state.
- **UI Automation** (PowerShell `System.Windows.Automation`) to invoke WT's "Rename Tab" UI — brittle, requires foreground focus, disrupts user.
- **AHK / SendInput** to send the `renameTab` keybinding — same focus-stealing issue, worse.

## Recommendation

For dynamic per-session status visibility, use an external dashboard/widget instead of trying to manipulate WT tab headers. [AI Status Dashboard](https://github.com/Idevelopusefulstuff/claude-status-dashboard) is a known Windows-compatible option (Electron, system tray + always-on-top overlay, hook-driven via localhost:7890).
