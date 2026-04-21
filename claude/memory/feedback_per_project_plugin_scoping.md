---
name: Prefer per-project plugin scoping
description: Put enabledPlugins in project .claude/settings.json rather than global; plugins bloat every session's context when enabled globally
type: feedback
---

When enabling a Claude Code plugin, default to per-project scope (`.claude/settings.json` or `.claude/settings.local.json`) unless the plugin is genuinely needed in every session. Globally enabled plugins (`~/.claude/settings.json` → `enabledPlugins`) contribute skills and MCP tool schemas to the context window of *every* session — silently wasted tokens outside their niche.

**Why:** On 2026-04-20, I added `rust-analyzer-lsp@claude-plugins-official` to the global settings. The user flagged it: LSP plugins typically expose 10–20 MCP tools, so carrying them into non-Rust sessions is pure overhead. The entry was moved to `tauri-dashboard/.claude/settings.local.json` and dropped from global. Each enabled plugin adds skills/MCP surface visibly in the system prompt's "available skills" list and tool roster — that cost is constant per session, whether the plugin is used or not.

**How to apply:** Before editing global `enabledPlugins`, ask: "Do I want this in every project's context?" If no, put it in the specific project's `.claude/settings.json` (team-shared) or `.claude/settings.local.json` (local preference). Language-specific LSP/tooling plugins almost always belong per-project. Cross-project utility plugins (e.g. diagram renderers, web scraping) may justify global enablement if used frequently enough across unrelated work.
