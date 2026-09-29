---
created: 2026-09-29 13:22:32
platform: macos
---

# The github-status report server does not survive a reboot on macOS

On macOS the tailnet report URL is backed by serve-report.py, a detached loopback server on 127.0.0.1:8787 that tailscale serve proxies. The tailscale serve config itself lives in tailscaled and survives a reboot; the Python process does not, so after a reboot the published URL — `https://<this machine>.<tailnet>.ts.net/github-status.html` — answers 502 until the next /github-status run spawns the server again.

Windows and Linux are unaffected: they serve the file path directly with no process involved. This is macOS-only because the sandboxed App Store Tailscale build refuses path serving outright ("Path serving is not supported on macOS due to sandbox restrictions").

Decide whether to close it or accept it. A launchd LaunchAgent with KeepAlive would make the URL answer across reboots without a scan. Against that: the file it serves goes stale within hours (fetch counts, ages, convention gaps all move), so a link that answers after a reboot mostly serves a stale report, and every /github-status run republishes anyway. Accepting it costs nothing as long as the URL is always handed over fresh from a run, which is how the skill hands it over today.

The other route, if it is worth closing, is the open-source tailscaled distribution on macOS, which permits path serving and would remove the loopback server entirely — that is a bigger change to how Tailscale is installed on this box.

Files: claude/skills/github-status/scripts/serve-report.py, and publish_report() in claude/skills/github-status/scripts/repos-status.py.
