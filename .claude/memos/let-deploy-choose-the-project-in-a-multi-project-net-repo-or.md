---
created: 2026-10-01 03:29:29
---

# Let /deploy choose the project in a multi-project .NET repo, or defer to its own build script

Found by the agwinterm session on 2026-10-01 when /deploy ran in that fork (yeroo/agwinterm upstream).

The deploy skill's .NET probe in SKILL.md is ls src/*.csproj, and its scripts/deploy.sh takes CSPROJ from the same glob piped through head -1. agwinterm keeps its five projects one level deeper (src/Agwinterm.Core, .Win32, .Ctl, .Pty, .App, each with its own csproj), so the probe reports '.NET project: no' and the skill falls through to its STOP text saying it recognises no stack.

Widening the glob to src/*/*.csproj is not the fix: head -1 would pick Agwinterm.App, a second front end nobody installs, and publishing one project misses agwintermctl and the Rust pty-host the managed side has an ABI handshake with.

The design call: a config key naming the project or projects to publish, or deferring to the repo's own build script when it has one (agwinterm has installer/build.ps1; the user's per-machine scripts/deploy.sh there already runs it and hands the setup to a detached helper).

Two smaller points in the same file: the STOP text describes .NET to the user as src/*.csproj, inheriting the blind spot; and config/deploy.env is documented as committable, which in a third-party clone means adding a tracked file to someone else's repo (a fork is different now that forks adopt conventions).
