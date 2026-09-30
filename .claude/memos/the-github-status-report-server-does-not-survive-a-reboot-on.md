---
created: 2026-09-29 13:22:32
---

# The tailnet publish server does not survive a reboot

Every tailnet URL handed over — the github-status report at `https://<this machine>.<tailnet>.ts.net/github-status.html`, and every file published with tailnet_publish.py — is backed by one detached loopback server on 127.0.0.1:8788 that `tailscale serve` proxies. This holds on both machines: the macOS App Store Tailscale build refuses path serving ("Path serving is not supported on macOS due to sandbox restrictions"), and Windows refuses it to a non-admin shell ("must be a Windows local admin to serve a path or Unix socket"). The serve config lives in tailscaled and survives a reboot; the Python process does not, so after a reboot every published URL answers 502 until the next publish spawns the server again.

Decide whether to close it or accept it. A per-platform autostart (a launchd LaunchAgent with KeepAlive on macOS, a logon scheduled task on Windows) would make the URLs answer across reboots. Against that: most published files are reports that go stale within hours, so a link answering after a reboot mostly serves a stale file, and every run that hands a URL over republishes it anyway. Accepting it costs nothing as long as a URL is always handed over fresh from a publish, which is how github-status and the CLAUDE.md rule hand it over today. The case for closing it is a link the user reopens days later, such as a contact sheet.

The other route is the file form of `tailscale serve`, which needs no process: on macOS it takes the open-source tailscaled distribution, on Windows an elevated shell. Neither fits an agent's normal shell on both machines, so the loopback server stays the shared shape either way.

Files: claude/skills/shared/tailnet_publish.py (server log at ~/.claude/tailnet-publish/server.log), and publish_report() in claude/skills/github-status/scripts/repos-status.py.
