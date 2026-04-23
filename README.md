# Claude Code Skills

A collection of reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills, hooks, and utility scripts for implementation planning, PR workflows, and architecture documentation.

## Skills

---

### Plan Implementation

Interactive design discussion that produces a structured plan document before any code is written.

**Command:** `/plan-ralphex`

**Features:**
- Researches the codebase to understand current architecture and patterns
- Asks clarifying questions and discusses design trade-offs
- Iterates on the approach until you're satisfied
- Outputs a plan in `docs/plans/` with design decisions, file changes, and task breakdown

---

### Create / Update PR

Prepares commits on a feature branch, pushes, and opens or updates a PR to main.

**Command:** `/pr-create`

**Features:**
- Reads the associated plan document and progress log for context
- Uses `/reset` and `/commit` to create clean, atomic commits from branch changes
- Rebases onto main before pushing so pr-merge can fast-forward
- Creates a new PR or updates the existing one (title, description, force-push)
- Drafts a detailed PR description with overview, changes, design decisions, and scope reconciliation

---

### Merge PR

Merges a PR locally via fast-forward to preserve your GPG-signed commits.

**Command:** `/pr-merge`

**Features:**
- Avoids GitHub's merge UI, which re-signs commits with GitHub's own key
- Fast-forwards main to the PR branch (rebases as fallback if needed)
- Stashes uncommitted changes and restores them after merge
- Cleans up remote and local branches, prunes stale remote-tracking refs

---

### Prepare PR

Summarizes what was done, how it matches the plan, and what the review found — all in one report before creating a PR.

**Command:** `/pr-prepare`

**Features:**
- Reads the plan doc, progress logs, and commits to build a complete picture
- Reports plan alignment: implemented items, unplanned additions, missing items
- Summarizes review findings: confirmed fixes, false positives, unaddressed concerns
- Read-only analysis — does not modify files or create commits

---

### Clean Code

Audits modified files for dead code, duplication, and import hygiene.

**Command:** `/clean-code`

**Features:**
- Removes debug prints left from development
- Dead code audit: traces callers to find unreachable methods, fields, imports, type members
- Duplication audit: flags repeated logic and proposes consolidation
- Optimizes imports in modified files
- Iterates until clean — each removal pass may reveal new dead code

---

### Commit

Analyzes changes and generates atomic Conventional Commit messages.

**Command:** `/commit`

**Features:**
- Reviews staged and unstaged changes, groups them into atomic commits
- Delegates to `/clean-code` and `/documentation` before planning commits
- Drafts commit messages in imperative mood with type prefixes
- Presents a full plan for approval before executing any commits
- GPG-signs all commits, never adds AI attribution

---

### Update Documentation

Scans project documentation for stale references and fixes them.

**Command:** `/documentation`

**Features:**
- Checks README, `docs/pages/`, CLAUDE.md, and source comments against current code
- Fixes stale paths, API references, and behavior descriptions
- Suggests new documentation files or reorganization when beneficial

---

### Deploy

Configures the deployment pipeline for a supported project (.NET, Tauri, or IntelliJ plugin) and runs it. On first use in a project, sets up the `deploy` bash function, creates a local `scripts/deploy.sh` wrapper, and updates `.gitignore`. Then builds, deploys to the install directory, and verifies the app starts.

**Command:** `/deploy`

**Features:**
- Auto-configures `deploy()` bash function in `~/.bashrc` if missing
- Creates `scripts/deploy.sh` wrapper pointing to the global deploy script
- Reads install path from `config/deploy.env` (asks on first run)
- Runs the full pipeline: stop app → build → clean install dir → copy → launch → verify
- After first `/deploy`, use `! deploy` for instant deploys without LLM overhead

---

### Build

Configures a build shortcut for any project. On first use, sets up the `build` bash function, creates a local `scripts/build.sh` wrapper, and updates `.gitignore`. Then auto-detects the project type and builds.

**Command:** `/build`

**Features:**
- Auto-configures `build()` bash function in `~/.bashrc` if missing
- Creates `scripts/build.sh` wrapper pointing to the global build script
- Auto-detects project type: `package.json` → `npm run build`, `src/*.csproj` → `dotnet build`
- After first `/build`, use `! build` for instant builds without LLM overhead

---

### Release

Tags a new version, pushes to trigger CI, monitors the build, and updates the GitHub release with final notes.

**Command:** `/release`

**Features:**
- Validates preconditions: clean tree, on main, in sync with remote
- Auto-detects project name from `.csproj` and GitHub repo info
- Recommends version bump based on commit history, asks for confirmation
- Compiles release notes from commits with SmartScreen warning and download table
- Pushes tag, monitors the GitHub Actions workflow until completion
- Updates release notes with actual asset sizes after CI produces the artifacts

---

### Document Data Flow

Generates or updates a data-flow architecture document (`docs/data-flow.md`).

**Command:** `/document-data-flow`

**Features:**
- Discovers the project's architecture by exploring the codebase
- Produces step-by-step flow diagrams with data transition annotations
- Generates message/API protocol tables for all message types and endpoints
- Follows strict formatting rules for consistency across updates

---

### Update Plannotator Plugin

Force-updates the plannotator plugin by clearing stale caches and reinstalling.

**Command:** `/plannotator-update`

**Features:**
- Removes the marketplace cache (stale git clone that prevents updates)
- Removes the plugin cache
- Guides through reinstallation after restart

---

## Hooks

### External Hook Paths

When a hook command needs a path outside `~/.claude/` or this repo, reference it via a `CLAUDE_<NAME>` user-scope environment variable instead of hardcoding the absolute path. The hook `command` field is executed via shell, so standard `$VAR` expansion works — the same mechanism that already makes `$HOME/.claude/hooks/...` portable across machines.

**Why:** `claude/settings.json` is symlinked to `~/.claude/settings.json` on every machine that uses this repo. Hardcoded absolute paths pin it to one user's filesystem layout; env vars keep it portable, and a repo move or rename only touches the env var (not every hook entry).

**Caveat:** This works for hook `command` strings only. It does **not** work for MCP server args in `~/.claude.json` — those are passed straight to `child_process.spawn()` with no shell, so paths there must be absolute. That file is not symlinked from this repo.

**Currently used env vars** — set these on a fresh machine before the corresponding hooks will work:

- **`CLAUDE_AI_AGENT_DASHBOARD`** — points to a local clone of the `tauri-dashboard` repo. Used by the `Notification`, `UserPromptSubmit`, `Stop`, `SessionEnd`, and `SessionStart` hooks for live session-status updates.

**Set on Windows** (User scope, persistent):

```powershell
[Environment]::SetEnvironmentVariable('CLAUDE_AI_AGENT_DASHBOARD', 'D:/projects/tauri-dashboard', 'User')
```

**Set on Linux / macOS** (in your shell profile):

```bash
export CLAUDE_AI_AGENT_DASHBOARD="$HOME/projects/tauri-dashboard"
```

---

## Git Hooks

### Pre-Push Validation

**File:** `git/hooks/pre-push`

Prevents pushing commits that are Claude-attributed or not GPG-signed. Every new commit in the push is checked for:

- Author or committer name/email containing "claude" or "anthropic"
- `Co-Authored-By` trailers mentioning Claude or Anthropic
- Missing good GPG signature (only `G` status passes)

**Global installation** is covered in the [Global Installation](#global-installation) section below.

---

## Learnings

Domain-specific knowledge files in `claude/learnings/` are available globally via the `~/.claude/learnings/` symlink. To use them in a project, add a line to that project's `CLAUDE.md`:

```
Read `~/.claude/learnings/chrome-extension.md` for domain-specific patterns.
```

| File | Domain |
|---|---|
| `anthropic-oauth-usage.md` | Undocumented `/api/oauth/usage` endpoint (5h/7d rate-limit utilization for Claude Code OAuth tokens) |
| `autohotkey.md` | AutoHotkey v2 patterns (hotkeys, clipboard, folder watchers, tray scripts) |
| `chrome-extension.md` | Chrome extensions (Manifest V3, Vite, side panel, service workers) |
| `claude-code-integration.md` | Observing Claude Code sessions (hooks, transcript JSONL, state classification) |
| `css-layout-gotchas.md` | Non-obvious CSS grid/flex/overflow behaviors in dashboard UIs |
| `dotnet-tray-app.md` | .NET Windows tray apps (WinForms/WPF, config, overlay, CI/CD) |
| `electron-windows-launcher.md` | Silent Electron launch on Windows (Startup folder, hidden BrowserWindow) |
| `git-line-endings.md` | CRLF/LF handling on cross-platform repos (`.gitattributes`, normalization) |
| `rust-serde-config-evolution.md` | Shipping Rust apps with schema-evolving override config files (container-level `#[serde(default)]`) |
| `shell-environment.md` | Shell config across bash/zsh/WSL (common functions, PATH, verification) |
| `skill-context-evaluator.md` | Constraints of the `!` backtick preprocessor in SKILL.md Context sections |
| `windows-terminal-title.md` | Why per-tab title manipulation from Claude Code hooks isn't feasible on WT |

---

## Scripts

Scripts in this section are written in [AutoHotkey v2](https://www.autohotkey.com/) (Windows-only). To run a script, install AutoHotkey v2 and double-click the `.ahk` file. To auto-start a script with Windows, place a shortcut to it in your Startup folder — press <kbd>Win+R</kbd>, type `shell:startup`, and drop the shortcut there.

---

### Monosnap Watcher

**File:** `scripts/monosnap-watcher.ahk` (AutoHotkey v2)

Claude Code can't receive pasted images — it needs a file path. Monosnap (a screenshot tool) can auto-save captures to a folder, but doesn't copy the file path to the clipboard. This script bridges the gap: polls the folder given by `MONOSNAP_DIR` every 500ms; on each new file, copies the full path to the clipboard and shows a `TrayTip`. Look for "Monosnap Watcher" in the tray to confirm it's running.

**Setup:**
1. Set the `MONOSNAP_DIR` environment variable to your Monosnap auto-save folder (e.g. `C:\Users\OlegS\Monosnap`)
2. Install as a Windows startup shortcut pointing at `scripts/monosnap-watcher.ahk` — drop the shortcut into `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`

---

## Global Installation

Global files live in `claude/` (symlinked to `~/.claude/`) and `git/` (hooks, gitignore, gitattributes — each symlinked to `~/`). Project-local config stays in `.claude/`.

> If any of these already exist in `~/.claude/` or `~/.git-hooks/`, move them into the repo first (or remove them) before creating the symlink.

### Windows

Run from the project root *as Administrator*:

```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\CLAUDE.md" -Target "$PWD\claude\CLAUDE.md"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills" -Target "$PWD\claude\skills"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\hooks" -Target "$PWD\claude\hooks"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\settings.json" -Target "$PWD\claude\settings.json"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\learnings" -Target "$PWD\claude\learnings"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\memory" -Target "$PWD\claude\memory"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.git-hooks" -Target "$PWD\git\hooks"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.gitignore" -Target "$PWD\git\gitignore"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.gitattributes" -Target "$PWD\git\gitattributes"
git config --global core.hooksPath "$env:USERPROFILE\.git-hooks"
git config --global core.excludesFile "~/.gitignore"
git config --global core.attributesFile "~/.gitattributes"
```

### Linux / macOS

Run from the project root:

```bash
ln -s "$(pwd)/claude/CLAUDE.md" ~/.claude/CLAUDE.md
ln -s "$(pwd)/claude/skills" ~/.claude/skills
ln -s "$(pwd)/claude/hooks" ~/.claude/hooks
ln -s "$(pwd)/claude/settings.json" ~/.claude/settings.json
ln -s "$(pwd)/claude/learnings" ~/.claude/learnings
ln -s "$(pwd)/claude/memory" ~/.claude/memory
ln -s "$(pwd)/git/hooks" ~/.git-hooks
ln -s "$(pwd)/git/gitignore" ~/.gitignore
ln -s "$(pwd)/git/gitattributes" ~/.gitattributes
git config --global core.hooksPath ~/.git-hooks
git config --global core.excludesFile "~/.gitignore"
git config --global core.attributesFile "~/.gitattributes"
```

## License

[GPL-3.0](LICENSE)
