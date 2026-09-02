# agterm

Things about agterm that its bundled skill does not cover. The skill itself is comprehensive; read it
first (`~/.claude/skills/agterm/SKILL.md`), and read this for the two facts it cannot carry.

## Do not edit the bundled skill — it is vendored, and your edit dies at the next upgrade

`claude/skills/agterm/` in the dotfiles repo is **vendored third-party content**, byte-identical to
`/Applications/agterm.app/Contents/Resources/agterm/`, shipped inside the Homebrew cask and **rewritten
in full on every `brew upgrade`**. It is deliberately gitignored (`claude/skills/*` with a whitelist of
the user's own skills) and declared in `claude/untracked-skills.local.txt` with that reason.

Three consequences:

- An edit there is silently reverted by the next cask upgrade, and breaks the byte-identity invariant
  meanwhile.
- It never appears in `git status`, because an ignored path does not — so no commit flow will mention it,
  and nothing will tell you the edit was lost.
- A note you want to keep about agterm belongs **here**, in a tracked learning, not in that file.

Restore it with `cp /Applications/agterm.app/Contents/Resources/agterm/SKILL.md ~/.claude/skills/agterm/SKILL.md`
and confirm with `diff` that the two are identical again.

The general shape, worth carrying beyond agterm: before editing anything under a `skills/` tree, check
whether that directory is tracked. `git ls-files --error-unmatch <dir>` answers it in one command, and
`git check-ignore -v <path>` names the rule and line that excludes it.

## `ok` from `session type` means accepted, not submitted

The documented way to send a message to another session is to type the text and then submit it:

```bash
tr -d '\n' < msg.txt | agtermctl session type --stdin --select --target <ID>
printf '\r'          | agtermctl session type --stdin --target <ID>
```

Both calls return `ok` — and the text can still be sitting unsent on the prompt line. Observed
2026-08-26 on a session receiving a long single-line brief: the paste arrived as a bracketed
`[Pasted text #N]` and the carriage return did not take. `ok` reports that the control socket accepted
the command, never that the program consumed the line.

So the send is not finished until you have looked:

```bash
agtermctl session text --target <ID> --lines 12
```

If the message is still on the `❯` prompt line rather than scrolled above it, send `\r` again. Two of
three sends took first time in that session and one did not, so this is intermittent — which means
verifying every send is the only reliable policy. It costs one command; skipping it costs a message the
other agent never receives while you believe it did.

Related: newlines in the payload each submit separately, so a multi-line brief becomes N premature
Enters — strip them (`tr -d '\n'`) and send one long line. The bundled skill covers that part.

**None of this applies to messaging another Claude Code session any more.** Claude Code ships a native
cross-session channel — `ListAgents` / `SendMessage`, delivered over a per-session socket — so a
Claude → Claude message needs no typing, no `\r`, and no pane read-back, and it reports
delivered / held / refused back to the sender. Verified 2026-08-30; see
`claude-code-cross-session-messaging.md`. The typing route above remains the answer only for driving a
program that is *not* a Claude Code session.

## The OSC title *is* the session name, and agterm never writes one itself

`displayName = customName ?? oscTitle ?? cwd basename`. So whatever a program writes as the terminal
title (`\033]0;…\007`) becomes the session's name in the sidebar row, the titlebar and OS window title,
the Dashboard grid caption, the Ctrl-Tab switcher, the command palette, the recent-sessions list, the
Dock menu, the rename seed, `agtermctl tree --json .name`, and the `{AGT_SESSION_NAME}` custom-command
token. There is no setting to ignore or hide it. Emoji, brackets and `%` survive verbatim — only C0/DEL
are stripped.

Two consequences worth planning around:

- An external status writer (a widget mirroring agent state onto tab titles) effectively **renames**
  every agterm session it touches. That is usable as a feature, not just a hazard. To keep a stable
  label anyway, double-click-rename the session: a `customName` outranks the OSC title. The OSC string
  then still shows as the row's *subtitle* wherever `oscTitle != displayName`.

  The flip side is silent, and it cost hours on 2026-08-29: a row renamed once is **permanently dark**
  for status, because `Session.displayName` returns `customName` before it ever consults the title
  (`agtermCore/Sources/agtermCore/Session.swift:389`). The writer keeps succeeding the whole time — the
  OSC reaches the pty, agterm stores it, `agtermctl tree --json` reports it under `.title` — and the row
  just never shows it. So diagnose from agterm, not from the writer: run `agtermctl tree --json` and
  compare `.name` against `.title` across every row. Equal everywhere means the writer is healthy; the
  one row where `.name` differs and reads like a bare cwd basename is the renamed one. The published
  node carries no `customName` key at all, so its absence proves nothing — confirm against the persisted
  snapshot at `~/Library/Application Support/agterm/windows/<window-id>.json`.

  **The `.name` vs `.title` comparison gives a false negative when the pin was captured from the status
  writer's own output**, which is the likely case if the rename happened by accident rather than on
  purpose. Seen 2026-08-30: `customName` was the literal `🔵 tauri-dashboard`, emoji included, so every
  time the row sat in the writer's blue/Working state `.name == .title` and every row looked healthy —
  the row read as a full status title, not the "bare cwd basename" the paragraph above suggests looking
  for. The discriminator that always works is a **unique** marker: write
  `printf '\033]0;UNIQUE-XYZ\007' > /dev/ttysNNN` and re-read the tree **within about a second**, before
  the status writer's next pass overwrites it (a 3s wait already lost it, twice). Pinned shows
  `.title` moving to `UNIQUE-XYZ` while `.name` stays put; healthy shows both. Do not conclude anything
  from a sample taken while the writer may have just refreshed — that misreading produced two wrong
  diagnoses in a row (a "wedged escape parser", then a retraction of the correct answer).

  Clear it with
  `agtermctl session rename "" --target <id>`: `AppStore.renameSession` runs
  `TerminalText.sanitized(name).trimmedOrNil`, so an empty string sets `customName` to nil and the row
  returns to title-driven naming.
- Clearing is clean: an empty title (`printf '\033]0;\007' > /dev/ttysNNN`) trims to nil and the name
  falls back to the cwd basename. Useful for undoing a title written to the wrong tab.

agterm is a **cooperative host** here — it ships `shell-integration-features = no-cursor,no-title` and
its own sources contain no escape-sequence writes, so nothing on its side clobbers an external writer.
Do not add `title` back to `shell-integration-features` in either the agterm-scoped ghostty config or
`~/.config/ghostty/config`: the shell would rewrite the title on every prompt and every command start.
An incoming title also fires **no** side effects — no unseen badge, no notification, no sound, no
auto-follow, no tree-change event — so a widget reasserting a title every few seconds is free.

## Agent status: one source only, and the installer re-adds hooks you removed

**Help ▸ Install Agent Status Hooks…** merges four Claude Code hooks into `~/.claude/settings.json`
(plus Codex/Pi/OpenCode equivalents) to drive a 4-value sidebar glyph: idle / active / completed /
blocked. Its docs treat agterm's glyph and an external status source as **alternatives, not layers**.
The glyph's only writer is the `session status` control command, so deleting the hooks leaves it idle
forever — and idle collapses its width to zero, so the row reclaims the space.

What goes dark with it: ⌃⌥↑/↓ attention navigation and `session go next-attention|prev-attention`, the
titlebar attention bell and its popover, the ⌃⇧I attention palette, auto-follow-to-blocked, the Blocked
sound, and the Dashboard grid's status-coloured caption pills. Nothing else depends on status — the
indicator is never persisted, restore-command capture is native, and naming is customName/OSC/cwd.

**The installer is not safely re-runnable.** Its skip-probe matches the wrapper's *literal absolute
path*, so an entry written as `$HOME/.config/agterm/agent-status/…` does not match and the merge
**appends a second copy** of every event — including `active --blink` entries you deliberately removed,
without any `async: true` or `[ -n "$AGTERM_SESSION_ID" ]` guard you added. The same run also wipes and
re-copies `~/.config/agterm/agent-status/`, destroying local edits to the wrapper. There is **no
uninstall path** anywhere in agterm; recovery is the `.bak` it leaves beside `settings.json`. So:
decline it on upgrade, and remove hooks by editing `settings.json`, not by neutering the wrapper.

Current setup (2026-08-27): agterm's Claude hooks are **removed** on this machine — the
claude-code-dashboard owns status display, because agterm's four values cannot express its `Waiting` or
`Error` states. agterm's shell integration is not a silent second source: its agent regex
(`gemini|cursor-agent|aider|crush|goose`) deliberately excludes Claude Code.

### When PR #461 ships, decline it

An agent spawned from inside a session inherits the spawner's whole `AGTERM_*` set, so its own hooks
repaint the **spawner's** row. Upstream accepts this (Discussion #456: *"the ownership guard: the bug is
mine"*); the fix is PR #461, a ppid-walk that silences a hook when it counts more than one agent binary
up the chain. Carriers include an agent CLI's own background daemon — Claude Code's
`claude daemon run --origin transient`, which no user launches, so the documented `env -u` prevention
has no application point and the daemon outlives the pane you would restart.

The counter-intuitive part: **when a release containing #461 appears, the action here is to decline the
installer, not to adopt the fix.** With zero hook entries present, #461's byte-exact migration finds
nothing to rewrite, so the ordinary merge path just adds fresh hooks — it is a precondition for safely
*re-installing* what was deliberately removed, not a mitigation for anything currently running. It also
only covers the hook lane; the skill still teaches agents `--target "$AGTERM_SESSION_ID"` directly, which
no file in that PR touches.

Do not scrub `AGTERM_SESSION_ID` as a workaround either: unset, the skill's `--target
"$AGTERM_SESSION_ID"` call sites expand to empty and agtermctl falls back to `--target active` — trading
a fixed wrong pane for whichever pane you happen to be looking at, on `type`, `close` and `split close`.

## Creating a session that runs a program *and* survives it

`session new --command` is the documented launcher (typing is not — see above), but on its own it is the
wrong shape for anything long-lived. The flags disagree with what you probably want:

| form | what you get when the program exits |
|---|---|
| `--command "prog"` | the **session closes**. `--command` replaces the login shell, so the session's process *is* `prog`. |
| `--command "prog" --wait` | libghostty's press-any-key prompt with the final output intact, then it closes. Good for reading a build's last lines; not a session. |
| `--command "zsh -ilc 'prog; exec zsh -i'"` | a live interactive prompt in the same cwd. The session never closes. |

The third is what reproduces a session the user started by hand and then ran something in.

**`-ilc`, not `-lc`.** agterm's own docs suggest `zsh -lc '…'` as the PATH wrapper, which is not enough
when agterm itself was launched from the GUI: a login-but-non-interactive shell never sources `.zshrc`,
and `.zshrc` is where `~/.local/bin` and the like get prepended. Measured on a normally-launched agterm
(`ps -Ewww`): `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, nothing else, and `launchctl getenv PATH` empty.
Under that env, `zsh -lc 'whence -w claude'` answers `claude: none` while `zsh -ilc` answers
`claude: function`. The `-i` also picks up the user's own shell *functions*, which is usually the point —
a wrapper function is where their real default flags live, so going through it is what makes the spawned
session identical to a hand-started one rather than merely similar.

**`--no-select` is free.** It creates the session without stealing focus, and — verified, not assumed —
the session is still `realized: true` immediately, pty and all. There is no trade-off to weigh.

**`ok: true` is not "it is running".** `session new` reports success for a session that exists in
agterm's *model*; libghostty refuses to create a surface while the display is asleep, and an unrealized
session never runs its `--command` at all. So an unattended creator must poll `tree --json` for that
id's `realized` flag and close the node if it stays false, or it accumulates one dead row per attempt.
Keep the `result.id` from the `--json` answer — without it the session cannot be checked or cleaned up.

**A `--command` session is remembered.** The command persists as `SessionSnapshot.initialCommand` and
re-runs on restore when *Restore running commands on restart* is on. App-global `restore clear`
deliberately does **not** clear it — that only wipes *captured foreground* commands. Fine when you want
the session to come back as itself; use the per-session `session restore` override when you do not.

## Window commands, and the floor that defeats a sidebar-only capture

`agtermctl window <new|list|select|close|rename|delete|resize|move|zoom|fullscreen|minimize>`
manages the OS windows themselves — `resize --width W --height H`, `move`, and
`zoom` (a maximize toggle) are enough to stage a window for a screenshot and put
it back. `window list --json` reports `geometry`, `zoomed`, `sidebarVisible` and
the id, so the prior state is readable before changing it.

**There is a hard minimum width of ~640pt.** A `resize --width 250` silently
lands at 640. That kills the obvious way to photograph the session sidebar as a
*window* (which would carry transparent rounded corners for free): at 640 the
pane beside it is still showing, and its content is a live conversation. Two
consequences:

- the sidebar has to be captured as a screen **region**, and rounded corners
  added in post-processing — see `macos-app-automation-and-capture.md`;
- `session scratch on` does **not** blank the pane for this purpose. It also
  forces the window wider (observed 1111pt), so it fights the resize as well.

Selecting a different session does not help either — every pane holds some
conversation. Assume the pane is unpublishable and crop it out.

### `tree --json` shows one window, and nothing in the answer says so

A bare `agtermctl tree --json` projects the **frontmost** window only. It returns
an ordinary `workspaces[]` array, just a short one, so on a single-window setup it
is indistinguishable from "every session on the machine" — which is exactly how it
gets mistaken for one. Enumerate instead:

```bash
agtermctl window list --json          # then, per open id:
agtermctl tree --json --window <id>
```

Filter `window list` on `open != false` first: closed windows are listed too, and
`tree --window <closed>` errors with "window not open", costing a failed
subprocess each.

The resulting bug is **permanent, not late**, which is what makes it worth
writing down. A caller that reads the frontmost window, finds a session missing
and intends to "ask again next time" never recovers — asking again resolves to
the same window, so the miss ends only when the *user* brings the other one
forward. Caught in tauri-dashboard 2026-09-02, where a session in a background
window would have been permanently invisible while a retry loop re-asked forever.
Anything genuinely per-window has the same shape: `idleMs` covers the projected
window, and each window has its own selected session.

## The sidebar's status glyph comes from whatever wrote the OSC title

Nothing in agterm produces those marks. `displayName = customName ?? oscTitle ??
cwd basename`, so a row reading `✋ bga-assistant [70%]` is showing a title some
other program wrote — for this fleet, the dashboard's `terminal_title::sync`.
The red count badge beside it *is* agterm's own, and the two are easy to
conflate when reading a screenshot.
