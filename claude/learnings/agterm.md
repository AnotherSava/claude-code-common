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
