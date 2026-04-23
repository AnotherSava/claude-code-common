# Claude Code plugin MCP config — locating and redirecting

A Claude Code marketplace plugin's MCP server command is usually embedded in `plugin.json` under `mcpServers`, **not** in a sibling `.mcp.json` — the latter often exists but is vestigial for plugins that use the `plugin.json`-embedded form. When a plugin redirect edit doesn't take effect, the most likely cause is that you edited `.mcp.json` when the authoritative definition was in `plugin.json`.

## Where the config lives

For a plugin installed via `/plugin install <plugin>@<plugin>`:

- `~/.claude/plugins/marketplaces/<plugin>/.claude-plugin/plugin.json` — marketplace definition; this is authoritative on next resolve.
- `~/.claude/plugins/cache/<plugin>/<plugin>/<version>/.claude-plugin/plugin.json` — the installed copy. Claude Code reads this at startup.
- `~/.claude/plugins/marketplaces/<plugin>/.mcp.json` and `~/.claude/plugins/cache/<plugin>/<plugin>/<version>/.mcp.json` — may or may not exist depending on the plugin's layout. For plugins that put `mcpServers` in `plugin.json`, these files are ignored.

Both `plugin.json` files share a block shaped like:

```json
{
  "mcpServers": {
    "<name>": {
      "command": "npx",
      "args": ["-y", "<plugin-package>"]
    }
  }
}
```

Editing only the cache copy is not enough — the marketplace copy is re-read when the plugin resolves on startup. Edit both.

## Redirect recipe (local fork of a plugin)

Useful when upstream has merged a fix but not yet cut an npm release, or when you want to test a patch before proposing it upstream.

1. Build the fork: `npm --prefix <fork-path> install && npm --prefix <fork-path> run build` (adapts to whatever the plugin's build script produces — for a typical `tsc`-based Node MCP plugin that's `build/index.js`).
2. Replace the `mcpServers.<name>` block in **both** `plugin.json` locations with:
   ```json
   {
     "command": "node",
     "args": ["<absolute-path>/build/index.js"]
   }
   ```
   Keep the key under `mcpServers` the same — that name is what the tool IDs (`mcp__plugin_<pkg>_<name>__<tool>`) are built from.
3. **Fully restart Claude Code** (close the process, reopen). A `/exit` within the same shell is not enough — the MCP server subprocess is spawned once at session start and stays alive across `/exit` in some setups.
4. Caveat: the plugin updater can overwrite these edits the next time the plugin publishes a new version. If symptoms return after an auto-update, reapply.

## Diagnosing "the edit didn't take effect"

Run this from PowerShell to see which command actually spawned the plugin's node process:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "<plugin>" } |
  Select-Object ProcessId, ParentProcessId, Name, CommandLine |
  Format-List
```

If the running `node.exe` command line still contains the upstream `npx -y <plugin>` invocation instead of `node <abs-path>/build/index.js`, Claude Code didn't pick up the redirect. Check that:

- You edited the correct file (search for `"mcpServers"` in both `plugin.json` locations — if neither contains it, the plugin doesn't use the embedded form and you need to look elsewhere).
- Claude Code was fully restarted, not just reloaded.

Walking the parent PID chain (`ParentProcessId` → its process → its parent) up to the Claude Code binary (`@anthropic-ai\claude-code\bin\claude.exe`) confirms that your session is the one that spawned the process.

## Concrete example

The `claude-mermaid` plugin had a Windows spawn bug: `execFile("npx", args)` failed with `spawn npx ENOENT` because Node.js doesn't resolve `.cmd` shims, and `spawn("npx.cmd", ...)` later fails with `spawn EINVAL` post-CVE-2024-27980. The fix (PR veelenga/claude-mermaid#117) wraps the call with `cmd.exe /c` on Windows.

The PR was merged upstream on 2026-04-21 but the latest npm release was 1.6.2 from March, so `npx -y claude-mermaid` still installed the buggy version. Redirecting the local install to a built fork (e.g. `<fork-path>/build/index.js`) via both `plugin.json` files unblocked `mermaid_preview` / `mermaid_save` on Windows until the fix lands on npm.

Initially I edited both `.mcp.json` files first without realizing they were vestigial. Three unsuccessful rounds of `/exit` + reopen later, `grep` turned up `"mcpServers"` inside `plugin.json` and the real fix took one edit.
