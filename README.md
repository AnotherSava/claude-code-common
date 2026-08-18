# Claude Code Environment

A complete [Claude Code](https://docs.anthropic.com/en/docs/claude-code) environment: global guidelines, reusable skills, hooks, settings, version-controlled memory and learnings, and shared git configuration — everything symlinked into place from one repo.

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
- Delegates to `/reflect`, `/clean-code`, and `/documentation` before planning commits
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
- Keeps curated feature listings (features page, docs index, README) in sync with the diff
- Regenerates dimensioned-draft drawings when the model they document changed
- Suggests new documentation files or reorganization when beneficial

---

### Create GitHub Repository

Creates a GitHub repo for a local project that has content but no remote yet, then wires it up without publishing anything. The remote ends up holding exactly one commit — a LICENSE — with local history rebased on top of it and still unpushed.

**Command:** `/github-create`

**Features:**
- Proposes repository names derived from the folder, manifest, and README, filtered against names already taken on the account
- Confirms visibility with public preselected, so an autopilot invocation can't silently publish
- Seeds a LICENSE-only initial commit through the Contents API, avoiding the README that `gh repo create --add-readme` would otherwise force into it
- Detects the states that break the rebase up front — a pre-existing LICENSE, a staged or dirty index, a local branch that doesn't match the remote default
- Subscribes the repo so new issues generate email, and explains the account-level toggle that delivery also depends on
- Leaves committing and pushing to `/commit`, per the rule that creating a repo is neither

---

### GitHub Pages Layout

Arranges a project's README and GitHub Pages docs into a consistent user-first layout — short README that links out, Jekyll site with a user-facing index, one page per user-facing feature, and exactly one developer page.

**Command:** `/github-pages`

**Features:**
- Enforces single-source-of-truth docs on GH Pages so the README stays under a screen
- Separates user-facing pages from the one developer entry-point page (`development.md`)
- Supports flat and monorepo variants with consistent navigation and screenshots
- Aligns new repos to the shape of existing reference implementations

---

### Deploy

Configures and runs the **local** deploy — it makes the current code runnable on this machine and never ships anywhere public. Either installs the built app locally (Tauri, IntelliJ plugin, .NET) or starts the project's local web server. On first use in a project, sets up the `deploy` bash function, creates a local `scripts/deploy.sh` wrapper, and updates `.gitignore`.

Shipping outward is a different verb: a versioned artifact goes through the `release` skill, and a public site through the project's own CI — deliberately not a skill, since publishing from a working tree can leak uncommitted work or the wrong environment's credentials.

**Command:** `/deploy`

**Features:**
- Auto-configures `deploy()` shell function in the platform-appropriate rc file (`~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux)
- Creates `scripts/deploy.sh` wrapper pointing to the global deploy script
- Reads install path from `config/deploy.env` (asks on first run)
- Install targets run the full pipeline: stop app → build → clean install dir → copy → launch → verify
- Local web servers (a `package.json` with a `dev` script, or a plain static `index.html`) relaunch detached on the configured port, then get health-checked
- After first `/deploy`, use `! deploy` for instant deploys without LLM overhead

---

### Cleanup

The destructive counterpart to `deploy`: stops the running app, removes the installed bundle, and wipes its user-data and cache directories — the "before a clean install" reset. Reuses `config/deploy.env`, so the install location is never entered twice.

**Command:** `/cleanup`

**Features:**
- Auto-configures `cleanup()` shell function in the platform-appropriate rc file (`~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux)
- Creates `scripts/cleanup.sh` wrapper pointing to the global cleanup script
- Always asks which of bundle / app data / caches to remove — never assumes
- Backs up paths listed in `BACKUP_FILES=` to `.cleanup-backups/<timestamp>/` before wiping data
- Recognizes Tauri projects; after first `/cleanup`, use `! cleanup` for instant runs

---

### Build

Configures a build shortcut for any project. On first use, sets up the `build` bash function, creates a local `scripts/build.sh` wrapper, and updates `.gitignore`. Then auto-detects the project type and builds. Optionally generates a GitHub Actions CI workflow.

**Command:** `/build`

**Features:**
- Auto-configures `build()` bash function in `~/.bashrc` if missing
- Creates `scripts/build.sh` wrapper pointing to the global build script
- Auto-detects project type: npm, dotnet, or Tauri
- Optionally generates `.github/workflows/build.yml` with CI for push/PR builds (Tauri uses a Windows + macOS matrix)
- After first `/build`, use `! build` for instant builds without LLM overhead

---

### Release

Tags a new version, pushes to trigger CI, monitors the build, and updates the GitHub release with final notes. Supports dotnet and Tauri projects (Tauri builds for Windows + macOS).

**Command:** `/release`

**Features:**
- Validates preconditions: clean tree, on main, in sync with remote
- Auto-detects project type (dotnet or Tauri) and extracts project name
- Recommends version bump based on commit history, asks for confirmation
- Bumps version in all manifest files before tagging (csproj / package.json / tauri.conf.json / Cargo.toml)
- Creates signed annotated tags for GitHub "Verified" badge
- Compiles platform-appropriate release notes (SmartScreen + Gatekeeper first-launch warnings)
- Monitors CI (single-platform for dotnet, matrix for Tauri) until completion
- Replaces draft notes and un-drafts Tauri releases (GitHub auto-renders the assets list)

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

### Reflect

Extracts durable knowledge from the current conversation and persists it to long-term memory before `/clear` or context compaction wipes it. Also runs automatically as an early step of `/commit`, so session learnings are captured alongside the changes they came from.

**Command:** `/reflect`

**Features:**
- Scans the conversation for feedback, project context, user profile, and external reference pointers
- Writes new memories or updates existing ones in global or project-scoped memory dirs
- Re-checks every project-scoped finding against "would this help in another repo tomorrow?", promoting what is actually global and splitting what is only partly so
- Audits already-stored project memories the same way, proposing promotions rather than performing them silently
- Flags candidate skill updates and learnings worth distilling
- Falls back to direct file reads when the gather-context helper is blocked by permissions

---

### Memo

Parks an off-task idea in the project's memo backlog so it isn't lost — without derailing the current task — or lists the backlog to pick something up.

**Command:** `/memo [idea]`

**Features:**
- `/memo <text>` appends a dated `- [ ]` item to `<repo>/.claude/memos.md` (created on first use); `/memo` with no args lists the open backlog and offers to address one
- Memos are deliberately lighter than GitHub issues — half-formed thoughts, committed with the project
- Open items resurface on their own: at session start / `/clear` (via the `memos-surface.py` hook), at task completion, and after a `/commit` push
- Capturing a memo never starts the work — that's the point; addressing one is always an explicit, separate choice

---

### GitHub Status

Cross-project overview of all your GitHub-owned local clones — branch, behind/ahead counts, uncommitted file/line totals, oldest pending work, and a per-repo description synthesized from the pending changes.

**Command:** `/github-status`

**Features:**
- Walks `PROJECTS_ROOT` (configured per-machine on first run), filters to repos owned by your GitHub user
- Fetches every repo's origin in parallel before reading state, so counts reflect the current remote
- Auto-pulls clean repos with inbound commits via `git pull --ff-only`, marks pulled repos with `✓`
- Auto-hides columns that have no meaningful data (no unpushed commits → no UNPUSHED column, all on main → no BRANCH column, etc.)
- Reports uncommitted-file lists and unpushed-commit subjects so Claude can summarize each repo in one line

---

### Update Plannotator Plugin

Force-updates the plannotator plugin by clearing stale caches and reinstalling.

**Command:** `/plannotator-update`

**Features:**
- Removes the marketplace cache (stale git clone that prevents updates)
- Removes the plugin cache
- Guides through reinstallation after restart

---

### Doppler

Manages env-style secrets — API keys, tokens, passwords, connection strings — in [Doppler](https://www.doppler.com/) instead of a plaintext `.env`. Owns every `doppler` command template, so the coordinates and quoting are never reconstructed from memory.

**Command:** `/doppler`

**Features:**
- Reads the real project list up front, so `-p`/`-c` are never guessed (the workplace name is not a project, and the config is `dev`)
- Emits a copy-ready, fenced command for every operation, with `{{placeholder}}` marking only what the user supplies
- Routes any command carrying a plaintext value to a separate terminal — the `!` prefix records the value in the transcript
- Prefers stdin over the command line, which also dodges Git Bash's path mangling on Windows
- Reads values without materializing them, deriving a boolean via `doppler run` instead of printing the secret
- Separate references for project wiring (`doppler.yaml`, directory binding, second-machine onboarding) and for failure modes that succeed silently with a wrong value

---

### Transcrypt

Encrypts designated files with [transcrypt](https://github.com/elasticdog/transcrypt) so they are ciphertext in git history but plaintext in the working tree, or unlocks an already-encrypted repo after a fresh clone. See [Encrypted memory](#encrypted-memory-secretmd) for how this repo uses it.

**Command:** `/transcrypt`

**Features:**
- Uses one shared passphrase from Doppler (`tools/prd` → `TRANSCRYPT_KEY`), never a freshly generated one
- Marks files by the `*.secret.*` naming convention in `.gitattributes`
- Verifies the index holds ciphertext while the working tree stays readable, and stages without committing
- Relies on the global pre-commit guard as a safety net against committing an unencrypted secret

---

### Notion

Works with [Notion](https://www.notion.so/) through whichever of its two APIs can actually do the job — the MCP integration by default, and the internal v3 API (`token_v2` cookie, `/api/v3/`) only for operations MCP cannot express.

**Command:** `/notion`

**Features:**
- Routes each operation to a surface from a decision table up front, so v3 is a deliberate choice rather than the first thing tried after an error
- Names the closed list of v3-only operations — select-option recolor and removal, date formats, reminders, conditional row colours, column widths, grouped views, trashing a row or view, and bulk row edits
- Flags the two operations impossible on both surfaces (column text alignment, enabling Sub-items) so neither gets chased
- Treats MCP as destructive too, calling out the three calls that wipe data despite MCP having no delete verb
- Degrades to the MCP half alone when the `notion_tools` package or the v3 token is missing
- Separate references for the MCP surface, reading data, and v3 transaction recipes

---

## Hooks

### External Hook Paths

When a hook command needs a path outside `~/.claude/` or this repo, reference it via a `CLAUDE_<NAME>` user-scope environment variable instead of hardcoding the absolute path. The hook `command` field is executed via shell, so standard `$VAR` expansion works — the same mechanism that already makes `$HOME/.claude/hooks/...` portable across machines.

**Why:** `claude/settings.json` is symlinked to `~/.claude/settings.json` on every machine that uses this repo. Hardcoded absolute paths pin it to one user's filesystem layout; env vars keep it portable, and a repo move or rename only touches the env var (not every hook entry).

**Caveat:** This works for hook `command` strings only. It does **not** work for MCP server args in `~/.claude.json` — those are passed straight to `child_process.spawn()` with no shell, so paths there must be absolute. That file is not symlinked from this repo.

**Currently used env vars** — set these on a fresh machine before the corresponding hooks will work:

- **`CLAUDE_AI_AGENT_DASHBOARD`** — points to a local clone of the `tauri-dashboard` repo. Used by the `Notification`, `UserPromptSubmit`, `Stop`, `SessionEnd`, and `SessionStart` hooks for live session-status updates.
- **`CLAUDE_AGWINTERM`** — points to the directory holding `agwintermctl.exe`. Used by the `PostToolUse`, `Notification`, `UserPromptSubmit`, and `Stop` hooks to report session status (active / blocked / completed) to the terminal. Each of those commands is additionally guarded on `$AGWINTERM_SESSION_ID`, so it stays inert outside an agwinterm session — leaving this unset costs nothing on a machine that doesn't run one.

**Set on Windows** (User scope, persistent):

```powershell
[Environment]::SetEnvironmentVariable('CLAUDE_AI_AGENT_DASHBOARD', '{{path-to-tauri-dashboard}}', 'User')
[Environment]::SetEnvironmentVariable('CLAUDE_AGWINTERM', '{{path-to-agwinterm}}', 'User')
```

**Set on Linux / macOS** (in your shell profile):

```bash
export CLAUDE_AI_AGENT_DASHBOARD="$HOME/projects/tauri-dashboard"
export CLAUDE_AGWINTERM="$HOME/programs/agwinterm"
```

---

### Memo Backlog

**File:** `claude/hooks/memos-surface.py` (one script, three modes)

Surfaces the open `/memo` backlog (`.claude/memos.md`, resolved at the git root, numbered newest-first) as a **transient status-bar reminder** so a fresh or freshly cleared session shows "what's next" without the user typing anything — then clears it the moment they start working. Three wired entry points:

- **`SessionStart`** (`startup`/`clear`, no arg) — writes a per-session state file with the open memos. Injects **nothing** into chat, so the model never greets with or pushes the backlog — the status bar is the only reminder.
- **`statusLine`** (`statusline` arg, `refreshInterval: 2`) — renders the compact backlog (top 3 + a `+N more` line) from the state file; the interval makes it appear within ~2s while the session is idle.
- **`UserPromptSubmit`** (`on-prompt` arg) — clears the state (the bar reminder is done). If the message is a bare number — or `memo N` / `start N` / `do N` / `pick N` — it injects, bound to that prompt, which memo N maps to, so Claude reliably starts it instead of treating the number as noise.

Stays silent when there's no file or nothing open. Needs no environment variable. See the [Memo](#memo) skill for how items get there and the other two moments they resurface (task completion, `/commit`).

---

### Doppler Guard

**File:** `claude/hooks/doppler-guard.py`

A `PreToolUse` backstop on `Bash`, `Write`, and `Edit`. Hook matchers scope by tool *name* only, so the script self-filters: it exits silently unless the call's command, content, or path mentions Doppler anywhere.

When it matches, it does two things:

- **Injects the conventions** — a condensed reminder citing the [Doppler](#doppler) skill, so a wrong project or config gets corrected at the moment of the command even if the skill was never invoked.
- **Denies a `doppler secrets set`/`delete` that omits `--silent`** — without it Doppler prints the full secrets table, every value included, into the transcript. The deny inspects only the Bash `command`, so prose or docs that merely mention the command still get the reminder rather than a block.

---

### Skill Tracking

**Files:** `claude/hooks/skill-tracked.py` and `claude/scripts/audit-skill-tracking.sh`

A skills directory is ignore-everything-then-allowlist (`claude/skills/*` plus one `!claude/skills/<name>/` line per skill), so a skill whose line was never added is invisible: it never appears in `git status`, nothing signals the omission, and the only copy stays on the machine that made it. Two complementary guards:

- **The hook** — a `PostToolUse` on `Write`, gated by `"if": "Write(//**/SKILL.md)"`. It asks git the moment a `SKILL.md` is written and names the exact file, line and pattern doing the ignoring. The `if` rule is what keeps it affordable: a matcher scopes by tool *name* alone, and on Windows an unfiltered Python hook costs ~200ms of interpreter startup on every edit. That pattern must stay root-anchored (`//`) — an unanchored `**/SKILL.md` matches nothing and silently disables the hook.
- **The audit script** — a sweep over every skill directory regardless of how it arrived (copied, moved, renamed, or unpacked by a plugin), which is the case the hook cannot see. Run by `/commit` before it drafts a plan, and standalone with `bash ~/.claude/scripts/audit-skill-tracking.sh`. It prints one line per skill a wildcard rule is swallowing, and nothing when all are accounted for.

A flagged skill is cleared one of two ways, both durable: add `!claude/skills/<name>/` to `.gitignore` to keep it, or record its directory name in `claude/untracked-skills.local.txt` to keep it machine-local on purpose. That decisions file is itself gitignored and per-machine, since which skills are deliberately unshared differs between machines; a fresh clone has none and decides each skill again there. Symlinked skills and those matched by an exact, wildcard-free path are filtered out without needing an entry.

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

### Encryption guard (pre-commit)

**File:** `git/hooks/pre-commit`

Installed by transcrypt and made portable: in a repo configured for [encrypted memory](#encrypted-memory-secretmd) it blocks a commit if a `*.secret.md` file is staged unencrypted (the last guard against a plaintext leak). Because `core.hooksPath` is global, it guards on the per-repo transcrypt copy and is a **no-op** in any repo that doesn't use transcrypt.

---

## Learnings

The `claude/learnings/` directory collects long-form, domain-specific reference notes — non-obvious behaviors learned through trial and error (framework quirks, API limitations, platform gotchas), each a topic-named markdown file with no frontmatter or index. They're available globally through the `~/.claude/learnings/` symlink, and the `/reflect` skill adds to them as new knowledge surfaces.

The filenames are the index — browse `claude/learnings/` to see what's covered rather than maintaining a manifest here. To pull a topic into a project, point that project's `CLAUDE.md` at the file:

```
Read `~/.claude/learnings/chrome-extension.md` for domain-specific patterns.
```

---

## Global Installation

Global files live in `claude/` (symlinked to `~/.claude/`) and `git/` (hooks, gitignore, gitattributes — each symlinked to `~/`). Project-local config stays in `.claude/`.

> If any of these already exist in `~/.claude/` or `~/.git-hooks/`, move them into the repo first (or remove them) before creating the symlink.

macOS / Linux users skip this section — see [Linux / macOS](#linux--macos) below.

### Windows

Run from the project root *as Administrator*:

```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\CLAUDE.md" -Target "$PWD\claude\CLAUDE.md"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills" -Target "$PWD\claude\skills"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\hooks" -Target "$PWD\claude\hooks"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\settings.json" -Target "$PWD\claude\settings.json"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\learnings" -Target "$PWD\claude\learnings"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\memory" -Target "$PWD\claude\memory"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\scripts" -Target "$PWD\claude\scripts"
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
mkdir -p ~/.claude
ln -s "$(pwd)/claude/CLAUDE.md" ~/.claude/CLAUDE.md
ln -s "$(pwd)/claude/skills" ~/.claude/skills
ln -s "$(pwd)/claude/hooks" ~/.claude/hooks
ln -s "$(pwd)/claude/settings.json" ~/.claude/settings.json
ln -s "$(pwd)/claude/learnings" ~/.claude/learnings
ln -s "$(pwd)/claude/memory" ~/.claude/memory
ln -s "$(pwd)/claude/scripts" ~/.claude/scripts
ln -s "$(pwd)/git/hooks" ~/.git-hooks
ln -s "$(pwd)/git/gitignore" ~/.gitignore
ln -s "$(pwd)/git/gitattributes" ~/.gitattributes
git config --global core.hooksPath ~/.git-hooks
git config --global core.excludesFile "~/.gitignore"
git config --global core.attributesFile "~/.gitattributes"
```

## Memory

Two complementary stores hold accumulated cross-session knowledge, both surfaced
to the harness for auto-recall:

- **Global memory** (`claude/memory/`, deployed to `~/.claude/memory/` via
  symlink) — cross-project preferences, feedback, and references meant to apply
  everywhere.
- **Project memory** — facts specific to a single repo. Claude Code writes these
  to a machine-local cache (`~/.claude/projects/<path-encoded>/memory/`) that is
  **not** version controlled, so the knowledge is invisible from other machines
  and lost if the cache is cleared.

### Versioning project memory

The `claude/scripts/link-project-memory.sh` script redirects a project's memory
cache — via a symlink, or a directory junction on Windows — into a committed
`.claude/memory/` directory inside that repo. The harness keeps reading and
writing the same path, so auto-recall is unaffected; the files just live in the
repo now and travel with `git clone`.

Run once per project, per machine — from inside the repo:

```bash
bash ~/.claude/scripts/link-project-memory.sh
```

It migrates any files already in the cache, wires up the link, and leaves
`.claude/memory/` staged for you to commit. On a fresh machine, clone the repo
and re-run the command to re-establish the (machine-local) link.

> In this dotfiles repo the two stores sit side by side: `claude/memory/` is the
> **global** payload deployed to `~/.claude/memory`; the repo-root
> `.claude/memory/` is this repo's own **project-specific** memory.

### Encrypted memory (`*.secret.md`)

Memory files holding sensitive coordinates (not secret *values* — those stay in
Doppler) are committed **encrypted**, so this public repo never exposes them.
They are transparently decrypted in a working tree that holds the key, and read
as opaque blobs to anyone without it.

- **Mechanism:** [transcrypt](https://github.com/elasticdog/transcrypt) (vendored
  at `claude/scripts/transcrypt`) wires Git clean/smudge filters. `.gitattributes`
  marks `claude/memory/*.secret.md filter=crypt`, so those files are ciphertext in
  every commit and plaintext only locally.
- **Key:** a symmetric passphrase kept in Doppler (a `TRANSCRYPT_KEY` secret) — not
  in this repo. The committed index entry for an encrypted memo is deliberately
  generic, so even the description gives nothing away.

**Unlock on a new machine** — after cloning and fetching the key, run from the repo
root (substitute your Doppler project/config):

```bash
bash claude/scripts/transcrypt --yes -c aes-256-cbc \
  -p "$(doppler secrets get TRANSCRYPT_KEY --project <project> --config <config> --plain)"
```

The portable `pre-commit` (installed globally via `core.hooksPath`) already chains
`transcrypt pre_commit`, so init skips writing its own redundant helper hook into
the shared, committed `git/hooks/` — no leftover, no manual cleanup. (This is a
local patch to the vendored `transcrypt`; re-apply it if you re-vendor upstream.)

Until then, `*.secret.md` files read as encrypted blobs. Add more by naming them
`*.secret.md`; the attribute pattern encrypts them automatically.

## License

[GPL-3.0](LICENSE)
