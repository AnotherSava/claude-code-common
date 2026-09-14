---
created: 2026-09-14 06:15:36
---

# swift-lsp is enabled globally on a box with no Swift toolchain

The `enabledPlugins` block in `claude/settings.json` carries `"swift-lsp@claude-plugins-official": true`. It arrived in aca16a5, whose subject is "fix(hooks): run every Python hook in UTF-8 mode" and whose message does not mention it — the plugin list gained one entry inside a large diff that was mostly key reordering and quote unescaping, and the plan shown at the time read +45/-37 for what was described as a one-line addition.

It is the plausible companion to the .swift capture helpers added in 3090ad6, which are macOS-only by construction. On the Windows machine there is no Swift toolchain for it to talk to, so it loads for nothing on every session there.

Nothing is observably broken — this is about a global plugin nobody chose deliberately, on one of the two machines that share this config. Found during the Windows verification of 2026-09-13 and reported to the Mac session then; never decided either way.

Worth doing: decide whether it is wanted at all. If it is, leave it and the entry is closed. If it is only wanted on the Mac, note that enabledPlugins in this file is shared by both machines, so 'enable it per-machine' is not available without splitting the setting — which is probably more machinery than the plugin is worth.
