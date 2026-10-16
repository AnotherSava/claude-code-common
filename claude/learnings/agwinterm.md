# agwinterm: control pipe, state files and what a client can observe

agwinterm is a Windows port of agterm (see `agterm.md`). Measured on 0.20.13 and a fork of it on 2026-10-02. Facts marked **fork** existed only on a local fork branch at that date, so probe for them rather than assume them.

## The control pipe

- **Name:** `AGWINTERM_PIPE` holds the *bare* pipe name (default `agwinterm`), not a path. A client opens `\\.\pipe\<name>`. The variable is exported only inside agwinterm sessions, so a GUI client outside one uses the default.
- **Framing:** newline-delimited JSON requests in a loop, so one connection carries every verb. A request is `{"cmd":"<verb>","target":"<id>","window":"<id>","args":{…}}`; a reply is `{"ok":true,"result":…}` or `{"ok":false,"error":"…"}`.
- **Bound the read, not the connect.** Connecting to a dead pipe fails in microseconds, but a reply waits on agwinterm's UI message loop: writes such as `session.rename` are queued behind every other UI action, with a 15 s ceiling on agwinterm's side.
- **Qualify with `window`.** Content verbs resolve against the frontmost window by default and search only that window.
- **Unknown verbs.** Over the pipe, the reply is `unknown command '<cmd>'`, the cmd exactly as sent; this is the reliable "this build lacks that verb" signal. Through `agwintermctl` the CLI refuses first, with different wording (`unknown session command '<sub>'`), so never sniff the CLI's text.
- **Cost:** a direct pipe call takes about 1 ms and `tree` about 8 ms. Spawning `agwintermctl.exe` costs about 95 ms of .NET startup per call.

## Per-session fields

- `session.rename` sets both `Name` and `CustomName`, and a blank name is refused. **Fork:** `--clear` (`{"clear":true}`) drops the custom name; an older build answers it with its blank-name refusal and changes nothing, which makes a safe probe.
- `session.context` is one line of at most 200 characters, with control characters refused, drawn dim after the name in the sidebar and title bar. It **persists** across restarts. `--clear` removes it.
- `session.status` takes only idle / active / blocked / completed and turns any other word into idle while still answering ok.
- **Fork:** the sidebar row shows the custom name, else the focused pane's OSC title, else `session N`. `tree` reports `title` (the focused pane's OSC title, present even while a custom name hides it) and `paneCwds` (pane id → directory). After an agwinterm restart, `title` stays absent for about 20 s, so read a missing title as "not yet", never as "this build has no titles".

## What runs in a pane, and when it has exited

- **A window file's `Command` is not the pane's root.** `%LOCALAPPDATA%\agwinterm\windows\<id>.json` records each pane's `Command`, and `tree` reports `capturedCommands`; both are the restore slot, the foreground command agwinterm captured to type back after a restart. A tab whose saved `Command` is `wsl.exe … start-here.sh` can be a PowerShell root with `wsl.exe` as its child, which reads very differently when the child exits. Read the real root from the process tree (PowerShell `Get-CimInstance Win32_Process` and each process's `ParentProcessId`). Measured 2026-10-15: all eight tabs on one machine were `powershell.exe` roots, while a review had taken the saved `Command` for the root and predicted a close that would never complete.
- **`foregroundShells` is per pane, in pane order.** A string is a live root shell agwinterm recognizes (cmd, powershell, pwsh, bash, sh, zsh, fish, nu) with no child process, which is a prompt. `null` covers three different states: a child is running, the root is not a recognized shell (`wsl.exe` or an agent started directly), and the pane's process has exited (`p.S.HasExited ? null : …` in the tree builder). Only the string answer is positive knowledge.
- **An exited single pane stays.** When a pane's process exits, agwinterm closes the pane only if the session is split; a one-pane session keeps the exited pane on screen and in `tree`. So waiting for a session to disappear after its program exits waits forever.
- **`session.close` asks nobody.** It disposes every pane in the session with no confirmation; the confirm prompt exists only on the keyboard path. A split's other pane goes with it.

## Reading what a pane shows

- `session.text` with `{"styles":true,"lines":N}` returns `{cols, rows:[{row, runs:[{col,width,text,faint,bold,…}]}], cursor}` over the last N rows, reaching into scrollback. Interior empty rows are kept; trailing whitespace and trailing empty rows are trimmed.
- **`agwintermctl session text` ignores a positional session id** and reads the active session; name one with `--target <id>`. Observed 2026-10-16: three different sessions all returned the same session's screen until `--target` was passed.
- **A pane mirroring a tmux window smaller than this client ends every row in tmux's edge and fill**: the window's right edge `│` (`┘` at the bottom corner), then `·` out to the client's width, and the rows below the window are `·` only. It appears whenever another client, such as a Mac attached to the same session, holds the window narrower. A `─` rule read off such a row is `───│····`, so strip the fill and then the edge before matching anything at a row's end, cutting the edge only where fill followed it, since without fill the last column is content.
- **The cursor is useless for a Claude Code pane under tmux.** Observed parked at the bottom-right cell (`row 66, col 240`) of an idle session, nowhere near the composer.
- **Claude Code's composer reads as a `>` (or `❯`) row directly under a `─` rule, through to the next rule**, with its status lines below that. An empty composer is the bare glyph. The placeholder suggestion is drawn faint; paste and image chips (`[Pasted text #1 …]`, `[Image #1]`) are plain text in the input value and not faint, per the 2.1.295 binary, so excluding faint runs separates a placeholder from a draft. A draft typed from a second tmux client, such as a Mac attached to the same session, appears in this pane too.

## Titles through WSL and tmux

A pane running `wsl.exe … tmux attach` receives the inner pane's title only when tmux has `set-titles on` with `set-titles-string '#T'`. Tested in isolation, both a plain OSC 0 sent from WSL and one forwarded by tmux reached agwinterm's title. A `SetConsoleTitleW` on the WSL-side console of a Windows process inside that tmux pane arrives as tmux's pane title and travels the same way (see `windows-terminal-title.md`).

## Observing which session the user is looking at

- **No event exists.** Selecting a session emits nothing on the `events` feed, the UIA session rows expose no Selection pattern and raise no event, and the OS window caption is the constant `agwinterm`.
- **The state file is the edge.** Every selection change rewrites `%LOCALAPPDATA%\agwinterm\windows\<window-id>.json` with the top-level `ActiveId` (the session id) and `Mru`.
  - The writer waits a fixed 200 ms after its first trigger, then writes the newest snapshot. Unchanged bytes are skipped.
  - Each save goes to `.tmp` and is renamed over the file, so watch the directory, not the file.
  - The same file is rewritten on every rename or context write too, so react only when `ActiveId` changes.
  - During a Ctrl+Tab walk each preview step writes `ActiveId` but leaves `Mru` alone; `ActiveId != Mru[0]` marks a preview.
  - The file format has no version field (its source says "additive keys only"); `windows.json`, the window index, does carry `Version`.
- `AGWINTERM_APP_ID` changes the data directory (a dev build uses `agwinterm-dev`). The quick terminal has the same window class but a different caption.

## Colour emoji

The chrome draws text with Direct2D. Without `DrawTextOptions.EnableColorFont`, Segoe UI Emoji glyphs render as flat outlines in the brush colour.
