# Terminal tab titles from Claude Code hooks

Per-tab title manipulation **is feasible** on Windows Terminal — but not from inside the hook process itself. An external long-lived process (e.g. a dashboard app) can set any tab's title by attaching to the console of a process running in that tab. Proven June 2026 (claude-code-dashboard `terminal_title.rs`); supersedes the April 2026 "not feasible" conclusion below, whose failures are now explained. The macOS equivalent — an OSC write to the tab's controlling tty — is proven too; see the macOS section below.

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

## macOS: OSC write to the controlling tty (proven June 2026)

The same external-process pattern works on macOS with no console attach:

- The hook reports its **ancestor pid chain** (one `ps -axo pid=,ppid=` snapshot, nearest first). The hook's own pid is transient, but Claude Code 1–2 levels up is long-lived and shares the controlling tty of the visible tab.
- The title-setter resolves a candidate's tty with `ps -o tty= -p <pid>` (→ `ttys003`), then writes the OSC escape straight to the device: open `/dev/ttys003` write-only and write `\x1b]0;<title>\x07`. The emulator interprets the sequence without rendering anything; no window focus needed. Works in kitty, Terminal.app, iTerm2.
- Walk candidates **near-to-far** (opposite of Windows — there is no attach dance whose first success must be the real console): dead transients fail the `ps` lookup and GUI ancestors (the terminal emulator itself) report `??`, so the first resolvable pid is Claude or the user's shell.
- Same verification trap as Windows: Claude's Bash tool shell has **no controlling tty** (`ps -o tty=` → `??`) — resolve from ancestors, never from the hook/tool process itself.

Proven in claude-code-dashboard `terminal_title.rs` (`push_title` unix arm) + `claude_hook.py` ancestor gathering.

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

## Reading a title back: `GetConsoleTitleW` is per session, not per screen

The inverse of the write above, and the useful property is that it is **not** what is on screen. Attach exactly as for the write, then read:

```
FreeConsole() → AttachConsole(pid) → GetConsoleTitleW(buf, len) → FreeConsole()
```

Verified September 2026 against seven live Claude Code sessions sharing one Windows Terminal window: seven distinct titles in a single pass, each the caption for that session, unchanged across three orderings (forward, reverse, interleaved). Attaching disturbed nothing measurable; the sessions' own registry records were byte identical before and after.

- **Judge success by the returned length, never by `GetLastError`.** After a call that succeeded it reads a stale 203 (`ERROR_ENVVAR_NOT_FOUND`).
- Failure codes worth recognising: 6 `ERROR_INVALID_HANDLE` for a process with no console (any GUI process), 5 `ERROR_ACCESS_DENIED` for a system process, 87 `ERROR_INVALID_PARAMETER` for a pid that does not exist.
- It works for a headless console too (a `CreateNoWindow` child), so it is not Windows Terminal specific: it reads the console object, whoever renders it. `GetConsoleWindow()` returns 0 for such a console, which is why it cannot be used to tell a real console from an invisible one.
- Because the read is per console, it is the only way to ask "what is each session showing" without enumerating tabs. A terminal's window caption can only ever answer for the tab in front.
- Since Claude Code's own OSC writes bypass conhost (see above), what comes back is what *you* wrote, which makes this a durable place to read your own last published state after a restart.

## Which tab is on screen

Windows Terminal publishes the **active tab's** title as its window caption, so one `GetWindowTextW` answers it, with no automation surface required:

- Enumerate with `EnumWindows` and keep windows whose `GetClassNameW` is `CASCADIA_HOSTING_WINDOW_CLASS` and which are visible. The invisible `Windows Terminal <hex>` window in the same process is the monarch, so the visibility test matters.
- **One `WindowsTerminal.exe` process hosts every window**, so its pid discriminates nothing. Key anything per window on the HWND.
- Switching tabs changes the caption, and therefore fires `EVENT_OBJECT_NAMECHANGE`. See `windows-winevent-hooks.md` for watching that cheaply.
- A user setting can break the link: `suppressApplicationTitle`, a profile `title`, or a `tabTitle` all pin the caption so it no longer follows the session.

Three routes that do **not** work, so they need no re-probing:

- The `wt.exe` CLI is fire and forget. No subcommand returns state; [microsoft/terminal#19818](https://github.com/microsoft/terminal/issues/19818) is the open ask.
- Nothing reaches disk on a tab switch. `state.json` holds `persistedWindowLayouts`, written on exit, so a file watcher sees nothing live.
- UI Automation **can** enumerate every `TabItem` with its `Name` and `SelectionItemPattern.IsSelected`, measured at 26 ms for a seven tab window. But it exposes no working directory, and it needs COM, so it buys nothing over the window caption unless you specifically need the tabs that are *not* in front.

## A renamed tab stops following the title, permanently

Windows Terminal lets a tab carry a **custom name** (right-click, Rename tab; or a double-click on the tab title). From that moment the tab ignores every title you write, and there is no way to undo it from outside the app. Diagnosed September 2026 after a tab sat on a stale glyph for hours while the console underneath it updated correctly.

The cause is in `Tab::_GetActiveTitle()` ([Tab.cpp](https://github.com/microsoft/terminal/blob/main/src/cascadia/TerminalApp/Tab.cpp)):

```cpp
if (!_runtimeTabText.empty()) { return _runtimeTabText; }
...
return activeContent ? activeContent.Title() : winrt::hstring{};
```

The custom name wins unconditionally, and the only thing that clears it is `ResetTabText()` (`_runtimeTabText = L""`), reached from exactly one place: the rename action carrying no title, which is what the menu's "Reset tab title" invokes. There is no counter, no timer, no tab-switch hook and no reattach hook, so **no number of console-side writes ever un-pins it**.

### It is invisible to inspection, and detectable only by behaviour

A full UI Automation property dump of a pinned tab and a normal one is **identical** across every property and pattern the managed API can reach: `ClassName=ListViewItem`, `ControlType=TabItem`, `AutomationId`/`HelpText`/`ItemStatus`/`ItemType` all `NotSupported`, patterns `SelectionItem`/`ScrollItem`/`VirtualizedItem`, subtree `Image` + `Text[HeaderTextBlock]` + `Button[CloseTab]`. Only `Name` differs, and it differs because the *title* differs. `--suppressApplicationTitle` is likewise indistinguishable from a custom name, so a detector cannot even report which kind of pin it hit.

What does work is probe-and-compare: write a title into the tab's process, then read that `TabItem`'s `Name` back.

```
tab A  plain                       console -> 'A-PUSHED-2'   tab -> 'A-PUSHED-2'      applied in 10 ms
tab B  renamed via command palette console -> 'B-PUSHED-2'   tab -> 'B-PINNED-CUSTOM' never applied
tab D  --suppressApplicationTitle  console -> 'D-PUSHED-2'   tab -> 'D-WTTITLE'       never applied
```

Sizing the grace period: eight samples of a legitimate change applied in 5.8 to 33.7 ms, every one caught on the *first* UIA read, so the true propagation is below one UIA round trip. Anything above ~200 ms is margin. Note `new-tab --title X` does **not** pin (a later console-side change overrides it); `--suppressApplicationTitle` does.

Two traps for a detector. A **dead pane keeps its stale tab title** indefinitely, so confirm the target process is alive before calling a mismatch a pin. And a caption can only be matched to a session by its text, since nothing exposes which window hosts which process, so a second window showing a lookalike title is judged too.

### Every route to resetting it from outside is closed

| route | result |
|---|---|
| `wt.exe` CLI | No rename or reset verb. Verb list extracted from `TerminalApp.dll` v1.24.11911.0: `new-tab`, `split-pane`, `focus-tab`, `move-focus`, `move-pane`, `swap-pane`, `focus-pane`. Title options are `--title`/`--suppressApplicationTitle`, both `new-tab`-only. |
| UI Automation | `TabItem` exposes no `Invoke` or `ExpandCollapse`. The COM-only `IUIAutomationElement3::ShowContextMenu` returns `S_OK` and opens **nothing** (zero `Menu` elements afterwards): a silent no-op. Only a real right-click at screen coordinates remains. |
| WinRT / COM / pipes | `AppxManifest.xml` registers three CLSIDs: OpenConsole handoff, the Monarch, and the shell extension. The Monarch's dispatch takes a **wt command line**, so it is isomorphic to the CLI and adds no verb. |
| State files | `_runtimeTabText` is in-memory only. `state.json` holds `persistedWindowLayouts`, written on exit. No registry surface. |

[microsoft/terminal#14616](https://github.com/microsoft/terminal/issues/14616) reports exactly this behaviour and is **closed with no fix**; [#19783](https://github.com/microsoft/terminal/issues/19783) documents the adjacent gap that there is no way to address an existing tab at all.

The only mechanically possible workaround is to write a keybinding into the user's `settings.json`, focus the tab, take the foreground and synthesize the keystroke. Treat it as unavailable: it mutates another application's config to work around that application's behaviour, and it steals foreground and changes the selected tab, which is destructive to anything that reads tab selection as a signal of what a human did. Report the condition and name the two-second manual fix instead.
