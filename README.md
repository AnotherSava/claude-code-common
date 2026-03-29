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

### Create PR

Squashes a feature branch into a single Conventional Commit, pushes, and opens a PR to main.

**Command:** `/pr-create`

**Features:**
- Reads the associated plan document and progress log for context
- Drafts a commit message explaining motivation and key decisions
- Asks for your approval before committing
- Rebases onto main before pushing so pr-merge can fast-forward
- Handles force-push when the branch was previously pushed with unsquashed commits

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

Analyzes plan-vs-implementation divergence before creating a PR.

**Command:** `/pr-prepare`

**Features:**
- Compares the most recent completed plan against the progress log and unpushed commits
- Surfaces unplanned additions, missing plan items, and design divergences
- Identifies review-driven changes in commit history
- Read-only analysis — does not modify files or create commits

---

### Update PR

Soft-resets unpushed commits and delegates to `/commit` for clean atomic commits, then pushes to update an existing PR.

**Command:** `/pr-update`

**Features:**
- Detects new changes since the last push (unpushed commits + uncommitted changes)
- Soft-resets unpushed commits and delegates to `/commit` for re-grouping
- Rebases onto main and force-pushes with lease
- Appends an update summary to the PR description

---

### Commit

Analyzes changes and generates atomic Conventional Commit messages.

**Command:** `/commit`

**Features:**
- Reviews staged and unstaged changes, groups them into atomic commits
- Drafts commit messages in imperative mood with type prefixes
- Updates stale documentation and optimizes imports before committing
- Presents a full plan for approval before executing any commits
- GPG-signs all commits, never adds AI attribution

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

### Review Summary

Summarizes a ralphex review — what was found, fixed, and dismissed.

**Command:** `/review-summary`

**Features:**
- Reads the most recent progress log from `.ralphex/progress/`
- Identifies committed but unpushed changes against `origin/main`
- Produces a concise summary: confirmed fixes, unaddressed concerns, and false positives

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

### Telegram Notification

Sends a Telegram message when Claude Code finishes a task and the user hasn't interacted for 60 seconds. Useful for long-running autonomous workflows.

**Location:** `claude/hooks/notifications/telegram.py`

**How it works:**
- `Notification` hook fires when Claude stops, waits 60 seconds, then checks the session log mtime to detect any user interaction (prompts, tool approvals, etc.) — if idle, sends a Telegram message with the project name and last prompt
- `UserPromptSubmit` hook saves the prompt text (for display in notifications) and auto-deletes any pending notification when the user returns

**Setup:** Create `claude/hooks/notifications/.env` with:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
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
| `chrome-extension.md` | Chrome extensions (Manifest V3, Vite, side panel, service workers) |

---

## Scripts

Scripts in this section are written in [AutoHotkey v2](https://www.autohotkey.com/) (Windows-only). To run a script, install AutoHotkey v2 and double-click the `.ahk` file. To auto-start a script with Windows, place a shortcut to it in your Startup folder — press <kbd>Win+R</kbd>, type `shell:startup`, and drop the shortcut there.

---

### Monosnap Watcher

**File:** `scripts/monosnap-watcher.ahk` (AutoHotkey v2)

Claude Code can't receive pasted images — it needs a file path. Monosnap (a screenshot tool) can auto-save captures to a folder, but doesn't copy the file path to the clipboard. This script bridges the gap: it watches the Monosnap output folder and copies the path of each new screenshot to the clipboard, so you can paste it straight into Claude Code.

**Setup:** Set the `MONOSNAP_DIR` environment variable to your Monosnap auto-save folder (e.g. `C:\Users\OlegS\Monosnap`).

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
ln -s "$(pwd)/git/hooks" ~/.git-hooks
ln -s "$(pwd)/git/gitignore" ~/.gitignore
ln -s "$(pwd)/git/gitattributes" ~/.gitattributes
git config --global core.hooksPath ~/.git-hooks
git config --global core.excludesFile "~/.gitignore"
git config --global core.attributesFile "~/.gitattributes"
```

## License

[GPL-3.0](LICENSE)
