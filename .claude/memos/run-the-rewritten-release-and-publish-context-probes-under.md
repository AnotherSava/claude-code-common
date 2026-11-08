---
created: 2026-11-08 10:42:38
platform: macos
---

# Run the rewritten release and publish Context probes under zsh on the Mac

On 2026-11-08 the Windows session rewrote the Context probes in claude/skills/release/SKILL.md (.NET project, AssemblyName, Signing policy, Tauri Cargo version) and claude/skills/publish/SKILL.md (Compose file, Vhost file, CI publish workflow), plus matching probes in build, cleanup, deploy, heartbeat and publish-chrome-extension SKILL.md, from '| head -1 || echo X' to capture-then-test, with every glob quoted. Bash was exercised on an empty and a populated repo; zsh is not installed on Windows, so the claim that zsh nomatch can no longer abort them is unverified. Next step on the Mac: in an empty git repo and one holding src/App.csproj, src-tauri/Cargo.toml, web/docker-compose.yml, web/deploy/site.caddy and .github/workflows/deploy-x.yml, run each probe line under zsh -c and confirm the fallback (no/n/a/none) on the empty one and the value on the populated one.
