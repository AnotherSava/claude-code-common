# Windows Terminal tab titles from Claude Code hooks

Per-tab title manipulation **is feasible** on Windows Terminal — but not from inside the hook process itself. An external long-lived process (e.g. a dashboard app) can set any tab's title by attaching to the console of a process running in that tab. Proven June 2026 (claude-code-dashboard `terminal_title.rs`); supersedes the April 2026 "not feasible" conclusion below, whose failures are now explained.

## What works: external process + AttachConsole

```
FreeConsole() → AttachConsole(pid) → SetConsoleTitleW(title) → FreeConsole()
```

- `pid` must be a process attached to the target tab's console (the Claude Code process itself, or the shell that launched it).
- ConPTY propagates the console-title change to Windows Terminal as a title event → the tab updates.
- The title **persists** after the setter detaches or exits (verified: survives both `FreeConsole` and process exit by minutes).
- A process can hold only one console at a time — serialize the dance behind a mutex.
- Risk: while attached, if the user closes that terminal window in that instant, Windows terminates the attached process. Microsecond window per update; accept it or do the write in a disposable helper process.

### Getting the right pid: hooks live in an invisible console

Claude Code spawns hooks with `CREATE_NO_WINDOW`, which gives the hook a **fresh invisible console** — not the terminal's. So:

- `GetConsoleProcessList` inside the hook lists the invisible console's pids (just the hook + its shell wrapper). Titles written there succeed (`ok=True`) but are invisible — this is exactly why the April tests below looked "attached but ineffective".
- The fix: the hook also walks its **ancestor pid chain** (Toolhelp32 snapshot → pid→ppid map, stdlib `ctypes` only). The long-lived Claude Code process and the user's shell sit 1–3 levels up and own the visible console.
- The title-setter then tries candidates **far-to-near**: far ancestors are GUI processes (WindowsTerminal.exe, explorer.exe) where `AttachConsole` simply fails; the first success walking inward is the user's shell or Claude itself — the real console. Near-end transients (per-hook cmd/python) hold the invisible console and are never reached.
- `GetConsoleWindow()` **cannot** discriminate invisible vs real consoles: on current Windows 11, conPTY consoles report no window (returns 0), same as `CREATE_NO_WINDOW` ones.
- Pid-reuse guard: intersect successive candidate reports per session — transient pids differ every event and drop out; long-lived ones survive.

### Verification trap: Claude's Bash tool has its own hidden console

Claude Code's Bash tool runs commands in a **separate hidden conPTY** — `GetConsoleProcessList` there never includes claude.exe, and titles read/written there are not the user's tab. The PowerShell tool's persistent host *does* share the real terminal console. Verify console-level behavior via PowerShell, not Bash.

## What does NOT work (tested April 2026, Windows 11 + Git Bash + WT)

From inside a Claude bash subprocess / hook:

**1. OSC escape to stdout** — Claude captures hook stdout; the ESC byte is stripped and the sequence never reaches WT.

**2. `SetConsoleTitleW` via ctypes, no attach** — returns `ok=True err=0` but titles the hook's invisible `CREATE_NO_WINDOW` console (see above), not WT's surface.

**3. `/dev/tty` write** — `No such device or address`; Claude's bash subprocess has no controlling TTY.

## Claude Code overwrites the title

Claude Code itself emits OSC 2 title sequences on every render tick (status spinner like `⠐ Claude Code`). This competes with any externally-set title while Claude renders. Notes:

- Claude's OSC writes go through the PTY stream straight to WT — they do **not** update the conhost title, so `GetConsoleTitleW` can't observe them.
- To opt out, set `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` in the environment when invoking Claude. See [anthropics/claude-code#44590](https://github.com/anthropics/claude-code/issues/44590) and [#23355](https://github.com/anthropics/claude-code/issues/23355).
- PowerShell also re-asserts its own title on each prompt render unless the WT profile sets `--suppressApplicationTitle`.
- Mitigation without the env var: periodically re-push (the dashboard reasserts titles older than 5s on every state emit).

## `wt.exe` capabilities (per Microsoft docs, Nov 2025)

- Subcommands: `new-tab`, `split-pane`, `focus-tab`, `move-focus`, `move-pane`, `swap-pane`. **No `rename-tab`.**
- `--title` only works at tab/pane *creation* time: `wt -w 0 nt --title "X"`.
- `--suppressApplicationTitle` makes a title static so children can't overwrite it (this also blocks the AttachConsole approach above).
- Active feature request: [microsoft/terminal#19887](https://github.com/microsoft/terminal/issues/19887) — independent per-tab custom titles. No public API yet.

## Related: typing into the terminal

The same AttachConsole door allows **keystroke injection**: open `CONIN$` while attached and call `WriteConsoleInputW` with synthesized `KEY_EVENT` records — they land in the console input buffer the app reads from, no window focus needed. (Unlike `SendInput`, which requires foreground focus.) Useful for "answer this prompt from outside" features; needs staleness guards so injected keys don't land in the wrong prompt.
