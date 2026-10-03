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
