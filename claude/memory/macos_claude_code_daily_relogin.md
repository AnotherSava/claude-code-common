---
name: macos_claude_code_daily_relogin
description: macOS Claude Code asks to /login ~daily due to a keychain OAuth refresh bug; Windows (plain-file creds) unaffected
metadata:
  type: reference
---

On macOS, Claude Code (native install, `~/.local/bin/claude`) stores OAuth credentials in the login Keychain (generic password "Claude Code-credentials"). It asks to `/login` roughly once a day because of a known refresh bug: the access token expires (~8h) and the refresh token isn't used — the CLI invalidates the cached credentials instead of silently refreshing, forcing a manual re-login. Tracked in anthropics/claude-code (issues ~#28302 / #31095 — numbers approximate, from web search). Frequent auto-updates may aggravate it. The keychain entry itself is healthy (verified 2026-06-06: present, recently updated, no ACL restriction), so it is **not** ACL loss after a binary update.

Windows never re-prompts because it stores credentials in a plain `~/.claude/.credentials.json` file, which doesn't go through the macOS keychain-refresh path.

Workarounds (it's an Anthropic-side bug — no local config fully fixes it): just re-run `/login`; click **"Always Allow"** (not one-time "Allow") on any keychain prompt after an update; try `security unlock-keychain ~/Library/Keychains/login.keychain-db` if the logouts correlate with sleep/lock. For headless/scripted use there's `claude setup-token` + `CLAUDE_CODE_OAUTH_TOKEN`, but that's not meant for daily interactive sessions.
