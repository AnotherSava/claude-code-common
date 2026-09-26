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
- Clears the index before staging each group, so work staged before the run cannot ride into the first commit
- Delegates to `/reflect`, `/clean-code`, and `/docs-relevance` before planning commits
- Drafts commit messages in imperative mood with type prefixes
- Presents a full plan for approval before executing any commits
- GPG-signs all commits, never adds AI attribution
- Asks the live session that owns a peer repository to commit work this session left there, scoped to repos it actually wrote to

---

### Reset

Unwinds selected unpushed commits back into the working tree so they can be re-committed. The counterpart to `/commit`, which never amends: an unpushed commit is corrected by putting it back and committing again.

**Command:** `/reset`

**Features:**
- Lists every unpushed commit with hash, timestamp and subject, newest first, offering each as "this commit only" or "this plus everything above it"
- Always offers "don't reset" as option 0, so the list can be inspected without committing to an action
- Defaults to the most recent commit alone — except where the newest commits form a contiguous run of `fix: address code review findings`, where the default unwinds the whole run
- Resets to the parent of the chosen commit, so nothing is discarded; the changes land back in the working tree for `/commit` to regroup
- Will not commit, push, or switch branches — unwinding is the whole job

---

### Pull

Brings the branch up to date with its upstream when the working tree is dirty — the normal case in repos worked from two machines and several concurrent sessions. The counterpart to `/commit`, which stops at a remote that has moved ahead.

**Command:** `/pull`

**Features:**
- Fetches and classifies the divergence first, stopping on an untracked branch, a failed fetch, or a branch already current
- Intersects the locally-changed files with the incoming ones, and stashes nothing at all when they are disjoint — git's refusal to fast-forward is per-path
- Scopes the stash to exactly the overlapping paths when they do intersect, so files another session is mid-edit in never leave the disk
- Restores with `git stash pop --index`, preserving the staged/unstaged split that a plain pop silently flattens
- Verifies against the stash commit as a baseline, then checks the two failure modes that produce no conflict at all: one document asserting the same thing twice, and an incoming file duplicating one already in the tree
- Reads its procedure from `@{upstream}` when the repo being pulled is this one, since a behind checkout's documentation is behind by the same commits
- Proposes a rebase on a diverged branch rather than running one, and will not commit or push
- Runs only when you type it — `disable-model-invocation: true` stops Claude starting it, even when asked directly

---

### Docs Relevance

Scans project documentation for stale references and fixes them.

**Command:** `/docs-relevance`

**Features:**
- Reads the project's own `CLAUDE.md` first and lets it override any step — a repo that rules out screenshots gets no staleness pass, no manifest and no offer — and says in the report which of its rules applied
- Checks README, `docs/pages/`, CLAUDE.md, and source comments against current code
- Fixes stale paths, API references, and behavior descriptions
- Keeps curated feature listings (features page, docs index, README) in sync with the diff
- Reconciles documentation screenshots against the docs that cite them, and proves a shot stale by grepping the text visible in it against source
- Records each shot in a `docs/screenshots/screenshots.json` manifest — what the frame shows, how to reproduce it, and whether replacement is `auto`, `confirm` or `never`
- Replaces one only as its policy allows, capturing through a committed `docs/screenshots/capture/<id>.sh` (or `<id>.ps1` on Windows, which calls the skill's shared `window-shot.ps1` and `windows-capture.ps1`) so the second capture is free and the diff shows how the image was made; anything undecided stops to ask, and a shot you supply yourself is filed the same way
- Stages the content a frame needs by replaying a committed fixture through an input the product already takes, never a demo mode or seed data inside it
- Gives a screenshot the edge its own capture lacks: a hairline traced from the image's alpha (`hairline.py`), or for a Windows capture the frame DWM draws, rebuilt from its measured model (`winframe.py`)
- Writes a contact sheet — one self-contained HTML page carrying every screenshot, replacements as before/after pairs, each frame numbered and one click apart — and hands it over as a `file:///` link for the user to open; under `confirm` the sheet *is* the proposal, written before anything is captured
- Names the shots that do not exist: sweeps pages for sections doing a picture's work in prose, proposes the two or three strongest, and captures none of them without an explicit yes
- Regenerates dimensioned-draft drawings when the model they document changed
- Suggests new documentation files or reorganization when beneficial

---

### Docs Style

Governs how a document is written, where [Docs Relevance](#docs-relevance) governs whether it is still true. Invoked before drafting or rewriting long-form prose — a docs page, a README section, a learnings file, a convention version README.

**Command:** `/docs-style`

**Features:**
- Opens on why the thing exists rather than on what it is, since a definition-first first paragraph would survive unchanged in a glossary
- Cuts the sentences that defend the text around them, the commonest source of removable words in a draft that already reads well
- Names the actor instead of leaving a procedure in the passive, and refuses a header a reader cannot predict the content of
- Carries the before/after pairs in `references/style-guide.md`, every one of them text that shipped and was then replaced
- Names what it will not do: never cut a warning, prerequisite or edge case to make a page shorter, and never rewrite a quote
- Resolves the reader from the file's path where that settles it, and declines a skill's own files outright — a SKILL.md is a procedure Claude executes, so trimming it to read better removes what a run needs

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
- Pins the remote theme to a release tag, so an upstream commit cannot change the site with nothing changing in the repo
- Enables Pages once `docs/` is pushed and points the repo's description and homepage at it

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
- An optional `DEV_PRESTART_CMD` runs the project's own script — seeding the local database from production, fetching a fixture — in the gap between stopping the old server and starting the new one
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
- Recommends version bump from commit history, checked against what the release actually ships, then asks for confirmation
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
- Ships only committed, pushed code: a dirty tree or a `HEAD` that isn't `origin/<branch>` stops it before the box is touched. A project with no users can waive that with `ALLOW_DIRTY_PUBLISH=1` in its `config/publish.env` and ship the working tree instead — the box then runs code no commit describes, which is why the key is per-project and never inherited by a co-tenant
- Reconciles the box's checkout with a hard reset to the remote, cloning it on the first publish so step one behaves like every later one
- Renders the production env file from Doppler straight onto the box over SSH, so no value reaches this terminal, the transcript, or shell history
- Detaches the compose build and polls its log, since a build routinely outlives the tool timeout that invoked the script
- Recreates the proxy only when its config actually changed — a bind-mounted config keeps its old inode, so a reload reports "config is unchanged" and the new vhost never gets a certificate. Handles both shapes: a co-tenant vhost gets installed into somebody else's proxy (validated before it goes live, restored on failure), while a repo that owns its proxy already has the file in the checkout and only needs the "did it change" answer
- Proves success by observing the target: a real user-facing page must return 200 *and* the container's restart count must not climb, because a health probe passes while every database-backed page 502s and a crash-looping container answers between restarts
- Asserts *identity*, not just liveness, where a box hosts several projects — a 200 proves something answered, never that it was yours, and a name collision routes a hostname at a neighbour's app just as healthily. The optional `IDENTITY_CHECK` runs twice: once before anything is built, to prove the check itself can run, and once after the deploy to assert the answer. "Serving the wrong app" and "the check could not run" are reported as different things, because only one of them justifies a rollback

---

### Publish Chrome Extension

Republishes a new version of an existing Chrome extension to the Chrome Web Store: takes the zip from a GitHub release, checks the store listing still covers what the package now does, uploads over the Web Store API and submits for review. Usually run straight after `/release`.

**Command:** `/publish-chrome-extension`

**Features:**
- Verifies the version inside the release zip's `manifest.json` against the tag before uploading, so an asset that doesn't contain what its tag claims stops the run
- Keeps `cws-publish.json` beside `manifest.json` as the tracked mirror of the dashboard-only listing data the API can neither read nor write — one per extension folder, so a repo can host several
- Diffs the package's `permissions` and `host_permissions` against the recorded justifications, drafting the missing ones and flagging orphans: the dashboard blocks submission on exactly this, and the API cannot fix it
- Re-checks the single-purpose statement and store description against the user-visible changes since the last published version, rather than assuming they still hold
- Walks the one-time Google Cloud OAuth setup on first run, and re-runs only the token steps when a refresh token expires
- Will not create a listing or edit listing content — that stays in the dashboard

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
- A per-engine table for taking a consistent copy (SQLite online backup, `pg_dump` with credentials read inside the container, `mongodump` from the image that matches the server), and the authorization boundary in `references/b2-provisioning.md` for what may be created without asking

---

### Heartbeat

Gives a scheduled job a dead-man's switch, so its silence is noticed. A scheduled job cannot report its own absence: every other check runs *inside* the thing being checked, so when the thing stops, so do they, and a stopped check is indistinguishable from a passing one. Derives the grace from the job's own cadence, creates the check over the healthchecks.io API, puts the ping URL where the job's other credentials live, and proves it by watching the alarm fire.

**Command:** `/heartbeat`

**Features:**
- Separates the two questions a job answers — *did it pass* (the verdict: mail, report, log) from *did it run at all* (the heartbeat) — so a failing job never looks dead and a dead job never looks merely failing; the heartbeat fires on a failed run too
- Treats the ping URL as a credential: `scripts/hc.py` never prints one, `store-url` pipes it straight into the job's own Doppler config, and `list` strips the uuid as well, since the ping URL is that uuid in longer form
- Defaults a new check to all integrations, because the API's own default is *none* — a check with nowhere to send an alert goes red on the dashboard and tells nobody, the exact silent failure the skill exists to prevent
- Refuses to send a schedule and a period together: healthchecks.io keeps the schedule and silently discards the period, so a caller passing both would get a cadence it never asked for and no error saying so
- Audits every check the key can see and names the inert ones — never pinged, so it sits in `new` forever and can never alert; or no integrations, so it can go down and nobody is told
- The one check permitted to degrade quietly: an unset or unreachable ping URL is a note, never a failure, since a heartbeat able to fail the job would turn a monitoring aid into an outage
- Keeps the inventory of what is and is not monitored out of this public repo — check names and unwatched machines are a map of where nobody is looking, so the method lives here and the map lives in the private repo that owns the thing being watched
- Grace derivation in `references/grace-derivation.md`; the healthchecks.io API key is per-project, so one key audits one project

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
- Writes evidence taken from the user's own data (sites in their history, fares, account figures) in generalized form, since learnings and memory are committed to a public repo
- Falls back to direct file reads when the gather-context helper is blocked by permissions

---

### Memo

Parks an off-task idea in the project's memo backlog so it isn't lost — without derailing the current task — or lists the backlog to pick something up.

**Command:** `/memo [idea]`

**Features:**
- `/memo <text>` writes one markdown file to `<repo>/.claude/memos/` (created on first use); `/memo` with no args lists the open backlog and offers to address one
- One memo is one file — a frontmatter block carrying `created:` and optionally `platform:`, an `# H1` title, and a body as long as the idea needs; open versus addressed is `memos/` versus `memos/done/`, so nothing parses a status marker
- An addressed memo is named `<close-date>-<slug>.md` and is kept for good — there is no command that clears `done/`. That directory is the one place the sort key sits in the filename rather than in frontmatter, because nothing lists it: `list` and `show` both resolve against the open backlog, leaving `ls` and `git status` as its only readers, and a name is all either sorts by
- Read one in full with `show`, close it with `done`, undo that with `reopen`, and delete a redundant duplicate outright with `drop` — a listing shows titles only, with a trailing `…` marking a memo that has more to read
- `--platform macos|windows` binds the minority of memos one box cannot act on — a codepage, a PowerShell API, a toolchain on one side only. Absent means either machine, and an unbound memo writes the bytes it always did. It **marks and never filters**: the memo keeps its place, its number and its close command, so a tag can never desync a listing from the number used to act on it. Picking a tagged memo from the status bar tells the session to do the portable part here and route the rest to the live session on that box
- The three that change the backlog — `done`, `reopen` and `drop` — each take several identifiers at once and resolve them all before acting, because a number indexes the live listing and closing one renumbers the rest
- Memos are deliberately lighter than GitHub issues — half-formed thoughts, committed with the project
- Open items resurface on their own: at session start / `/clear` (via the `memos-surface.py` hook), at task completion, and after a `/commit` push
- Capturing a memo never starts the work — that's the point; addressing one is always an explicit, separate choice
- Every command refuses in a repo that has not adopted this layout, naming the version and pointing at [`/adopt`](#adopt) — otherwise a listing reports an empty backlog while the old file holds items, and an `add` writes a memo beside it and leaves the migration half done. It asks the adopted version rather than looking for the old file, so the next format change needs no edit here; a dotfiles checkout it cannot read at all degrades to a note on stderr rather than blocking

**Tests:** `python claude/tests/memos.py` — exit 0 all cases behave, 1 otherwise. It pins the numbering (one snapshot per command, and that two commands cannot share one), the case folding that keeps a generated filename off an existing memo on a case-insensitive filesystem, the undo hint naming where a memo went rather than where it came from, the close date riding in the name and nowhere else — uniqueness tested on the prefixed form, the `-2` suffix kept behind the date, and a reopen dropping the prefix by deriving from the title rather than by recognising a date — and the platform binding — that it marks without filtering, that an unbound memo still writes the bytes it did before the field existed, and that a value reaching the file by hand renders rather than reading as "either machine". Its platform cases are written against `memos.THIS_PLATFORM`, so the suite asserts the same thing on the mac and on the Windows box.

---

### Wrap Up

Closes out a section of work. Before anything is committed it re-reads the current session's transcript from disk and surfaces the business left unfinished: questions Claude asked that were never answered, concerns raised and passed over, ideas that should have been memo'd, and follow-ups promised but never delivered. Each finding is settled individually, then `/commit` runs and the section ends at a `/clear`.

**Command:** `/wrap-up`

**Features:**
- Reads the transcript on disk rather than the live context, so a session that has been compacted still gets a complete review
- Keeps every word both sides said and discards tool traffic; prose is a small fraction of a transcript (82 KB of a 3.5 MB session, measured), so no keyword heuristic has to decide which findings are allowed to surface
- Restores answers given through question prompts, which carry direction that often appears nowhere else in the session
- Checks each candidate against the current working tree before presenting it, dropping whatever is already settled: a later message, an existing memo, an earlier `/wrap-up`, or a step of the commit flow that owns it
- Gates the commit: every finding is answered now, memo'd for later, or dropped, and nothing is committed until the list is disposed of
- Routes work only the other machine can do to the live session there rather than parking it as a memo, and holds that message until the push when the peer has to pull this session's work before it can act
- Hands the rest to `/commit` (remote sync, reflect, clean-code, documentation, confidentiality scan, push), then recommends the `/clear` that scopes the next wrap-up to exactly one section

---

### GitHub Status

Cross-machine overview of all your GitHub-owned local clones — branch, behind/ahead counts, uncommitted file/line totals, oldest pending work, open issues, how far behind [`/adopt`](#adopt) each clone is, and a description synthesized from the pending changes for each machine that has any. Prints a box table and writes a self-contained HTML report.

**Command:** `/github-status`

**Features:**
- Walks `PROJECTS_ROOT` (configured per-machine on first run), filters to repos owned by your GitHub user
- **Covers both machines in one run** — the peer is scanned by piping this same script into its interpreter over SSH, so nothing is installed on the far side and the two ends cannot run different versions of the scan
- Merges the two on each repo's `OWNER/REPO` origin slug, the only identity that survives a different clone path per machine; in the terminal table a machine gets a line only where it has a clone, so which machines a block lists is itself where the repo exists, while the report shows only outstanding work and leaves clean and absent alike as an empty column
- Fetches every repo's origin in parallel on both machines before reading state, so counts reflect the current remote
- Auto-pulls clean repos with inbound commits via `git pull --ff-only` on both machines, marks pulled repos with `✓`
- **Reports each clone's convention gap** in a `CONV` column and in the report card, so a repo behind on [`/adopt`](#adopt) appears even with a clean tree — it imports the conventions engine rather than re-reading `.claude/conventions`, since two readers of one format drift the day either changes shape. Per machine, not per repo: the two dotfiles checkouts are routinely at different commits, so each machine's summary line names the version set its column was measured against
- Says when it could not measure — a machine whose dotfiles checkout predates `/adopt`, a record that will not parse, one naming a version newer than the version set — rather than leaving an empty column that reads as a fleet with nothing to adopt
- Auto-hides columns nothing fills — MACHINE disappears on a single-machine run, BRANCH when every clone is on main — and drops DESCRIPTION entirely on a terminal too narrow to hold prose, rather than wrapping every summary into a four-line ribbon
- **Describes each clone once, not once per run** — a description is reused whenever the work behind it is byte-identical, judged by a content digest of the pending state rather than a modification date, which a deleted file leaves none of. Each machine caches only its own clones and resolves them during the scan, so the peer's answers ride back inside its snapshot and a report run from either machine starts warm; `--no-cache` crosses the hop to refresh both. The scan itself is never cached — its cost is the per-repo fetch and `gh issue list`, and both ask the remote something no local state can answer
- Degrades loudly when the peer is unreachable: the SSH error is named once in the summary and the report header, and the table falls back to the single-machine shape rather than quietly dropping half the picture
- Writes an HTML report to the repo's gitignored `tmp/` — one full-width block per project with the machines side by side in a column each, named once in a sticky header carrying their OS, projects root and scan age, so a column's position is what attributes its contents
- Recomputes every interval in the page rather than baking it in, so a report left open or reopened tomorrow still reads correctly; exact timestamps sit on hover
- Reports uncommitted-file lists and unpushed-commit subjects for the clones still awaiting a description, so Claude reads only the work that actually moved
- **Scopes to one repo with `--repo`**, which is what [`/repo-status`](#repo-status) invokes — the peer is told the slug too, so both ends scan one repo; the scoped run renders a block per machine instead of this table, writes no HTML, and merges the description cache rather than rebuilding it

---

### Repo Status

Cross-machine status of a single repo — this machine's clone and the peer's, side by side. The other half of [`/github-status`](#github-status): same scanner, same config, same description cache, scoped with `--repo` to the repo you are standing in. It answers "how does this repo stand" where the fleet report answers "which repos need attention", and it costs seconds rather than minutes because the peer is told the slug too and scans one repo instead of its own fleet.

**Command:** `/repo-status`

**Features:**
- **Has no scripts of its own** — one `SKILL.md` invoking `github-status/scripts/repos-status.py --repo`, so the scanner, the per-machine config and the description cache are shared rather than duplicated
- Resolves the repo to its `OWNER/REPO` origin slug before crossing to the peer, so the peer finds its own clone whatever path it keeps it at; a path or a slug both work as the argument
- **Prints a block per machine, not the fleet's table** — columns exist to align repos against each other, and one repo has nothing to align with
- **Omits every fact sitting at its default**: branch `main`, an upstream level in both directions, a current convention record, zero open issues. A clone with none of them reads `clean`, which is the whole line — what remains is only what is not ordinary
- Distinguishes unknown from zero — `gh` failing to answer prints `open issues unknown` rather than nothing, which would assert a count nobody checked
- Names a machine that was not reached with its SSH error, and one holding no clone as `no clone here`, rather than leaving either silent
- **Shares the description cache and merges into it** instead of rebuilding — a run that saw one repo has no opinion about the rest, so every other entry carries through untouched, on both machines; the peer's merge runs on the peer, which is the only side holding its own entries
- Terminal only. A repo found on no machine exits non-zero naming the reason, so an empty block never stands in for a clean one

---

### Move Project

Moves or renames the current project folder while preserving the Claude Code data tied to it — session logs, memory, subagent history. That data lives in its own directory keyed by a mangled form of the project's path, so a plain `mv` orphans it.

**Command:** `/move-project`

**Features:**
- Derives the old and new `~/.claude/projects/<key>` directory names from the path-mangling rule in `claude/skills/skill/references/claude-project-memory-paths.md`, so the session history follows the folder
- Previews both moves with their resolved paths before anything runs, and refuses a destination that already exists
- **Prints the commands rather than running them** — moving the working directory out from under a live session would break it, so they are run from elsewhere and Claude reopened at the new location
- Prints PowerShell alongside bash on Windows, bash alone on macOS and Linux
- Skips the data move for a project that has no `~/.claude/projects/` directory yet

---

### Annotate

Opens any file in Plannotator's browser annotation UI, not just the markdown and HTML it takes natively. Anything else is wrapped in a temporary `.md` with its contents in a fenced code block, annotated there, and the temporary file deleted afterwards.

**Command:** `/annotate <file>`

**Features:**
- Passes `.md` and `.html` straight through to `plannotator-annotate`; wraps everything else
- Infers the fence's language tag from the file's extension using the mapping table in the skill, and emits a bare fence for an extension it does not recognize
- Copies the file byte-for-byte into the fence — never transformed or summarized — so annotations line up with what is on disk
- Treats returned annotations as referring to the **original** file; the temporary `.md` is a presentation surface only
- Cleans up through `trap`/`try-finally` so the temporary file goes even on failure, warns before very large files, and refuses binaries

---

### Update Plannotator Plugin

Force-updates the plannotator plugin by clearing stale caches and reinstalling. The plugin only — the `plannotator` CLI has its own installer, and neither path moves the other.

**Command:** `/plannotator-update`

**Features:**
- Removes the marketplace cache (stale git clone that prevents updates)
- Removes the plugin cache
- Guides through reinstallation after restart
- Repairs the install registry, which the reinstall does not: deleting the cache leaves `installed_plugins.json` naming a version and a path that no longer exist, so `/plugin install` reports "already installed" and writes nothing
- Says what it does not cover, so a current plugin is not mistaken for a current CLI

---

### Doppler

Manages env-style secrets — API keys, tokens, passwords, connection strings — in [Doppler](https://www.doppler.com/) instead of a plaintext `.env`. Owns every `doppler` command template, so the coordinates and quoting are never reconstructed from memory.

**Command:** `/doppler`

**Features:**
- Reads the real project and config list up front, so `-p`/`-c` are never guessed (the workplace name is not a project, and a new app is a *config* inside a shared project rather than a project of its own)
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

### Skill Authoring

Conventions for writing and changing skills — the directory shape, the frontmatter, how the description controls auto-invocation, and what belongs in the body rather than a reference file. Read before creating or modifying any `SKILL.md`.

**Command:** `/skill`

**Features:**
- Fixes the layout: `SKILL.md` as the entry point, optional `scripts/` and `references/` beside it, shared resources in `skills/shared/`
- Treats the un-ignore line as part of *creating* a skill rather than a final step — an allowlisted skills directory leaves a new skill untracked and invisible, and the `skill-tracked.py` hook is a net, not the plan
- Spells out the `description` field's double duty — the skill list *and* the auto-invocation trigger — with explicit `TRIGGER when` / `DO NOT TRIGGER when` conditions
- Covers injecting dynamic context through `!` commands, and what that costs on every invocation
- Points at `references/claude-project-memory-paths.md` for the `~/.claude/projects/<project-id>/` mangling rule, so no skill re-derives it
- Carries the checks owed before writing anywhere shared — whether the destination is published, and which gitignore scope applies — plus the cross-platform rules for scripts that run on both Windows and macOS

---

### Adopt

Brings one repo into the shape the conventions in this repo currently require. Each change an already-conforming repo has to act on ships as a numbered **version** — one folder of prose under `claude/conventions/versions/`, written as instructions an agent follows — and `/adopt`, run in the repo that is behind, walks the versions that repo has not adopted yet and hands the record to `/commit`. What a version hands over for good is a **rule**, run from then on by the checker in that repo's commit gate.

**Command:** `/adopt`

**Features:**
- Keeps a repo's whole convention state as **one integer** in a committed `.claude/conventions` — a version is a migration, so it ran here or it did not, and the number says how far. One file and nothing beside it: a property that is per-machine rather than per-repo can never be a migration, since no number could be true of both machines at once, so it becomes a universal rule instead
- Advances that number by exactly one per version, through a command that refuses to lower it, to skip, or to name a version this dotfiles checkout does not have — a walk cannot leave the record claiming a migration nobody read
- Reads each version's prose in full and performs the migration itself; a version carries a script only where the work is mechanical and tedious, and every mutation is shown before it happens and applied only on a yes
- Settles "does this apply here" on the positive evidence the version names, so "nothing found" can never be read off "nothing looked at" — and a version that does not apply is still decided, with the number advancing and nothing mutated
- Puts a version's question to the user verbatim wherever no file can settle it — whether a repo wants a backlog at all, whether a missing LICENSE is deliberate — and never answers it on their behalf
- Stops on a branch behind its upstream, where a migration's delete merges cleanly against the other machine's append and loses it in silence — but never on a dirty tree, since the record and the pending change are meant to commit together
- Hands every continuing property a version defines to `claude/conventions/check.py`, which runs the rules the repo's number entitles it to on every commit, reports a rule that *could not look* as `UNMEASURED` rather than as a pass, and is the reason there is nothing here to re-sample by hand
- Keeps a second, ungated class of rule in `claude/conventions/universal/` for the properties no number could ever be true of — the memory-cache link is per-machine, so a fresh clone has genuinely not made it and a cleared cache breaks it years after any adoption, and the install links are the same shape one step closer to home, since v9 tells every repo to dial `~/.claude/conventions/check.py` and the gate therefore reads one of those links to run at all. These run in every repo whose gate calls the checker, whatever its number, fail that gate exactly as a versioned rule does, and each names the command that repairs what it found, since a repo meeting one for the first time has no version prose to read. Reaching every such repo with no adoption in between is the price, so anything a repo can adopt stays a version
- Lets a tool gate itself on the adopted number — it names the version it needs as a constant beside the code that reads the format, so a repo that has not migrated is refused rather than silently read with the wrong parser
- Enumerates what can never carry a version at all — agent behaviour, code content, unbounded properties, global settings — in `claude/conventions/not-versioned.md`, so "current" means every versionable convention has been decided rather than every rule in `CLAUDE.md` being satisfied

**Full guide:** [Conventions](docs/convention-versions.md) — how the system works: what a version is, what the record holds, how the notice → `/adopt` → `/commit` loop runs, and where the checker takes over. [What the conventions require](docs/convention-requirements.md) is the companion list — the set as it stands, one line per version, and which of them keep being re-checked.

**Authoring a version:** `claude/conventions/authoring.md` — the contract for adding one: the narrow test for when a version is owed at all, which half of a change is a migration and which is a continuing rule, the folder's four mandatory sections, the rule signature, and the two things every rule has to get right.

**Authoring gate:** `python claude/conventions/tests.py` — exit 0 the version set and its rules are sound, 1 otherwise. It asserts that every version folder parses and the numbers run contiguously, that all four mandatory sections are present, that versions and rules name each other in both directions, that a universal rule is introduced by no version and names the command that fixes what it finds, and that each rule comes back clean on a conforming tree, non-empty on a violating one and *raising* on a tree where git cannot answer — each built in a temp directory by the test itself, so no broken fixture tree is committed. This repo's `.claude/commit-checks.sh` runs it alongside `claude/conventions/check.py`, `claude/tests/memos.py`, `claude/tests/install-links.py`, `claude/tests/python-baseline.py` and `claude/tests/ingress-lint.py`, so a version that would edit every other repo on the machine cannot be committed here untested.

---

### Tune Output

Changes how Claude's replies are shaped — adopting, revising or rejecting a response-style rule — and records each pass in a ledger, so the next one starts from what was already measured rather than from scratch.

**Command:** `/tune-output`

**Features:**
- Keeps a ledger whose two most useful fields are the rejections and what evidence would re-open each one, since a rejection nobody wrote down gets re-proposed within months
- Routes a rule to one of four homes from a decision table — the output style for shape, the Overused Phrases section for a banned phrase, a memory file for a preference with a *why*, and CLAUDE.md for anything a subagent must also obey
- Records the verified mechanics behind that table in `references/mechanisms.md`: why CLAUDE.md is not system-prompt level, why a missing `keep-coding-instructions: true` silently drops the built-in engineering instructions, and why an unresolvable style name is a no-op that looks like a working session
- Tests a candidate before it ships, with both arms loading the real global CLAUDE.md — a config-less baseline measures the rule against a bare Claude and flatters it
- Renders the two arms side by side with the sides shuffled per pair and the mapping written only to a key file, so the read is blind for whoever ran it
- Requires trap cases, not just preference cases: an under-determined failure and a completion report whose items only look verified are what catch a rule that makes the model assert more than it knows
- Names every rule for the behaviour it produces rather than for a characteristic of the reader, because this repo is public and a commit cannot be taken back

---

### Transcrypt

Encrypts designated files with [transcrypt](https://github.com/elasticdog/transcrypt) so they are ciphertext in git history but plaintext in the working tree, or unlocks an already-encrypted repo after a fresh clone. See [Encrypted memory](#encrypted-memory-secretmd) for how this repo uses it.

**Command:** `/transcrypt`

**Features:**
- Uses one shared passphrase from Doppler (`tools/prd` → `TRANSCRYPT_KEY`), never a freshly generated one
- Marks files by the `*.secret.*` naming convention in `.gitattributes`
- Verifies the index holds ciphertext while the working tree stays readable, and stages without committing
- Relies on the global pre-commit guard as a safety net against committing an unencrypted secret
- Silences OpenSSL's `deprecated key derivation` warning by pointing `transcrypt.openssl-path` at an idempotent shim, rather than touching the KDF — so blobs stay byte-compatible with a machine running stock transcrypt

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

Surfaces the open `/memo` backlog (`.claude/memos/`, resolved at the git root, numbered newest-first) as a **transient status-bar reminder** so a fresh or freshly cleared session shows "what's next" without the user typing anything — then clears it the moment they start working. It imports `memos.py` for the parse rather than re-implementing it, and only in the session-start mode — the status line refreshes every couple of seconds and stays off that path. Three wired entry points:

- **`SessionStart`** (`startup`/`clear`, no arg) — writes a per-session state file with the open memos, each carrying its slug, title, platform tag and whether that platform is this machine. Those last two are resolved once, here, because this mode already forks git and imports `memos.py`. Injects **nothing** into chat, so the model never greets with or pushes the backlog — the status bar is the only reminder.
- **`statusLine`** (`statusline` arg, `refreshInterval: 2`) — renders the compact backlog (top 3 + a `+N more` line) from the state file alone, deciding nothing; the interval makes it appear within ~2s while the session is idle. The summary line counts how many of the *hidden* memos are bound to the other platform — without it the bar would be the one surface a binding never reaches, since the backlog is newest-first and a bound memo is rarely among the newest three.
- **`UserPromptSubmit`** (`on-prompt` arg) — clears the state (the bar reminder is done). If the message is a bare number — or `memo N` / `start N` / `do N` / `pick N` — it injects, bound to that prompt, which memo N maps to, so Claude reliably starts it instead of treating the number as noise. The injection carries the memo's **slug** and the commands to read it in full and to close it, since the bar showed only its title. Never the number: this state was written at session start while `memos.py` resolves a number against the live listing, so any `add` or `done` since then would make it name a different memo. A memo bound to the other platform gets an extra clause — do the portable part here, route the rest to the live session on that box.

Stays silent when there's nothing open. Needs no environment variable. See the [Memo](#memo) skill for how items get there and the other two moments they resurface (task completion, `/commit`).

---

### Install Check

**File:** `claude/hooks/check-install.py`

A `SessionStart` hook verifying every symlink and git setting the [install blocks](#global-installation) create — each link in those blocks plus `core.hooksPath`, `core.excludesFile` and `core.attributesFile`. Silent unless something is broken; it also runs by hand as `python ~/.claude/hooks/check-install.py`, where it prints a pass/fail line per check.

A missing link is silent in a way that looks like working software, and each one fails differently: no `output-styles` link leaves `outputStyle` in `settings.json` resolving to nothing, so response-style rules apply on one machine and not the other; no `memory` link sends saved memories outside the repo; no `learnings` link makes every lookup come back empty as though nothing had been written down. None of it shows in git, because the links are machine-local while the settings depending on them are committed and identical everywhere.

- **Paths are compared by inode (`os.path.samefile`), never as strings.** These links store `projects` where the disk spells it `Projects`, so a textual comparison passes or fails depending on whether the script was reached through the symlink or from the repo. The inode test also catches a "link" that is really a copy — what Git-Bash `ln -s` leaves behind on Windows, and what every textual check calls healthy.
- **A link the OS refuses to follow is reported, not crashed on.** Windows declines to follow a reparse point created by a non-administrator, `samefile` raises on one, and `realpath` then raised again from inside the handler explaining it — which exited 0 with no output at all, so a broken install read as a clean report. Three links were in that state on the Windows machine while this printed nothing. The check now names the refusal and where the link points; a crash anywhere in it prints the traceback by hand, and says the install is unverified as a hook.
- **No matcher**, deliberately. The events reference lists `|` among the characters that keep a matcher an *exact* string, which would make `startup|resume` match nothing and the hook silently never fire; an absent matcher is the one form certain to run. A broken install is a persistent state rather than a passing event, so re-reporting it after a `/clear` is honest rather than noisy.
- **It cannot verify `~/.claude/settings.json` or `~/.claude/hooks` when run as a hook**, since it is reached through them — but nothing else runs either when those are broken, so the hook firing at all is what vouches for them. Run it from the repo to check them for real.

Adding a link to the install blocks needs a matching line in the script's `LINKS` list, which is the only other copy of that contract — and `claude/tests/install-links.py`, run by this repo's commit gate, fails the commit when the two disagree or when the Windows and Linux blocks install different sets. That check exists because the `conventions` link was in both blocks and in neither list, so it was never created on either machine and this script called the install clean on both.

---

### Conventions Check

**File:** `claude/hooks/conventions-check.py`

A `SessionStart` hook comparing two integers: the newest convention version in this dotfiles checkout, and the highest one the current repo has recorded. Silent when they agree. When they don't, it prints the gap and offers [`/adopt`](#adopt) — at most five bullets and then `... N more`, because a line per pending version at every session start is a wall nobody reads.

It runs **no subprocess at all**: the repo root by walking up for a `.git`, `.git/config` as text for the origin owner, the record file, one `listdir` of the versions directory with a head-read of each README's frontmatter, and this checkout's `.git/HEAD` for a short sha. Every message that claims a "latest" version names that sha, so that claim is never unqualified — the diagnostic messages, which name no version, carry no sha. It verifies nothing: whether the repo still *holds* the shape its number claims is the checker's question, asked at every commit rather than at every session start.

- **"Unrecorded" and "v0" are different facts** and get different lines — a repo with no record file is asked to record where it stands, while one at v0 is told how far behind it is.
- **A record naming a version this checkout does not have** means the dotfiles repo is behind, not the project. It says so and withholds the `/adopt` offer, since adopting against a stale version set records a repo as current against a `latest` that has already moved.
- **A directory with no `.git` is told once**, and only where a `.claude/` or a `CLAUDE.md` is present, so a scratch directory stays silent while a real project directory stops being outside the system with nothing anywhere saying so.
- **A record it cannot read at all** — a content line that is neither a number nor an `exempt` reason, a permission bit, bytes that are not UTF-8 — names what stopped it and withholds `/adopt`, and so does a version set that will not load; an `exempt` record, or an origin owned by anyone other than the user, is silent.

The message is a `systemMessage`, so it reaches the screen and never the transcript; `/adopt` re-derives the gap itself rather than trusting what was pasted into it. The notice's shape and what its silence means are in [Conventions](docs/convention-versions.md).

---

### Doppler Guard

**File:** `claude/hooks/doppler-guard.py`

A `PreToolUse` backstop on `Bash`, `Write`, and `Edit`. Hook matchers scope by tool *name* only, so the script self-filters: it exits silently unless the call's command, content, or path mentions Doppler anywhere.

When it matches, it does two things:

- **Injects the conventions** — a condensed reminder citing the [Doppler](#doppler) skill, so a wrong project or config gets corrected at the moment of the command even if the skill was never invoked.
- **Denies a `doppler secrets set`/`delete` that omits `--silent`** — without it Doppler prints the full secrets table, every value included, into the transcript. The deny inspects only the Bash `command`, so prose or docs that merely mention the command still get the reminder rather than a block, and a bare `-h`/`--help` is exempt since usage output carries no values.

---

### Windows Link Guard

**File:** `claude/hooks/windows-link-guard.py`

Windows does not follow a reparse point created by a non-administrator — RedirectionGuard, WinError 448 — and it refuses a symlink exactly as readily as a junction. A link made from an ordinary Git Bash is therefore created, resolves from the shell that made it, and raises in whichever process has to read it next. Measured 2026-09-18 on the Windows machine: three of the twelve `~/.claude` install links and all 19 project memory caches were in that state, and the one that surfaced dropped a whole machine out of [GitHub Status](#github-status) while leaving [`/adopt`](#adopt) unable to load its own engine there.

A `PreToolUse` on `Bash`, gated by four `if` patterns — `powershell *ItemType*`, `pwsh *ItemType*`, `cmd *` and `mklink *` — so an ordinary command never starts the interpreter. It exits silently off Windows, and on a command that merely names the verbs rather than running them, since `grep -rn "New-Item -ItemType Junction"` is not an invocation. Otherwise it asks PowerShell whether this shell is elevated and, when the answer is no or unobtainable, blocks with exit 2, quoting the command it saw and naming the elevated form to run instead.

The `if` gate is best-effort and fails open — a command the harness cannot decompose reaches the script whatever the pattern says — so the script's own match is what decides, never the gate. It also only ever sees what Claude runs: a link made by hand in a terminal is caught later instead, by [Install Check](#install-check) for the ones under `~/.claude` and by the `memory-cache-linked` rule for each repo's own cache.

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

**Tests:** `python claude/tests/ingress-lint.py` — exit 0 all cases behave, 1 otherwise. It pins the compose rules, the delegation, the silent skips and all three NOT CHECKED paths, and it stubs landlord so it runs on a machine with no checkout.

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

## Output Styles

The `claude/output-styles/` directory holds response-shape rules — how a reply is laid out and worded, as opposed to what it is allowed to do. Each style is one markdown file whose frontmatter carries a `name`, a one-line `description`, and `keep-coding-instructions: true`; the body is the guidance itself. The `/tune-output` skill owns the process for changing them and keeps its ledger of what has already been tried.

A style takes effect only when `claude/settings.json` selects it by name:

```json
"outputStyle": "action-first"
```

Two things about that key are worth knowing before debugging one. The name is resolved against `~/.claude/output-styles/` and the project's own `.claude/output-styles/`, so a missing symlink leaves the selection pointing at nothing — and **an unresolvable name is a silent no-op**: no warning, exit 0, a session that looks exactly like a working one. And omitting `keep-coding-instructions: true` from a style file quietly drops the built-in engineering instructions instead of adding to them. Run `sh ~/.claude/skills/tune-output/scripts/preflight.sh` to see the selected name and the resolved file separately, which is the only way to tell those apart.

---

## Remote Session

The `claude/remote-session/` directory holds a Claude session that runs on the Windows machine and
can be watched from both machines at once — a keystroke in agterm on the Mac and an ordinary
terminal on Windows, attached to the same session simultaneously. The agent is a native Windows
process with a real Windows working directory, so it can build and drive Windows GUI applications;
WSL and tmux only hold the terminal it lives in.

It lives here rather than in its own repo because both halves come from one checkout: the Windows
holder and the Mac attach script arrive together on a single `git pull`.

Setup, daily use and what it does not survive are in
[`claude/remote-session/README.md`](claude/remote-session/README.md); the measurements that shaped it
are in `claude/learnings/windows-persistent-terminal-session.md`.

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
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude" | Out-Null
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\CLAUDE.md" -Target "$PWD\claude\CLAUDE.md"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills" -Target "$PWD\claude\skills"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\hooks" -Target "$PWD\claude\hooks"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\settings.json" -Target "$PWD\claude\settings.json"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\learnings" -Target "$PWD\claude\learnings"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\memory" -Target "$PWD\claude\memory"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\scripts" -Target "$PWD\claude\scripts"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\output-styles" -Target "$PWD\claude\output-styles"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\conventions" -Target "$PWD\claude\conventions"
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
ln -s "$(pwd)/claude/output-styles" ~/.claude/output-styles
ln -s "$(pwd)/claude/conventions" ~/.claude/conventions
ln -s "$(pwd)/git/hooks" ~/.git-hooks
ln -s "$(pwd)/git/gitignore" ~/.gitignore
ln -s "$(pwd)/git/gitattributes" ~/.gitattributes
git config --global core.hooksPath ~/.git-hooks
git config --global core.excludesFile "~/.gitignore"
git config --global core.attributesFile "~/.gitattributes"
```

### Verifying the install

Confirm every link above resolves, on this machine:

```bash
python ~/.claude/hooks/check-install.py
```

It prints a pass/fail line per link and per git setting, and the same script runs at every session start — silent unless something is broken. A link added to the blocks above needs a matching line in its `LINKS` list or it goes unchecked, which the commit gate now asserts rather than leaving to memory. See [Install Check](#install-check) for what it catches and what it cannot.

### Python interpreter

Every Python hook and the statusline in `claude/settings.json` invoke the interpreter as `python`, never `python3`. That is deliberate and measured: on both platforms the `python3` name resolves to an indirection rather than the real binary — a bash shim on Windows and an `xcode-select` dispatcher on macOS — and each costs a spawn on every hook. Nothing else on `PATH` may shadow it, so a machine that lacks a real `python` runs no hooks at all. Figures live in `claude/skills/hooks/references/performance.md`.

Windows satisfies this out of the box. macOS does not — Apple ships no `python`, and the Command Line Tools `python3` is stuck on 3.9, which is old enough that ordinary annotations like `str | None` fail at import. Install a current Python and expose it under the bare name:

```bash
brew install python
mkdir -p ~/.local/bin
ln -s /opt/homebrew/bin/python3 ~/.local/bin/python
```

Point the symlink at `/opt/homebrew/bin/python3`, not at the versioned `libexec/bin/python`, so it follows future upgrades. Make sure `~/.local/bin` is on `PATH`, then confirm with `python -V`.

The `/memo` skill and the memo commands inside `/commit` and `/wrap-up` use the bare `python` too, allowlist strings included — an allowlist that names a different interpreter than its command makes every call prompt for permission.

### UTF-8 mode

The `env` block of `claude/settings.json` sets `PYTHONUTF8=1`, which puts every Python process Claude Code spawns into UTF-8 mode. It is there for a failure that is invisible on macOS and silent on Windows: Claude Code writes each hook's JSON payload to stdin as UTF-8 bytes, but Python on Windows decodes stdin with the system ANSI codepage. **It does not raise** — CPython opens stdio with `errors="surrogateescape"`, so the bytes come through *mangled into mojibake* rather than rejected, `json.load` succeeds because JSON's own punctuation is ASCII, and the hook runs happily on a populated but corrupted payload. Nothing reaches the never-raise `except`; there is no crash and no log line, which is exactly why it went unnoticed.

What that actually costs, measured on the Windows machine: under a non-ASCII repo path `memos.py` decodes `git rev-parse --show-toplevel` with the locale codec and writes the whole backlog into a garbage sibling directory *outside* the repo while printing a plausible in-repo path, and `skill-tracked.py` takes its early return because the mangled path fails `os.path.isdir`, so its warning never fires. One env var closes both, survives `python -S`, and reaches hook scripts living in repos this one cannot edit. It is process-wide rather than hook-scoped, so it also changes the default encoding of every bare `open()` and of `subprocess.run(..., text=True)` — a script reading a codepage-encoded file now raises under Claude Code while still working in a plain terminal.

Because the symlink lives outside the repo, it is the one setup step no `git clone` restores. A machine missing it fails silently — hooks simply never fire.

Every invocation also passes `-S`, which skips `site` — the single largest slice of interpreter startup. **The cost is that `site-packages` is off `sys.path`, so every hook must stay stdlib-only.** All of them currently are. A hook needing a third-party package must drop `-S` on its own command line rather than for all of them.

### Screenshot capture helper (macOS)

The `docs-relevance` skill takes screenshots through a small helper rather than through the agent's own binary. macOS grants Screen Recording to a *binary*, and the agent's is version-named, so granting it there would both go stale on every update and hand whole-display access to every session forever. A purpose-built bundle at a fixed path is granted once and scoped to the one job. Build it once per machine:

```bash
bash claude/skills/docs-relevance/scripts/build-docshot.sh
```

That installs `DocShot.app` into `~/Applications`. Grant it Screen Recording the first time it asks — a denial is silent rather than loud, since window ids, owners and bounds all still populate while every window *title* comes back empty, so use the helper's `--check` probe to confirm the grant is live instead of discovering it as a black PNG. The grant is pinned to the bundle's ad-hoc signature, so the script refuses to clobber an existing install unless passed `--force`; rebuilding resets the grant.

Like the `python` symlink above, this lives outside the repo and is not restored by `git clone`.

## Memory

Two complementary stores hold accumulated cross-session knowledge, and they reach
a session by different routes:

- **Global memory** (`claude/memory/`, deployed to `~/.claude/memory/` via
  symlink) — cross-project preferences, feedback, and references meant to apply
  everywhere. `claude/memory/MEMORY.md` indexes every one of them and is the only
  global index edited by hand; nothing loads it on its own. An entry marked
  `{always}` there is also rendered into `CLAUDE.md` by
  `claude/scripts/render-memory-index.py`, and CLAUDE.md *is* injected into every
  session — so the marker is what decides whether a memory fires unprompted or
  merely stays findable. A commit check re-renders the block and fails on any
  difference, which is what keeps the two from drifting apart as they once did.
- **Project memory** — facts specific to a single repo. Claude Code writes these
  to a machine-local cache (`~/.claude/projects/<path-encoded>/memory/`) that is
  **not** version controlled, so the knowledge is invisible from other machines
  and lost if the cache is cleared.

### Versioning project memory

The `claude/scripts/link-project-memory.sh` script redirects a project's memory
cache, by symlink, into a committed `.claude/memory/` directory inside that repo.
The harness keeps reading and writing the same path, so auto-recall is unaffected;
the files just live in the repo now and travel with `git clone`.

Run once per project, per machine — from inside the repo, and on Windows from an
elevated shell. Windows will not follow a link created by a non-administrator
([Windows Link Guard](#windows-link-guard) has the mechanics), so without
elevation the script refuses and prints the command to run rather than leaving a
link behind that some process will not walk:

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
