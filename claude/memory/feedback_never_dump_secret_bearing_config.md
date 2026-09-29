---
name: Never dump a secret-bearing config section
description: To check a setting in a config file, print only the named keys or masked values — a whole section can carry a credential into the transcript
metadata:
  type: feedback
---

When reading a config file to check a setting, print only the keys the question needs, and mask any value that could be a credential. Never print a whole section or the whole file.

**Why:** on 2026-09-27 a quick check of two flags in a desktop app's `config.json` printed its `notifications` block wholesale, and that block held a Telegram bot token in plaintext. Once a value is in the transcript it has left the machine, so the only remedy was rotating it — which took a BotFather revoke, a Doppler update, a redeploy and a sweep for other copies, and ended in switching bots. Nothing flagged the print: the file was not named like a secrets file, and the safety classifier that blocks an explicit `doppler secrets get` let a `json.load` + `print` straight through.

**How to apply:** select the keys by name (`c['high_alert']`, not `c['notifications']`), or print structure only (key names, value types, lengths, a masked prefix such as `sed -E 's/("[^"]*token[^"]*": *")([^"]{6})[^"]*"/\1\2…"/'`). Treat any config that feeds a notifier, a sync peer, an API client or a deploy as secret-bearing until shown otherwise. Git's own config counts: in a transcrypt repo `git config --list` prints `transcrypt.password`, and on 2026-09-28 an audit of stray local settings did exactly that, within the hour of this rule being committed. Ask for the keys in question with `git config --get <key>`. When a value genuinely has to be used, pipe it straight into its consumer as `/doppler` describes, and report a derived fact (a length, a `getMe` username, a digest) rather than the value. See [[feedback_doppler_secrets]] and [[feedback_rotate_dont_abandon]].
