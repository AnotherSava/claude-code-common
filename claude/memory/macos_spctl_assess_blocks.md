---
name: macos-spctl-assess-blocks
description: spctl --assess raises a blocking Touch ID/password dialog on macOS 26; never run it from a subagent or background task
metadata:
  type: reference
---

On macOS 26, `spctl --assess` (both `-t exec` and `-t install`) raises a LocalAuthentication Touch ID / password dialog and **blocks** until a human answers it. The unified log records it as `coreautha ... [LADFRController] -[LADFRController _iconFromPath:] /usr/sbin/spctl` — the dialog takes its icon and name from the requesting binary, so it reads to the user as "install spctl from an identified developer", which sounds like a software install and is not one. `spctl` is a built-in Apple binary at `/usr/sbin/spctl` (`Identifier=com.apple.spctl`); nothing is being downloaded.

Cost when this fires in a subagent: the agent hangs mid-task with no output, looking like a stalled API call, while a modal the user didn't expect sits on their screen.

**How to apply:** For read-only Gatekeeper/signature inspection use `codesign -dvvv`, `codesign -d --entitlements -`, and `xattr -l` / `xattr -r -l` — none of which prompt. Reserve `spctl` for interactive sessions where a prompt is acceptable.

More generally: instructing a subagent "non-destructive, no sudo" does **not** prevent credential prompts. When agents run on a machine with a human present, ban prompt-raising commands by name — `spctl`, `sudo` (including `sudo -n`), `osascript ... with administrator privileges`, `security`, `gktool`, `pmset -a`, `launchctl load` of anything under /Library, and `open` of any GUI app.

Related: [[reference_push_hook]]
