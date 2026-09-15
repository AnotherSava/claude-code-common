---
created: 2026-09-15 08:43:56
platform: windows
---

# Run the memo backlog gate on the Windows box — the platform field and the narrowed flag parser were verified on macOS only

Added 2026-09-15 in the change that gave memos an optional `platform:` frontmatter field. Everything in it was written, run and mutation-checked on the mac; nothing was executed on Windows.

## Why it needs the other box

`.claude/commit-checks.sh` states the reach in its own header: everything under `claude/` is symlinked into `~/.claude/` on both machines, so a defect in `memos-surface.py` fires at every session start everywhere. The `memo` PowerShell wrapper in `learnings/shell-environment.md` calls `memos.py add` on that box daily.

## What to run

From the dotfiles repo root, after pulling:

    bash .claude/commit-checks.sh

Expected: the `memos.py` suite passes. Its platform cases are written against `memos.THIS_PLATFORM` rather than literals, so on that box `HERE` resolves to `windows` and `OTHER` to `macos`, and the same assertions hold with the values swapped. The one that would fail first is `check("this machine's platform is one memos.py names", HERE in memos.PLATFORMS)`, which is the guard for exactly this.

## The specific things unverified there

1. **`THIS_PLATFORM`** maps `sys.platform` `win32` to `windows`. Read, not observed.
2. **`_take_flag` was narrowed** to the leading run of `--flag value` pairs. Confirm the PowerShell `memo` wrapper still forwards `--title` and `--platform` — it passes `$args` straight to `add`, so flags must come first.
3. **The status-bar hook** now carries `tag` and `elsewhere` in its per-session state file and counts bound memos behind the `+N more` line. Check the bar renders at session start and that the em-dash and bracketed tags survive the console codepage — `memos-surface.py` reconfigures stdout to UTF-8 for this reason, and this repo's backlog now has two `[windows]` titles to render.

## Why this is a memo and not a ping

Checked at capture time: `ListAgents` showed six live sessions, all on this machine. No session on the Windows box was reachable, so there was nobody to route it to.
