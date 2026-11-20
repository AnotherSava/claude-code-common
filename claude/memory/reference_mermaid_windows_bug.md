---
name: reference_mermaid_windows_bug
description: The claude-mermaid MCP plugin fails on Windows with "spawn npx ENOENT"; the fix and the local workaround are in the learnings
metadata:
  type: reference
---

The claude-mermaid plugin (veelenga/claude-mermaid) fails on Windows with `spawn npx ENOENT` when its MCP server runs the npm package through `npx -y`. Do not try `npx.cmd`: it fails with `EINVAL`. The diagnosis, the working `cmd.exe /c` fix and the plugin.json redirect to a built fork that makes `mermaid_preview` and `mermaid_save` work are in `~/.claude/learnings/claude-code-integration.md` ("Windows `execFile("npx", ...)` failure chain") and `~/.claude/learnings/claude-code-plugin-mcp-config.md` ("Concrete example"). Check which package actually runs before calling the bug present: the plugin.json version (1.2.0) is not the npm package version, and a redirected install runs the fork.
