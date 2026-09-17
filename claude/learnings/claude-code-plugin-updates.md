# Updating a Claude Code plugin, and the registry that silently disagrees with the cache

Companion to `claude-code-plugin-mcp-config.md`, which covers where a plugin's MCP
definition lives. This one is about versions: which file records them, which one the
loader actually obeys, and why the two drift apart.

## Three places a version is written, and only one is authoritative

```
~/.claude/plugins/marketplaces/<name>/            a git clone of the marketplace repo
~/.claude/plugins/cache/<name>/<name>/<version>/  the installed copy; carries .in_use
~/.claude/plugins/installed_plugins.json          the registry: version, installPath, gitCommitSha
```

The loader follows the cache directory carrying `.in_use`. The registry is bookkeeping,
and `claude plugin list` reports **the registry**, not the cache. So the number you read
and the code you run are two different facts.

## Deleting the cache does not clear the registry

The force-update recipe that circulates for a stale marketplace clone is

```bash
rm -rf ~/.claude/plugins/marketplaces/<name>/
rm -rf ~/.claude/plugins/cache/<name>/
# then /plugin marketplace add … and /plugin install …
```

The `rm -rf` pair removes the clone and the installed copy. It leaves
`installed_plugins.json` untouched, so the follow-up install answers

```
Plugin '<name>@<name>' is already installed globally. Use '/plugin' to manage existing plugins.
```

and writes nothing. Measured 2026-09-17: after that sequence the cache held only
`0.27.15` while the registry still said `0.19.4` with an `installPath` pointing at a
directory that no longer existed and a `gitCommitSha` from four months earlier.
`claude plugin list` reported 0.19.4 throughout, while the plugin actually loaded was
0.27.15 — the marketplace `add` had re-fetched and re-installed it under the new
version, and `.in_use` was on that one.

Nothing errors in this state. The only tell is that the recorded `installPath` does not
exist on disk, which nothing checks.

## The repair is one command, and it is not uninstall

```bash
claude plugin update <name>@<marketplace>
```

```
✔ Plugin "<name>" updated from 0.19.4 to 0.27.15 for scope user. Restart to apply changes.
```

It rewrites `version`, `installPath`, `gitCommitSha` and `lastUpdated` to match what is
on disk. No uninstall, no second cache deletion, no hand-editing the JSON. Reach for it
before anything destructive whenever `claude plugin list` disagrees with the cache
directory — including the two-copies case, where a plugin's cache holds both `unknown`
and a sha-named directory and the registry names the stale one.

The whole `claude plugin` CLI is non-interactive, which the `/plugin` slash commands are
not: `list`, `install`, `uninstall`, `update`, `marketplace add|update|list|remove`,
`enable`, `disable`, `details`. Use it from a script or a tool call rather than asking a
human to type slash commands.

## A tool that ships as both a plugin and a CLI has two update paths

Do not assume one covers the other. For plannotator, measured the same day:

| Path | Moves | Does not move |
|---|---|---|
| `/plannotator-update` (rm the two caches, reinstall) | marketplace clone, plugin cache | the `~/.local/bin` binary |
| `curl -fsSL https://plannotator.ai/install.sh \| bash` | the binary, and the skills under `~/.claude/skills/` | the plugin cache / registry |

So a box can sit with a current plugin and an eight-month-old CLI, reporting the new
number from `claude plugin list` and the old one from the binary's own `--version` — or
print nothing at all for `--version`, `-v` and `version` alike, because the flag
postdates what is installed. An empty-but-zero-exit version probe means *old*, not
*absent*.

Check both before calling a tool current, and resolve "latest" against the source rather
than a number someone quoted:

```bash
curl -fsSL https://api.github.com/repos/<owner>/<repo>/releases/latest |
  python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])"
```

## Where a plugin's commands and skills come from can change under you

A plugin that once shipped `commands/` may stop. plannotator's plugin package resolves
to `./apps/hook` in its `marketplace.json`, and at 0.27.15 that directory holds only
`README.md`, `hooks/`, `server/`, `index.html`, `index.tsx` and build config — no
`commands/`, no `skills/`, no `SKILL.md`. The three `plannotator-*` skills now come from
the standalone installer instead, written into `~/.claude/skills/`.

Read the upstream tree before planning around the current layout; a fetched marketplace
clone answers without installing anything:

```bash
git -C ~/.claude/plugins/marketplaces/<name> fetch -q
git -C ~/.claude/plugins/marketplaces/<name> ls-tree -r --name-only @{upstream} -- <plugin-subdir>
```

The practical consequence: a cleanup plan built on "delete the loose copies, keep the
plugin's" expires the moment the plugin stops shipping them. Update first, look at what
the new version wrote, then deduplicate.
