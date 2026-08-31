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
- Reconciles documentation screenshots against the docs that cite them, and proves a shot stale by grepping the text visible in it against source
- Places a replacement screenshot you shot yourself, then sweeps its caption, alt text and surrounding prose — it never captures one itself
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

Shipping outward is a different verb: a versioned artifact goes through the `release` skill, and a running site through the [Publish](#publish) skill or the project's own CI. Where CI already publishes on push, the push *is* the ship and the project gets no local publish script at all.

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

### Publish

Ships a project outward to where its users are — the counterpart to `deploy`, which only makes the code runnable on this machine. Writes `config/publish.env` and a per-machine `scripts/publish.sh` wrapper, then publishes and verifies the live result. Supports Dockerised apps on a box reached over SSH; a Chrome extension goes through `/publish-chrome-extension` and a versioned artifact through `/release`.

**Command:** `/publish`

**Features:**
- Declines to write a wrapper at all for a project that publishes from CI — there the push *is* the ship, and a local path would upload a working tree stamped with local `HEAD`
- Ships only committed, pushed code: a dirty tree or a `HEAD` that isn't `origin/<branch>` stops it before the box is touched
- Reconciles the box's checkout with a hard reset to the remote, cloning it on the first publish so step one behaves like every later one
- Renders the production env file from Doppler straight onto the box over SSH, so no value reaches this terminal, the transcript, or shell history
- Detaches the compose build and polls its log, since a build routinely outlives the tool timeout that invoked the script
- Recreates the proxy only when its config actually changed — a bind-mounted config keeps its old inode, so a reload reports "config is unchanged" and the new vhost never gets a certificate. Handles both shapes: a co-tenant vhost gets installed into somebody else's proxy (validated before it goes live, restored on failure), while a repo that owns its proxy already has the file in the checkout and only needs the "did it change" answer
- Proves success by observing the target: a real user-facing page must return 200 *and* the container's restart count must not climb, because a health probe passes while every database-backed page 502s and a crash-looping container answers between restarts
- Asserts *identity*, not just liveness, where a box hosts several projects — a 200 proves something answered, never that it was yours, and a name collision routes a hostname at a neighbour's app just as healthily. The optional `IDENTITY_CHECK` runs twice: once before anything is built, to prove the check itself can run, and once after the deploy to assert the answer. "Serving the wrong app" and "the check could not run" are reported as different things, because only one of them justifies a rollback

---

### Backup

Gives a project on the shared VPS a nightly off-box backup, or works on one it already has: provisions its Backblaze bucket and bucket-scoped key, writes the job and its systemd units, renders the credentials, and proves the restore by running it. Encodes one shape across every co-tenant — restic to B2, one bucket per project, credentials in `/etc/<tenant>/backup.env`, a staggered timer, a drill.

**Command:** `/backup`

**Features:**
- Provisions Backblaze end to end over the native API — bucket, lifecycle rule and a key scoped to that bucket alone — with an explicit boundary between what it may create unasked and what needs the user (deleting anything, or touching another project's)
- Sets the bucket lifecycle rule **at creation**, because the S3-compatible backend only *hides* what it deletes: without it `forget --prune` reclaims nothing while every nightly run exits 0 and the bill grows with no signal anywhere
- Insists on a fixed staging path — `restic forget` groups snapshots by host *and* paths, so a per-run tmpdir silently turns the whole retention policy into a no-op
- Renders credentials from a workstation over an ssh pipe with `umask 077`, since the box deliberately has no Doppler and `>` then `chmod` leaves the passphrase world-readable for a window
- Keeps backup credentials out of the publish-time required-secrets list, so a durability credential can never refuse a change to what the box is serving
- Catches the failures that report success: restic's exit 3 writes a *partial* snapshot, `Type=oneshot` disables systemd's start timeout by default, and an `ExecStart` under the repo directory name rather than the deploy path dies 203/EXEC on every fire
- Proves the restore by counting what came back — and, where the box still serves, by matching a restored artefact's digest against the live one
- A per-engine table for taking a consistent copy (SQLite online backup, `pg_dump` with credentials read inside the container, `mongodump` from the image that matches the server), plus `references/tenants.md` recording what each neighbour already does and which nightly slots are free

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
- Offers the clipboard route first for a value only the user holds — it pipes clipboard → Doppler behind a prefix guard, so nothing occupies a command line — and the copy-ready command as the alternative, routed to a separate terminal because the `!` prefix records the value in the transcript
- Hands a stored value back to the clipboard without printing it, reporting a label, length and digest, and leaves a `cb` script that re-fetches it hours later when the clipboard has moved on
- Prefers stdin over the command line, which also dodges Git Bash's path mangling on Windows
- Reads values without materializing them, deriving a boolean via `doppler run` instead of printing the secret
- Separate references for project wiring (`doppler.yaml`, directory binding, second-machine onboarding) and for failure modes that succeed silently with a wrong value

---

### Hooks

Authoring guidance for Claude Code hooks — picking the event and matcher, keeping the per-invocation cost down, and the never-raise contract a hook script owes the harness. Invoked when writing a hook, editing a `hooks` entry in `settings.json`, or diagnosing one that never fires or fires too often.

**Command:** `/hooks`

**Features:**
- A narrowing ladder that puts the zero-startup `if` rule first, the matcher second, and an in-script early return last
- Measured cost tables for every implementation choice, so an interpreter is picked on evidence rather than intuition (`references/performance.md`)
- Event catalog with cadence, matcher targets, timeouts, exit-code semantics and the stdin payload shape (`references/events-and-payloads.md`)
- A frequency table pairing each event with the cost budget it can bear, from per-streaming-chunk down to once per session
- The never-raise contract, plus the rule that hook errors are silent — so anything consequential logs to disk
- A findings log that accumulates each surprise (a cost, a silent failure, a semantic) instead of leaving it in a session transcript

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
- **`CLAUDE_LANDLORD`** — points to a local clone of the `landlord` repo, which owns the shared-host tenancy rules [Ingress Lint](#ingress-lint) delegates to. Optional, and only consulted for a repo that publishes a vhost: the lookup falls back to a `landlord` sibling of the repo being linted, which is the layout both machines already have. Unlike the two above, leaving it unset is not free — the tenancy half then reports **NOT CHECKED** rather than passing quietly.

The macOS counterpart needs no env var. The same four events also report status to **agterm** via `$HOME/.config/agterm/agent-status/agterm-agent-status.sh` — the app installs that script at a fixed `$HOME`-relative path, so there is nothing to configure. Those commands are guarded on `$AGTERM_SESSION_ID` and stay inert outside an agterm session, which is what lets one committed `settings.json` carry both machines' status hooks.

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
- **Denies a `doppler secrets set`/`delete` that omits `--silent`** — without it Doppler prints the full secrets table, every value included, into the transcript. The deny inspects only the Bash `command`, so prose or docs that merely mention the command still get the reminder rather than a block, and a bare `-h`/`--help` is exempt since usage output carries no values.

---

### Skill Tracking

**Files:** `claude/hooks/skill-tracked.py` and `claude/scripts/audit-skill-tracking.sh`

A skills directory is ignore-everything-then-allowlist (`claude/skills/*` plus one `!claude/skills/<name>/` line per skill), so a skill whose line was never added is invisible: it never appears in `git status`, nothing signals the omission, and the only copy stays on the machine that made it. Two complementary guards:

- **The hook** — a `PostToolUse` on `Write`, gated by `"if": "Write(//**/SKILL.md)"`. It asks git the moment a `SKILL.md` is written and names the exact file, line and pattern doing the ignoring. The `if` rule is what keeps it affordable: a matcher scopes by tool *name* alone, and on Windows an unfiltered Python hook costs ~200ms of interpreter startup on every edit. That pattern must stay root-anchored (`//`) — an unanchored `**/SKILL.md` matches nothing and silently disables the hook.
- **The audit script** — a sweep over every skill directory regardless of how it arrived (copied, moved, renamed, or unpacked by a plugin), which is the case the hook cannot see. Run by `/commit` before it drafts a plan, and standalone with `bash ~/.claude/scripts/audit-skill-tracking.sh`. It prints one line per skill a wildcard rule is swallowing, and nothing when all are accounted for.

A flagged skill is cleared one of two ways, both durable: add `!claude/skills/<name>/` to `.gitignore` to keep it, or record its directory name in `claude/untracked-skills.local.txt` to keep it machine-local on purpose. That decisions file is itself gitignored and per-machine, since which skills are deliberately unshared differs between machines; a fresh clone has none and decides each skill again there. Symlinked skills and those matched by an exact, wildcard-free path are filtered out without needing an entry.

---

### Ingress Lint

**Files:** `claude/hooks/ingress-lint.py` and `claude/scripts/ingress-lint.py`

Where several projects share one box behind one reverse proxy, a generic name is a claim on a namespace someone else uses. Docker Compose publishes a *service's* name as a DNS alias on every network it joins, so two projects that both call a service `app` both answer to `app` on the shared bridge and the proxy resolves whichever the daemon hands back; a vhost dropped into a common `conf.d` is separated from its neighbours only by its basename. The failure is silent and stays green — HTTP 200, healthy containers, `caddy validate` clean — which is why it is caught at the moment the name is written rather than afterwards.

- **The rules** live in `claude/scripts/ingress-lint.py`, a stdlib-only checker (Claude Code hooks run `python -S`, so PyYAML is not importable and the small YAML subset is read by hand). Run it over files or repo roots: `python ~/.claude/scripts/ingress-lint.py [path ...]` — exit 0 clean, 1 violations, 2 nothing to check. This is also what a repo's `.claude/commit-checks.sh` should call.
- **The hook** is a `PostToolUse` adapter that feeds the checker one just-written path. It loads the rules by path instead of copying them, so there is exactly one copy. It is **not registered in `settings.json` by default** — its docstring carries the entry to add, along with the three things that fail silently if you get them wrong (the mandatory `//` root anchor, `if` belonging *inside* the hook object, and `"async": false` being set explicitly because a backgrounded hook cannot deliver `additionalContext` at all).
- **The tenancy rules are not implemented here.** What a vhost may claim inside a shared `conf.d` belongs to the `landlord` repo, whose on-box gate enforces it; this checker loads `landlord/bin/vhost-lint.py` by path and applies it to the single file `VHOST_SRC` in `config/publish.env` names, so the two cannot disagree. A Caddy file the repo has *answered for* — it names a different one, or names none via an empty `VHOST_SRC=` — is skipped in silence, since a keyless global-options block, a snippet definition and a port-only address are all legitimate when you own the proxy. Every other way the rules fail to run is **NOT CHECKED**, never a bare "clean": no landlord checkout, no declaration at all, or a declaration naming a file that is not there. That third state is what the checker is for — an undeclared live tenant printed `clean (2 file(s) checked)` over a vhost no tenancy rule had touched, character-for-character what a real pass prints. See [`CLAUDE_LANDLORD`](#external-hook-paths).

**Tests:** `python3 claude/tests/ingress-lint.py` — exit 0 all cases behave, 1 otherwise. It pins the compose rules, the delegation, the silent skips and all three NOT CHECKED paths, and it stubs landlord so it runs on a machine with no checkout.

**Related:** `claude/scripts/identity-check.py` is the other half — the same problem checked from outside instead of prevented at the source. Given a per-host manifest it asserts, for every hostname on a box, that the host's own marker is present *and* that every other tenant's marker is absent; the second half is what turns "up" into "up and correct". The `/publish` skill wires it in via `IDENTITY_CHECK`. The manifest is per-host data and is passed in rather than kept here — see the note in [Global Installation](#global-installation).

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

### Pre-commit guard

**File:** `git/hooks/pre-commit`

Two independent checks, ordered by cost. Because `core.hooksPath` is global this hook runs for every repo on the machine, so each check has to be inert where it doesn't apply — one that fires wrongly is one that gets disabled, and disabling it removes the case where it did apply.

- **`config/publish.env` must be marked for encryption before it can be committed.** That file names the box, its paths, the container to watch and the vhost to install. No credential — which is exactly what made it easy to commit by accident. It is versioned rather than ignored, because per-machine copies drifted: one tenant was left pointing at a path another had deleted. The check is *structural* — does the path resolve to `filter=crypt` — so it can't be fooled by a file that merely looks encrypted, and it refuses with instructions rather than leaking. This half is **not** a no-op in a repo without transcrypt: staging that path anywhere tells you to set it up. Only that one path is enforced; `.env` as a class is the wrong unit, since a plaintext `host.env` and a secret-carrying rendered `.env` share a suffix and need opposite handling.
- **A file marked `filter=crypt` must actually be ciphertext.** Transcrypt's own check, made portable: in a repo configured for [encrypted memory](#encrypted-memory-secretmd) it blocks a commit if a `*.secret.md` is staged without the encrypted "Salted" magic — the last guard against a plaintext leak. This half guards on the per-repo transcrypt copy and **is** a no-op where transcrypt isn't configured.

---

## Learnings

The `claude/learnings/` directory collects long-form, domain-specific reference notes — non-obvious behaviors learned through trial and error (framework quirks, API limitations, platform gotchas), each a topic-named markdown file with no frontmatter or index. They're available globally through the `~/.claude/learnings/` symlink, and the `/reflect` skill adds to them as new knowledge surfaces.

The filenames are the index — browse `claude/learnings/` to see what's covered rather than maintaining a manifest here. To pull a topic into a project, point that project's `CLAUDE.md` at the file:

```
Read `~/.claude/learnings/chrome-extension.md` for domain-specific patterns.
```

---

## Global Installation

Global files live in `claude/` (symlinked to `~/.claude/`) and `git/` (hooks, gitignore, gitattributes — each symlinked to `~/`). Project-local config stays in `.claude/`. The one directory under `claude/` that is deliberately not symlinked is `claude/tests/`: those run from a checkout of this repo, not from `~/.claude/`.

> If any of these already exist in `~/.claude/` or `~/.git-hooks/`, move them into the repo first (or remove them) before creating the symlink.

> **There is deliberately no `claude/hosts/` here, and `.gitignore` still blocks the path.** A per-host identity
> manifest inventories a box's hostnames and the exact string each site emits to prove the right application is
> answering — none of it a credential, which is precisely why it is easy to publish by accident, and **this repo
> is public**. One briefly lived here and drifted from its original within hours. Per-host data now lives in the
> private repo that owns the host, and each project's `IDENTITY_CHECK` fetches it at publish time rather than
> keeping a copy. The ignore rule outlives the directory on purpose: it is what stops the path being recreated by
> someone repeating the reasoning that put it here, which looked entirely sound at the time.

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

### Python interpreter

Every Python hook and the statusline in `claude/settings.json` invoke the interpreter as `python`, never `python3`. That is deliberate and measured: on both platforms the `python3` name resolves to an indirection rather than the real binary — a bash shim on Windows and an `xcode-select` dispatcher on macOS — and each costs a spawn on every hook. Nothing else on `PATH` may shadow it, so a machine that lacks a real `python` runs no hooks at all. Figures live in `claude/skills/hooks/references/performance.md`.

Windows satisfies this out of the box. macOS does not — Apple ships no `python`, and the Command Line Tools `python3` is stuck on 3.9, which is old enough that ordinary annotations like `str | None` fail at import. Install a current Python and expose it under the bare name:

```bash
brew install python
mkdir -p ~/.local/bin
ln -s /opt/homebrew/bin/python3 ~/.local/bin/python
```

Point the symlink at `/opt/homebrew/bin/python3`, not at the versioned `libexec/bin/python`, so it follows future upgrades. Make sure `~/.local/bin` is on `PATH`, then confirm with `python -V`.

Because the symlink lives outside the repo, it is the one setup step no `git clone` restores. A machine missing it fails silently — hooks simply never fire.

Every invocation also passes `-S`, which skips `site` — the single largest slice of interpreter startup. **The cost is that `site-packages` is off `sys.path`, so every hook must stay stdlib-only.** All of them currently are. A hook needing a third-party package must drop `-S` on its own command line rather than for all of them.

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
